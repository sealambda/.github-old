"""The record folder: its layout, its numbers and the front matter of a record."""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from decisions.findings import Finding
from decisions.schemas import validate_document
from decisions.yamlio import describe_error, parse_yaml

RECORDS_DIR = "docs/decisions"
"""The folder of the records, relative to the checked root."""

LEDGER_NAME = "superseded.yaml"
"""File name of the ledger in the record folder."""

LEDGER_PATH = f"{RECORDS_DIR}/{LEDGER_NAME}"
"""The ledger, relative to the checked root."""

_README_NAME = "README.md"

RECORD_NAME = re.compile(
    r"""
    ^(?P<number>[0-9]{4})            # four digits
    -[a-z0-9]+(?:-[a-z0-9]+)*        # a dash and a slug with dashes
    \.md$
    """,
    re.VERBOSE,
)
"""The name of a record file. The group `number` holds its number."""

_FRONT_MATTER = re.compile(
    r"""
    \A---[ \t]*\r?\n                 # opening fence on the first line
    (?P<body>.*?)                    # the YAML text
    ^---[ \t]*\r?$                   # closing fence
    """,
    re.VERBOSE | re.DOTALL | re.MULTILINE,
)

_BYTE_ORDER_MARK = "\N{BYTE ORDER MARK}"

# A level-1 heading: at most three spaces of indent, `#`, a space, the title
# and an optional run of closing `#`. A line with four spaces is indented code.
_HEADING = re.compile(r"^ {0,3}# +(?P<title>\S.*?)(?: +#+)?[ \t]*$")

# The fences of a code block as CommonMark defines them. The info string of a
# backtick fence has no backtick: otherwise the line is inline code.
_OPENING_FENCE = re.compile(r"^ {0,3}(?P<marker>`{3,}|~{3,})(?P<info>.*)$")
_CLOSING_FENCE = re.compile(r"^ {0,3}(?P<marker>`{3,}|~{3,})[ \t]*$")


@dataclass(frozen=True)
class Record:
    """A record file in the record folder.

    Attributes:
        number: The four-digit number from the file name.
        name: The file name.
        path: The path relative to the checked root, with `/` separators.
    """

    number: str
    name: str
    path: str


def collect_records(
    files: Iterable[PurePosixPath],
) -> tuple[list[Record], list[Finding]]:
    """List the record files and report entries that do not belong in the folder.

    The folder holds only record files, `README.md` and the ledger. A missing
    folder is not a finding: a repository without records has nothing to check.

    The folder is read from a listing and not from the disk, so a file that
    Git ignores, such as `.DS_Store`, is not there. A folder is stray when the
    listing names a file below it; an empty folder is not listed.

    Args:
        files: The listing of the checked root that `walk.list_files` returns.

    Returns:
        The records, sorted by name, and a finding for each stray entry.
    """
    records: list[Record] = []
    findings: list[Finding] = []
    for name, is_folder in sorted(_entries_of_record_folder(files).items()):
        path = f"{RECORDS_DIR}/{name}"
        match = RECORD_NAME.match(name)
        if match and not is_folder:
            records.append(Record(match["number"], name, path))
        elif is_folder or name not in (_README_NAME, LEDGER_NAME):
            findings.append(Finding(path, 1, _stray_message(name, is_folder)))
    return records, findings


def _entries_of_record_folder(files: Iterable[PurePosixPath]) -> dict[str, bool]:
    """Return the entries directly in the record folder: name to "is a folder".

    An entry is a folder when the listing names a file below it.
    """
    folder_parts = PurePosixPath(RECORDS_DIR).parts
    entries: dict[str, bool] = {}
    for path in files:
        if path.parts[: len(folder_parts)] != folder_parts:
            continue
        below = path.parts[len(folder_parts) :]
        if below:
            name = below[0]
            entries[name] = entries.get(name, False) or len(below) > 1
    return entries


