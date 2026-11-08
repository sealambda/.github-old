"""Find the citations of records, specs and documentation pages in a text.

A citation is a piece of text that names a record, a spec or a page of the
repository. This module only finds them. `decisions.check` decides whether each
one resolves. The forms are in `docs/reference/decision-records.md`.

Every pattern requires digits, so the placeholder `NNNN` in a template or in
prose never matches.
"""

import bisect
import functools
import itertools
import posixpath
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from enum import Enum, StrEnum, auto
from pathlib import PurePosixPath
from typing import NamedTuple

from decisions.records import RECORD_NAME, RECORDS_DIR

PROSE_SUFFIXES = frozenset({".md", ".markdown", ".txt", ".rst", ".adoc"})
"""File suffixes whose text is split into sentences. Other files, such as code
and configuration, are split into lines."""

# Four digits and nothing else of digits around them.
_FOUR_DIGITS = r"(?<![0-9])[0-9]{4}(?![0-9])"

# The number of a record or a spec: exactly four digits. A dash and a digit after
# it would make a date such as 2026-11-08, so that is not a number either.
_NUMBER = _FOUR_DIGITS + r"(?!-[0-9])"

# The dash between the ends of a range: a hyphen or an en dash, with optional
# spaces around it.
_DASH = r"\s*[-–]\s*"

# The second end of a range written with a dash. A dash and a letter or a digit
# right after it make the text a slug or a date, as in `NNNN-2026-roadmap`, so
# the four digits are not an end.
_RANGE_END = _FOUR_DIGITS + r"(?![-–][0-9A-Za-z])"

# The dash between the ends of a range after a singular keyword: an en dash,
# with optional spaces, or a hyphen with a space on both sides. A hyphen with no
# space or one space is written inside a name such as `ADR-NNNN-MMMM`, so only a
# plural keyword makes it a range.
_SPACED_DASH = r"(?:\s+-\s+|\s*–\s*)"

# A range of two numbers, as `NNNN-NNNN` or `NNNN–NNNN`. The dash must lead to a
# second four-digit number that is an end (`_RANGE_END`), so a date is not a
# range, and neither is a slug that starts with four digits. After a plural
# keyword, any dash joins the ends. After a singular keyword, only `_SPACED_DASH`
# does.
_PLURAL_RANGE = _FOUR_DIGITS + _DASH + _RANGE_END
_SINGULAR_RANGE = _FOUR_DIGITS + _SPACED_DASH + _RANGE_END

# A number that the range pattern refused because its second end is the start of
# a slug or a date, as the first `NNNN` of `NNNN-2026-roadmap`. The number alone
# is cited: the dash and the digits after it are part of the slug. The digits
# after the dash stay out of the match, because they are not cited.
_SLUG_LEAD = _FOUR_DIGITS + "(?=" + _DASH + _FOUR_DIGITS + r"[-–][0-9A-Za-z])"

# A number that a singular keyword cites alone, because a hyphen with no space
# and four digits follow it, as the first `NNNN` of `ADR-NNNN-MMMM`. The digits
# after the hyphen are part of a name or a year, not a second record.
_HYPHEN_LEAD = _FOUR_DIGITS + "(?=-" + _FOUR_DIGITS + ")"

# Between two numbers of a list: `, `, ` and `, `, and `, ` or ` or ` to `, in
# any letter case.
_LIST_SEPARATOR = r"(?:\s*,\s*(?:(?i:and|or)\s+)?|\s+(?i:and|or|to)\s+)"

_PLURAL_ITEM = f"(?:{_PLURAL_RANGE}|{_NUMBER}|{_SLUG_LEAD})"
_SINGULAR_ITEM = f"(?:{_SINGULAR_RANGE}|{_NUMBER}|{_SLUG_LEAD}|{_HYPHEN_LEAD})"

# The list of numbers and ranges that follows a keyword. The keyword decides
# which items it holds, and every item of the list takes the rule of the keyword
# that starts the list: in `ADRs NNNN, MMMM-PPPP` the later hyphen follows a
# plural keyword.
_PLURAL_LIST = f"{_PLURAL_ITEM}(?:{_LIST_SEPARATOR}{_PLURAL_ITEM})*"
_SINGULAR_LIST = f"{_SINGULAR_ITEM}(?:{_LIST_SEPARATOR}{_SINGULAR_ITEM})*"