def _stray_message(name: str, is_folder: bool) -> str:
    """Say why the entry `name` does not belong in the record folder."""
    kind = "folder" if is_folder else "file"
    return (
        f"the {kind} {name} does not belong in {RECORDS_DIR}/: it holds "
        f"only NNNN-slug.md records, {_README_NAME} and {LEDGER_NAME}"
    )


def find_duplicate_numbers(records: list[Record]) -> list[Finding]:
    """Report each record whose number an earlier record already uses.

    Args:
        records: The records, sorted by name.

    Returns:
        A finding on every record after the first of its number.
    """
    first_by_number: dict[str, Record] = {}
    findings = []
    for record in records:
        first = first_by_number.setdefault(record.number, record)
        if first is not record:
            findings.append(
                Finding(
                    record.path,
                    1,
                    f"number {record.number} is also the number of {first.name}",
                )
            )
    return findings


def check_record(
    root: Path, record: Record, schema: Mapping[str, Any]
) -> list[Finding]:
    """Validate one record: its YAML front matter and its title.

    The file may start with a byte order mark and may use CRLF line ends.

    Args:
        root: The checked root.
        record: The record to read.
        schema: The JSON Schema of the front matter.

    Returns:
        The findings: an unreadable file, or missing or malformed front
        matter, or a schema violation, and a missing level-1 heading.
    """
    try:
        text = (root / record.path).read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return [Finding(record.path, 1, "the file is not valid UTF-8 text")]
    findings = _check_front_matter(record.path, text, schema)
    if record_title(text) is None:
        findings.append(
            Finding(
                record.path,
                1,
                "the record has no level-1 heading: put its title in a line "
                "that starts with `# ` after the front matter",
            )
        )
    return findings


def _check_front_matter(
    path: str, text: str, schema: Mapping[str, Any]
) -> list[Finding]:
    """Validate the YAML front matter at the start of `text`."""
    match = _FRONT_MATTER.match(text)
    if match is None:
        return [
            Finding(path, 1, "the file does not start with a YAML front matter block")
        ]
    # The block starts on line 2, after the opening fence.
    line_offset = 1
    try:
        document = parse_yaml(match["body"])
    except yaml.YAMLError as error:
        return [_yaml_finding(path, error, line_offset)]
    return validate_document(path, document, schema, line_offset)


def record_title(text: str) -> str | None:
    """Return the text of the first level-1 heading of a record.

    The search starts after the front matter. It skips fenced code blocks, so a
    `# comment` in an example is not a title. A fence closes with the same
    character as it opened and at least as many of them, as in CommonMark. A
    line with four spaces of indent is code, so it is not a heading. A closing
    `#` run in the heading is not part of the title.

    Args:
        text: The whole text of the record file.

    Returns:
        The title, or `None` when the record has no level-1 heading.
    """
    text = text.removeprefix(_BYTE_ORDER_MARK)
    front_matter = _FRONT_MATTER.match(text)
    body = text[front_matter.end() :] if front_matter else text
    fence: str | None = None
    for line in body.splitlines():
        if fence is not None:
            fence = None if _closes_fence(line, fence) else fence
        elif (opening := _opening_fence(line)) is not None:
            fence = opening
        elif heading := _HEADING.match(line):
            return heading["title"]
    return None


def _opening_fence(line: str) -> str | None:
    """Return the fence marker when `line` opens a fenced code block."""
    match = _OPENING_FENCE.match(line)
    if match is None:
        return None
    marker = match["marker"]
    if marker[0] == "`" and "`" in match["info"]:
        return None
    return marker


def _closes_fence(line: str, fence: str) -> bool:
    """Tell whether `line` closes a code block that `fence` opened."""
    match = _CLOSING_FENCE.match(line)
    if match is None:
        return False
    marker = match["marker"]
    return marker[0] == fence[0] and len(marker) >= len(fence)


def _yaml_finding(path: str, error: yaml.YAMLError, line_offset: int) -> Finding:
    """Turn a YAML syntax error into a finding at the line of the error."""
    line, problem = describe_error(error)
    return Finding(
        path, line_offset + line, f"the front matter is not valid YAML: {problem}"
    )