# The text between two numbers of a list that makes them the ends of a range:
# `to` in any letter case, a hyphen or an en dash, with optional spaces. The list
# patterns already refuse a joiner that the keyword does not allow.
_RANGE_JOINER = re.compile(r"\s*(?:(?i:to)|[-–])\s*")

# `ADR NNNN`, `ADR-NNNN` and `ADRs NNNN and NNNN`, or `decision record NNNN`,
# with digits for each `NNNN`. The groups `plural` and `singular` hold the list
# of the plural keywords (`ADRs`, `decision records`) and of the singular ones
# (`ADR`, `ADR-`, `decision record`). Exactly one of them matches.
# The bare word `record` is not a form: "audit records 2024 to 2026" is prose.
_RECORD_LIST = re.compile(
    r"\b(?:(?i:ADRs(?:\s+|-)|decision\s+records\s+)(?P<plural>"
    + _PLURAL_LIST
    + r")|(?i:ADR(?:\s+|-)|decision\s+record\s+)(?P<singular>"
    + _SINGULAR_LIST
    + "))"
)
_SPEC_LIST = re.compile(
    r"\b(?:(?i:specs)\s+(?P<plural>"
    + _PLURAL_LIST
    + r")|(?i:spec)\s+(?P<singular>"
    + _SINGULAR_LIST
    + "))"
)
_NUMBER_PATTERN = re.compile(_FOUR_DIGITS)

_RECORDS_FOLDER = f"{RECORDS_DIR}/"

# Where the record folder of THIS repository can start in a text. Either a path
# from the root, with an optional `./`, that no other path segment precedes: a
# nested `services/api/docs/decisions/` is another folder, which is not checked.
# Or a `github.com` address of a file in the folder, as in
# `https://github.com/<owner>/<repo>/blob/<ref>/docs/decisions/`; the `owner`
# and `repo` groups hold the repository, and the caller compares them with the
# repository that it checks. A `<ref>` is one path segment: a branch name that
# holds a slash is not recognized.
_RECORDS_FOLDER_START = (
    r"(?:(?<![\w./-])(?:\./)?"
    r"|(?<![\w.-])github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)"
    r"/(?:blob|tree)/[\w.-]+/)" + re.escape(_RECORDS_FOLDER)
)

_RECORD_PREFIX = re.compile(_RECORDS_FOLDER_START + r"(?P<number>[0-9]{4})-")

_RECORD_FILE_NAME = r"[0-9]{4}-[a-z0-9]+(?:-[a-z0-9]+)*\.md(?![\w-])"

# A record file name right after the record folder, as in
# `docs/decisions/NNNN-x.md` and `https://host/o/r/blob/main/docs/decisions/NNNN-x.md`.
_FILE_IN_RECORDS_FOLDER = re.compile(
    _RECORDS_FOLDER_START + "(?P<name>" + _RECORD_FILE_NAME + ")"
)

# A relative path to a record file, as `0007-x.md` or `../decisions/0007-x.md`.
# Whether it names a record depends on the file that holds it.
_RELATIVE_FILE = re.compile(
    r"(?<![\w./-])(?P<folder>(?:[\w.-]+/)*)(?P<name>" + _RECORD_FILE_NAME + ")"
)

_DOC_PATH = re.compile(
    r"""
    (?<![\w./-])(?:\./)?                    # the path starts at the root
    (?P<path>docs/(?:[\w.-]+/)*[\w.-]+\.md)
    (?![\w-])
    """,
    re.VERBOSE,
)

_PLACEHOLDER = "NNNN"

# The name of a repository other than the checked one, in two forms: the
# address `github.com/<owner>/<repo>`, and the short `<owner>/<repo>` with the
# owner of the checked repository. The short form is built per repository, in
# `_mention_pattern`.
_URL_MENTION = r"(?<![\w.-])github\.com/(?P<url_owner>[\w.-]+)/(?P<url_repo>[\w.-]+)"

# The first path segments that github.com reserves: an address that starts with
# one of them is a page of GitHub, not `github.com/<owner>/<repository>`.
_RESERVED_GITHUB_PATHS = frozenset(
    {
        "about",
        "account",
        "apps",
        "codespaces",
        "collections",
        "contact",
        "copilot",
        "customer-stories",
        "enterprise",
        "events",
        "explore",
        "features",
        "git-guides",
        "issues",
        "login",
        "marketplace",
        "new",
        "notifications",
        "orgs",
        "pricing",
        "pulls",
        "readme",
        "resources",
        "search",
        "security",
        "sessions",
        "settings",
        "signup",
        "site",
        "solutions",
        "sponsors",
        "stars",
        "team",
        "topics",
        "trending",
        "users",
        "watching",
    }
)

# A Markdown inline link: its text and its address are one unit. Neither part
# holds a bracket, and each part has a length limit. Both keep the match time
# linear in the segment: from one `[`, the scan ends at the next bracket or
# after at most 3000 characters, so a long line of `[` costs one step each.
_MARKDOWN_LINK = re.compile(r"\[[^\[\]]{0,1000}\]\([^)\[\]]{0,2000}\)")

# The rest of an address or path that continues after a repository name.
_ADDRESS_TAIL = re.compile(r"[^\s`'\"<>()\[\]]*")

# What may stand between a repository name and the citation that it qualifies:
# space, quotes, code marks, a colon, a comma, a dash, an opening bracket, `'s`.
_QUALIFIER_GAP = re.compile("(?:['’]s|[\\s`'\"*_:,(\\[–—-])*")

_SENTENCE_BREAK = re.compile(
    r"""
      \n[ \t]*\n                            # a blank line
    | \n[ \t]*(?:[-*+]|[0-9]+[.)])[ \t]     # the start of a list item
    | \n[ \t]*[|#>`~]                       # a table row, heading, quote or fence
    | (?<=[.!?])\s+(?=[A-Z0-9`"'(\[*])      # the end of a sentence
    """,
    re.VERBOSE,
)


class CitationKind(StrEnum):
    """What a citation names."""

    RECORD_NUMBER = "record number"
    RECORD_FILE = "record file"
    SPEC_NUMBER = "spec number"
    DOC_PATH = "documentation path"
    REVERSED_RANGE = "reversed range"
    """A range of numbers whose end is lower than its start. The value is the
    range as `NNNN to MMMM`."""
    OVERSIZED_RANGE = "oversized range"
    """A range that the budget of the file did not allow to expand. The value is
    the range as `NNNN to MMMM`."""


MAX_RANGE_NUMBERS = 10_000
"""How many numbers the ranges of one file may name in all.

One range `0001 to 9999` names 9999 numbers, so one full-width range fits. The
limit stops a file from repeating such a range thousands of times: each
repetition would add as many findings, in time and memory without bound. A range
that does not fit is not expanded, and `check` reports it."""


@dataclass
class _RangeState:
    """What the ranges of one file share: the budget of numbers and the ids.

    Attributes:
        remaining: The numbers still allowed. `scan_text` makes one state for
            each file and passes it down, so every range of the file draws on it.
        issued: How many range ids `new_range_id` has given out.
    """

    remaining: int = MAX_RANGE_NUMBERS
    issued: int = 0

    def take(self, count: int) -> bool:
        """Use `count` numbers when they fit, and tell whether they did."""
        if count > self.remaining:
            return False
        self.remaining -= count
        return True

    def new_range_id(self) -> int:
        """Return an id that no other range of the file has."""
        self.issued += 1
        return self.issued


@dataclass(frozen=True)
class Citation:
    """One citation in a text.

    Attributes:
        kind: What the citation names.
        value: The number, the file name or the path that it names.
        line: The 1-based line where the citation starts.
        range_id: For a number that a range names: an id that the numbers of
            the same range share, unique in the file. `None` for a number that
            the text cites alone, and for every other kind.
    """

    kind: CitationKind
    value: str
    line: int
    range_id: int | None = None


class _Found(NamedTuple):
    """A citation in a segment: where it starts, before its line is known.

    Attributes:
        start: The position of the cited expression in the segment, or in the
            text once `scan_text` has added the offset of the segment.
        kind: What the citation names.
        value: The number, the file name or the path that it names.
        range_id: The id of the range that names the number, if one does.
    """

    start: int
    kind: CitationKind
    value: str
    range_id: int | None = None


class _Link(Enum):
    """How the text between two numbers of a list joins them."""

    NONE = auto()
    """No range: a comma, `and` or `or`, or anything but a range joiner."""
    SAME = auto()
    """A range joiner between two equal numbers: one number, once."""
    RANGE = auto()
    """A range from the lower number to the higher, which fits the budget."""
    REVERSED = auto()
    """A range whose end is lower than its start."""
    OVERSIZED = auto()
    """A range that does not fit in what is left of the budget."""


def scan_text(
    text: str, repository: str, *, path: PurePosixPath, prose: bool
) -> list[Citation]:
    """Find every citation in `text` that is about this repository.

    The text is cut into segments: sentences for prose, lines for anything
    else. In a segment, a citation that another repository qualifies is skipped.
    A repository name qualifies the citation that directly follows it and the
    citations in its own address or Markdown link, not the rest of the sentence.

    A range names every number from its start to its end, up to
    `MAX_RANGE_NUMBERS` numbers in all ranges of the text, also those that
    another repository qualifies. Every number of a range has the line of the
    keyword that starts its list, and the `range_id` of the range, so that a
    caller can treat the numbers of one range as one citation.

    Args:
        text: The content of one file.
        repository: The `owner/name` of the repository that holds the file.
        path: The path of the file relative to the checked root. A file name
            without a folder names a record only in a file of the record folder.
        prose: Whether to cut the text into sentences (Markdown and plain text)
            or into lines (code and configuration).

    Returns:
        The citations in order of appearance.
    """
    newlines = [match.start() for match in re.finditer("\n", text)]
    found: list[_Found] = []
    state = _RangeState()
    for offset, segment in _segments(text, prose=prose):
        foreign = _foreign_regions(segment, repository)
        found.extend(
            item._replace(start=offset + item.start)
            for item in _find_in_segment(segment, path, repository, state)
            if not any(first <= item.start < stop for first, stop in foreign)
        )
    return [
        Citation(
            item.kind,
            item.value,
            bisect.bisect_left(newlines, item.start) + 1,
            item.range_id,
        )
        for item in sorted(found, key=_position)
    ]


def _position(item: _Found) -> int:
    """Return the start of a found citation: the sort key that keeps text order.

    The sort is stable, so two citations that start at the same place, as a
    record number and a record file after `docs/decisions/`, keep the order in
    which `_find_in_segment` yields them.
    """
    return item.start


def _segments(text: str, *, prose: bool) -> Iterator[tuple[int, str]]:
    """Yield `(offset, segment)` pairs that cover `text`."""
    if not prose:
        offset = 0
        for line in text.splitlines(keepends=True):
            yield offset, line
            offset += len(line)
        return
    start = 0
    for match in _SENTENCE_BREAK.finditer(text):
        yield start, text[start : match.start()]
        start = match.end()
    yield start, text[start:]


def _foreign_regions(segment: str, repository: str) -> list[tuple[int, int]]:
    """Return the `(first, stop)` ranges of start positions that are foreign.

    A citation that starts in a range is qualified by another repository. The
    ranges of one foreign repository name are:

    - the name and the rest of its address or path, as in
      `github.com/other/repo/blob/main/docs/decisions/0038-x.md`;
    - the position of the citation that directly follows the name, after
      `_QUALIFIER_GAP`;
    - every Markdown link that holds the name, text and address together.

    Args:
        segment: One sentence or one line.
        repository: The `owner/name` of the repository that holds the file.
    """
    mentions = list(_foreign_mentions(segment, repository))
    if not mentions:
        return []
    links = [link.span() for link in _MARKDOWN_LINK.finditer(segment)]
    regions: list[tuple[int, int]] = []
    for start, end in mentions:
        tail_end = _address_end(segment, end)
        regions.append((start, tail_end))
        if tail_end == end:
            after_gap = _end_of_match(_QUALIFIER_GAP, segment, end)
            regions.append((after_gap, after_gap + 1))
        regions.extend(link for link in links if link[0] <= start < link[1])
    return regions


def _foreign_mentions(segment: str, repository: str) -> Iterator[tuple[int, int]]:
    """Yield `(start, end)` of each name of a repository other than `repository`.

    The end leaves out the sentence punctuation and the `.git` suffix. An
    address that is a page of GitHub, such as `github.com/orgs/x`, is no name.
    """
    wanted = repository.lower()
    for match in _mention_pattern(repository).finditer(segment):
        if match["url_owner"]:
            owner, group = match["url_owner"], "url_repo"
            if owner.lower() in _RESERVED_GITHUB_PATHS:
                continue
        else:
            owner, group = match["short_owner"], "short_repo"
        raw = match[group]
        name = _clean_repository_name(raw)
        if f"{owner}/{name}".lower() != wanted:
            yield match.start(), match.end(group) - (len(raw) - len(name))


@functools.cache
def _mention_pattern(repository: str) -> re.Pattern[str]:
    """Return the pattern for the names of repositories, for one checked repository.

    It matches `github.com/<owner>/<repo>` and the short `<owner>/<repo>`. The
    owner of the short form is the owner of `repository`, in any letter case.
    """
    owner = repository.partition("/")[0]
    return re.compile(
        _URL_MENTION
        + r"|(?<![\w./-])(?P<short_owner>(?i:"
        + re.escape(owner)
        + r"))/(?P<short_repo>[\w.-]+)"
    )


def _address_end(segment: str, end: int) -> int:
    """Return where the address or path that continues after `end` stops.

    A repository name followed by `/` is the start of a longer address, which
    ends at a space, a quote, a bracket or the end of the segment. Otherwise
    the name ends at `end`.
    """
    if not segment.startswith("/", end):
        return end
    return _end_of_match(_ADDRESS_TAIL, segment, end)


def _end_of_match(pattern: re.Pattern[str], text: str, position: int) -> int:
    """Return where `pattern` ends when it matches at `position`, else `position`.

    The patterns that this module passes can match the empty string, so a
    match is the normal case.
    """
    match = pattern.match(text, position)
    return position if match is None else match.end()


def _clean_repository_name(name: str) -> str:
    """Drop the sentence punctuation and the `.git` suffix after a repository."""
    name = name.rstrip(".-")
    return name.removesuffix(".git")


def _find_in_segment(
    segment: str, citing: PurePosixPath, repository: str, state: _RangeState
) -> Iterator[_Found]:
    """Yield each citation in one segment.

    The start is where the cited expression begins: the keyword of a number,
    or the first character of a path. The ranges of the segment draw on `state`.
    """
    yield from _find_numbers(segment, repository, state)
    yield from _find_record_files(segment, citing, repository)
    for match in _DOC_PATH.finditer(segment):
        if _is_documentation_path(match["path"]):
            yield _Found(match.start(), CitationKind.DOC_PATH, match["path"])


def _find_numbers(
    segment: str, repository: str, state: _RangeState
) -> Iterator[_Found]:
    """Yield the citations by number and by the folder prefix of a record."""
    for pattern, kind in (
        (_RECORD_LIST, CitationKind.RECORD_NUMBER),
        (_SPEC_LIST, CitationKind.SPEC_NUMBER),
    ):
        for match in pattern.finditer(segment):
            numbers = match["plural"] or match["singular"]
            yield from _expand_list(numbers, kind, match.start(), state)
    for match in _RECORD_PREFIX.finditer(segment):
        if _is_in_repository(match, repository):
            yield _Found(match.start(), CitationKind.RECORD_NUMBER, match["number"])


def _expand_list(
    numbers: str, kind: CitationKind, start: int, state: _RangeState
) -> Iterator[_Found]:
    """Yield every number that a list of numbers and ranges names.

    A range, joined by `to` or a dash, names each number from its start to its
    end, both ends included: `0007 to 0009` names 0007, 0008 and 0009. The
    numbers of one range share a range id. A chain of ranges, as in
    `0001 to 0003 to 0005`, is one range. A range whose two ends are equal names
    that number once, with no range id. In a range whose end is lower than its
    start, only the two ends are named, and the range itself is reported as
    `CitationKind.REVERSED_RANGE`. A range that does not fit in the budget of
    `state` names only its two ends, and is reported as
    `CitationKind.OVERSIZED_RANGE`.

    Args:
        numbers: The text of a list that `_PLURAL_LIST` or `_SINGULAR_LIST`
            matched. It holds a dash joiner only where its keyword allows one.
        kind: The kind of each number: a record or a spec.
        start: The position of the list keyword, for every citation.
        state: The budget of the file and its range ids. A range of N numbers
            uses N of the budget.

    Yields:
        A citation for each number, in the order of the list, and one with the
        kind `CitationKind.REVERSED_RANGE` or `CitationKind.OVERSIZED_RANGE`,
        valued `NNNN to MMMM`, for a range that is not expanded. A number that
        two ranges of a chain share is yielded once.
    """
    ends = list(_NUMBER_PATTERN.finditer(numbers))
    links = [
        _classify_link(numbers, before, after, state)
        for before, after in itertools.pairwise(ends)
    ]
    range_ids = _range_ids(links, state)
    for index, end in enumerate(ends):
        if index > 0:
            link, first = links[index - 1], ends[index - 1][0]
            yield from _unexpanded_or_between(
                link, first, end[0], kind, start, range_ids[index]
            )
            if link is _Link.SAME:
                continue
        yield _Found(start, kind, end[0], range_ids[index])


def _classify_link(
    numbers: str, before: re.Match[str], after: re.Match[str], state: _RangeState
) -> _Link:
    """Tell how the text between two neighbouring numbers of a list joins them.

    A range that fits uses its numbers from the budget of `state`.
    """
    if _RANGE_JOINER.fullmatch(numbers, before.end(), after.start()) is None:
        return _Link.NONE
    first, last = int(before[0]), int(after[0])
    if first == last:
        return _Link.SAME
    if first > last:
        return _Link.REVERSED
    if not state.take(last - first + 1):
        return _Link.OVERSIZED
    return _Link.RANGE


def _range_ids(links: Sequence[_Link], state: _RangeState) -> list[int | None]:
    """Return the range id of each number of a list, from the links between them.

    Args:
        links: The link after each number but the last.
        state: Gives the new ids.

    Returns:
        One entry for each number: the id of the range that the number is in,
        or `None`. Two links that share a number are one range.
    """
    ids: list[int | None] = [None] * (len(links) + 1)
    for index, link in enumerate(links):
        if link is _Link.RANGE:
            current = ids[index]
            ids[index] = ids[index + 1] = (
                state.new_range_id() if current is None else current
            )
    return ids


def _unexpanded_or_between(
    link: _Link,
    first: str,
    last: str,
    kind: CitationKind,
    start: int,
    range_id: int | None,
) -> Iterator[_Found]:
    """Yield what the link between two numbers adds besides the numbers.

    For a range, these are the numbers strictly between the ends. For a range
    that is not expanded, it is the finding. For no range, nothing.
    """
    if link is _Link.REVERSED:
        yield _Found(start, CitationKind.REVERSED_RANGE, f"{first} to {last}")
    elif link is _Link.OVERSIZED:
        yield _Found(start, CitationKind.OVERSIZED_RANGE, f"{first} to {last}")
    elif link is _Link.RANGE:
        for number in range(int(first) + 1, int(last)):
            yield _Found(start, kind, f"{number:04d}", range_id)


def _find_record_files(
    segment: str, citing: PurePosixPath, repository: str
) -> Iterator[_Found]:
    """Yield the citations of a record by its file name.

    A name after the record folder of this repository is a record citation in
    any file. A name with another path, or alone, is one only when the path
    leads from the citing file into the record folder.
    """
    for match in _FILE_IN_RECORDS_FOLDER.finditer(segment):
        if _is_in_repository(match, repository):
            yield _Found(match.start(), CitationKind.RECORD_FILE, match["name"])
    for match in _RELATIVE_FILE.finditer(segment):
        folder, name = match["folder"], match["name"]
        if folder.removeprefix("./") == _RECORDS_FOLDER:
            continue  # found above, with its folder
        if _leads_into_records_folder(citing, folder + name):
            yield _Found(match.start(), CitationKind.RECORD_FILE, name)


def _is_in_repository(match: re.Match[str], repository: str) -> bool:
    """Tell whether a match of `_RECORDS_FOLDER_START` is in `repository`.

    A path from the root is. A `github.com` address is when its owner and name
    equal `repository`, with any letter case: GitHub ignores the case.
    """
    owner = match["owner"]
    if owner is None:
        return True
    return f"{owner}/{match['repo']}".lower() == repository.lower()


def _leads_into_records_folder(citing: PurePosixPath, target: str) -> bool:
    """Tell whether the relative path `target` from `citing` is in the record folder.

    Args:
        citing: The path of the citing file relative to the checked root.
        target: A path as the text writes it, such as `../decisions/0007-x.md`.
    """
    joined = posixpath.normpath(posixpath.join(citing.parent.as_posix(), target))
    return posixpath.dirname(joined) == RECORDS_DIR


def _is_documentation_path(path: str) -> bool:
    """Tell whether a match of the documentation path pattern is a path to check.

    A path with the placeholder is a template. A record file under
    `docs/decisions/` is a record citation, which another pattern covers.
    """
    if _PLACEHOLDER in path:
        return False
    return not RECORD_NAME.match(path.removeprefix(_RECORDS_FOLDER))
