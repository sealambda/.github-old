"""The patterns of the private facts that a public tree must not hold.

Each rule finds one kind of fact by its shape, never by its value: no rule
holds the name of a private repository, bucket, host or runner. The only names
in a rule come from the `Policy`, which lists what is public.

A rule reads the whole text of a file and yields each `Leak` with its offset,
so a rule can match across lines. The rules are deliberately broad: a match
that is not a private fact is fixed by rewording the text, and a fact that a
narrow rule misses is public for ever.

Every rule runs in time that grows in step with the size of the text, also on
one line of a million characters. A pattern that is anchored to a name has a
boundary to its left, a pattern that looks for a closing character has a
bound, and the code scans an expression with `str.find`, so no input makes a
rule rescan the rest of the line from each of its characters.

The flake check does not scan this file, because the patterns below contain
the prefixes that they search for.
"""

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class Policy:
    """What the organization allows a public tree to name.

    Attributes:
        organization: The GitHub login of the organization, in any letter
            case. It is also the first label of the organization's domains and
            the prefix of its resource names.
        public_repositories: The names of the repositories that a tree may
            name, in lower case.
        public_teams: The names of the teams that a tree may mention, in
            lower case.
    """

    organization: str
    public_repositories: frozenset[str]
    public_teams: frozenset[str]


@dataclass(frozen=True)
class Leak:
    """One match of a rule.

    Attributes:
        offset: The index of the first character of the match in the text.
        text: The matched text.
    """

    offset: int
    text: str


Finder = Callable[[str], Iterator[Leak]]
"""Reads the text of one file and yields each leak in it."""

Exemption = Callable[[re.Match[str]], bool]
"""Tells whether a match of a pattern names something public."""


@dataclass(frozen=True)
class Rule:
    """One kind of private fact.

    Attributes:
        name: The short name that a finding starts with.
        advice: What the fact is and how to fix the text, in one sentence.
        find: The function that yields the leaks of a text.
    """

    name: str
    advice: str
    find: Finder


# A name must not continue to the left or to the right of a match, so a rule
# reads whole tokens and never a part of a longer word or number.
_NO_NAME_BEFORE = r"(?<![A-Za-z0-9.-])"
_HOST_LABELS = r"(?:[A-Za-z0-9-]+\.)+"

# A percent-encoded byte before a name, such as the `%3A` of
# `q=repo%3A<organization>%2Fname`, delimits the name, as a colon or an equals
# sign does. The last hex digit of the byte is not a character of the name. A
# byte that encodes a character of a name (`%2D`, `%2E`, `%5F`, `%7E`) is part
# of a longer word, so it does not delimit. The slash `%2F` delimits a host
# name and the first label of a Pages address, and it does not delimit the
# organization in a repository name: `example%2F<organization>%2Fname` is the
# name of another owner, as in the plain form. The hex digits take any case.
_AFTER_ENCODED_BYTE = r"(?<=%[0-9A-Fa-f]{2})(?<!%2[DdEe])(?<!%5[Ff])(?<!%7[Ee])"
_AFTER_ENCODED_DELIMITER = _AFTER_ENCODED_BYTE + r"(?<!%2[Ff])"
# The start of a host name or of a first label: no name before it, or an
# encoded delimiter, with the slash included.
_HOST_START = r"(?:" + _NO_NAME_BEFORE + r"|" + _AFTER_ENCODED_BYTE + r")"

_AWS_ACCOUNT = (
    # Twelve digits, alone: `123456789012`.
    r"(?<![A-Za-z0-9])[0-9]{12}(?![A-Za-z0-9])",
    # The form of the console: `1234-5678-9012`.
    r"(?<![A-Za-z0-9-])[0-9]{4}-[0-9]{4}-[0-9]{4}(?![A-Za-z0-9-])",
)

# An ARN of any partition and service. A managed policy of AWS has the literal
# account `aws`: `arn:aws:iam::aws:policy/ReadOnlyAccess`. That ARN is public.
_ARN = re.compile(r"arn:aws[a-z-]*:[A-Za-z0-9:/._*-]*")
_ARN_ACCOUNT_FIELD = 4
_AWS_MANAGED_ACCOUNT = "aws"
# A service endpoint, a registry or a bucket address. The name of a service
# principal has one label before the domain: `sts.amazonaws.com`. That name is
# public, and a host with a region, an account or a bucket label is not. A
# path that starts with a name after the host is not public either: the
# path-style address of a bucket, `s3.amazonaws.com/<bucket>/key`, has one
# label and names a bucket. The slash may be escaped, as in JSON or in a URL.
_PATH_AFTER_HOST = re.compile(r"(?:/|\\/|%2[Ff])[A-Za-z0-9]")
_AWS_HOST = re.compile(
    _NO_NAME_BEFORE
    + r"(?P<labels>"
    + _HOST_LABELS
    + r")amazonaws\.com(?:\.cn)?(?![A-Za-z0-9-])"
)

# The value of a bucket key: the characters and the length of a bucket name,
# that is not a Terraform address (`var.name`), does not continue as one
# (`aws_s3_bucket.state.id`) or as a variable, and is not a flag value. A flag
# value is `true`, `false`, `null`, `none`, `yes`, `no`, `on` or `off` in any
# letter case, alone: `create_bucket = true` sets a switch and names no bucket.
# A dot ends the word when no name character follows it, as in the end of a
# sentence, so `true.` is a flag value and `true.example` is a name.
_BUCKET_VALUE = (
    r"(?!(?:var|local|module|data|each|path|self|count)\.)"
    r"(?!(?i:true|false|null|none|yes|no|on|off)(?![A-Za-z0-9_${-]|\.[A-Za-z0-9]))"
    r"[a-z0-9][a-z0-9.-]{2,}(?![A-Za-z0-9_.${-])"
)

# The key of a bucket value. The word `bucket` ends the key or is followed by
# the suffix `_name`, `-name` or `Name`. Word prefixes come before it, joined
# by `_` or `-` (`state_bucket`, `s3-cache-bucket_name`), or the word starts
# with a capital after a lower-case prefix (`stateBucket`, `stateBucketName`).
# The key starts at a token boundary, so the part of a longer word is not a
# key, and the prefix loop needs a separator in each step, so it has one way
# to split a token and reads it in time that grows in step with its length.
_BUCKET_KEY_START = r"(?<![A-Za-z0-9_.-])"
_BUCKET_KEY_WORD = (
    r"(?:(?:[A-Za-z0-9]+[_-])*(?i:bucket)|[A-Za-z0-9_-]*[a-z0-9]Bucket)"
    r"(?:[_-](?i:name)|Name)?"
)

_BUCKET = (
    # An address with the S3 scheme, as a Nix cache or a state backend has.
    r"s3://[A-Za-z0-9._/-]*",
    # The S3 interface and the public address of a Cloudflare R2 bucket.
    _NO_NAME_BEFORE + _HOST_LABELS + r"r2\.cloudflarestorage\.com(?![A-Za-z0-9-])",
    _NO_NAME_BEFORE + r"[A-Za-z0-9-]+\.r2\.dev(?![A-Za-z0-9-])",
    # The value of a bucket key, in the assignment form `bucket = "name"`, in
    # the mapping form `bucket_name: name` and in the flag form
    # `--bucket name`, quoted or not. A variable (`$NAME`, `${NAME}`) and an
    # expression (`${{ ... }}`) start with `$`, so they are not a name.
    _BUCKET_KEY_START
    + _BUCKET_KEY_WORD
    + r"[\"']?[ \t]*[:=][ \t]*[\"']?"
    + _BUCKET_VALUE,
    r"(?<![A-Za-z0-9-])--bucket(?:-name)?(?:=|[ \t]+)[\"']?" + _BUCKET_VALUE,
)

# The key of a runner. A comment starts after a blank, and a backquote closes a
# code span in a page: both end the labels.
_RUNS_ON_KEY = "runs-on:"
_VALUE_END = re.compile(r"[ \t]#|`")
_BLANKS = re.compile(r"[ \t\r]*")
_LABEL = re.compile(r"[A-Za-z0-9\x00][A-Za-z0-9._\x00-]*")
_QUOTED = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"")
# The text of an expression has no value in a file, so a placeholder stands in
# for it. A label that starts with a placeholder, as `${{ matrix.os }}-large`
# does, is the business of the expression. A hosted prefix with an expression
# after it, as `ubuntu-${{ matrix.version }}`, is hosted.
_PLACEHOLDER = "\x00"
# The shapes of the labels of the runners that GitHub hosts, from the tables
# "Standard GitHub-hosted runners" and "Larger runners" of
# https://docs.github.com/en/actions/reference/runners/github-hosted-runners
# and https://docs.github.com/en/actions/reference/runners/larger-runners
# (read on 2026-11-12). The patterns hold the shape of a version, never its
# value, so a new image needs no change: `ubuntu-NN.NN`, `windows-NNNN`,
# `windows-NN-arm`, `macos-NN` and `xcode-NN` stand for every version. A
# larger runner of the organization has a name that its owner chooses, so
# that name is not a hosted label. GitHub documents that labels are
# case-insensitive (the note of "Using labels with self-hosted runners",
# https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/apply-labels,
# read on 2026-11-12), so a hosted label has any letter case.
_HOSTED_LABEL = re.compile(
    r"ubuntu-(?:latest|slim|[0-9]{2}\.[0-9]{2}(?:-arm)?)"
    r"|windows-(?:latest|[0-9]{4}(?:-vs[0-9]{4})?|[0-9]{2}(?:-vs[0-9]{4})?-arm)"
    r"|macos-(?:latest(?:-large|-xlarge)?|[0-9]{2}(?:-intel|-large|-xlarge)?)"
    r"|xcode-[0-9]{2}(?:-xlarge)?",
    re.IGNORECASE,
)
# A hosted family prefix with an expression right after it, as in
# `ubuntu-${{ matrix.version }}` or `macos-${{ matrix.version }}-large`. The
# expression stands for the version, so only the parts of a hosted label may
# follow it: digits, dots, another expression, a dash before an expression and
# a documented suffix. The suffixes are the same for the three families.
_HOSTED_LABEL_WITH_EXPRESSION = re.compile(
    r"(?:ubuntu|windows|macos)-(?=[0-9.]*\x00)"
    r"(?:[0-9.]|\x00|-(?:arm|intel|large|xlarge|vs|(?=\x00)))+",
    re.IGNORECASE,
)
# A line below the key: a list item (`- label`), or the group or the labels of
# a runner mapping (`group: name`, `labels: [a, b]`).
_BLOCK_LINE = re.compile(r"[ \t]*(?:(?P<dash>-[ \t]+)|(?:group|labels)[ \t]*:[ \t]*)")
# A key without a value reads at most this many lines below it, and a flow
# list reads at most this many lines up to its closing bracket.
_MAX_BLOCK_LINES = 50
_MAX_FLOW_LINES = 20

_RUNNER_TYPE = (
    # A runner type of the form `<project>-<architecture>-<size>`. A package
    # name such as `@rollup/rollup-linux-x64-gnu` has the same form, so the
    # type does not start after `@` or `/`.
    r"(?<![A-Za-z0-9@/-])[a-z0-9][a-z0-9-]*-(?:x64|arm64)-[a-z0-9]+(?![A-Za-z0-9-])",
)
# `self-hosted` as an element of a list: after `[`, a comma or a quote, and
# before a comma, a quote or the closing bracket. A phrase in a link text,
# such as `[about self-hosted runners]`, is not an element.
_SELF_HOSTED_ELEMENT = re.compile(r"[\[,\"'][ \t]*self-hosted(?=[ \t]*[\",'\]])")
_LIST_REACH = 200

_OCTET = r"(?:\.[0-9]{1,3})"
_INTERNAL_HOST = (
    # A name under a suffix that only a private network resolves.
    _NO_NAME_BEFORE
    + _HOST_LABELS
    + r"(?:internal|local|lan|corp|intranet)(?![A-Za-z0-9-]|\.[A-Za-z0-9]|\()",
    # A machine name of a Tailscale network.
    _NO_NAME_BEFORE + _HOST_LABELS + r"ts\.net(?![A-Za-z0-9-])",
    # A private or carrier-grade IPv4 address (RFC 1918, RFC 6598).
    r"(?<![0-9.])(?:"
    + rf"10{_OCTET}{{3}}"
    + rf"|192\.168{_OCTET}{{2}}"
    + rf"|172\.(?:1[6-9]|2[0-9]|3[01]){_OCTET}{{2}}"
    + rf"|100\.(?:6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7]){_OCTET}{{2}}"
    + r")(?![0-9]|\.[0-9])",
)

_GITHUB_APP = (
    # The client identifier of a GitHub App, in its two formats.
    r"(?<![A-Za-z0-9])Iv1\.[0-9a-f]{16}(?![A-Za-z0-9])",
    r"(?<![A-Za-z0-9])Iv23[A-Za-z0-9]{16}(?![A-Za-z0-9])",
    # A numeric App, installation or client identifier next to its key.
    r"(?i)(?<![A-Za-z0-9])(?:app|installation|client)[-_ ]?id[\"'`]?"
    r"[ \t]*[:=][ \t]*[\"']?[0-9]{3,}",
    # The address of an installation in the settings pages.
    r"installations/[0-9]{3,}",
)
# The commit address of an App: `<identifier>+<slug>[bot]@...`. The three bot
# accounts that every repository has are public.
_BOT_ADDRESS = re.compile(
    r"(?<![0-9])[0-9]+\+(?P<slug>[A-Za-z0-9-]+)\[bot\]@users\.noreply\.github\.com"
)
_PUBLIC_BOT_SLUGS = frozenset({"github-actions", "renovate", "dependabot"})

# What can come before the name of the organization in a repository name:
# - an address with a host name and a slash, a colon or a port, so that a
#   forge, a registry and a raw-content host are read in the same way;
# - the API path, with or without its first slash;
# - the mention of a team;
# - a path that starts with a slash, as in `see /<organization>/<name>`;
# - nothing, in the short form, but not after a character of a name or of a
#   path, so that a folder with the name of the organization is not read. A
#   percent-encoded delimiter, as the `%3A` of `repo%3A<organization>/name`,
#   is not a character of a name, so it may come before the name.
_REPOSITORY_PREFIX = (
    r"(?:(?P<address>"
    + _HOST_START
    + _HOST_LABELS
    + r"[A-Za-z]{2,}(?::[0-9]+)?[/:]"
    + r"|/repos/|(?:(?<![A-Za-z0-9._/-])|"
    + _AFTER_ENCODED_DELIMITER
    + r")repos/)"
    + r"|(?P<team>@)"
    + r"|(?:(?<![A-Za-z0-9_.@~/-])|"
    + _AFTER_ENCODED_DELIMITER
    + r")/"
    + r"|(?:(?<![A-Za-z0-9_./@-])|"
    + _AFTER_ENCODED_DELIMITER
    + r"))"
)

# The slash of an escaped address: `\/` in JSON and `%2F` or `%2f` in a URL. A
# name has the same prefixes as above, with this slash in the place of `/`:
# - a host name, the API path or the mention of a team before the slash;
# - a slash that starts a path, or nothing, at the start of a token;
# - the end of another escaped slash, as in `https:\/\/github.com\/<name>`.
# A name does not follow a character of a path or the name of another owner,
# so `example\/<organization>\/name` is not a repository, as in the plain form.
_ESCAPED_SLASH = r"(?:\\/|%2[Ff])"
_NO_ESCAPED_NAME_BEFORE = r"(?<![A-Za-z0-9._@~/\\-])(?<!%2[Ff])"
_ESCAPED_NAME_START = (
    r"(?:" + _NO_ESCAPED_NAME_BEFORE + r"|" + _AFTER_ENCODED_DELIMITER + r")"
)
_ESCAPED_REPOSITORY_PREFIX = (
    r"(?:(?:(?<![A-Za-z0-9.%-])|"
    + _AFTER_ENCODED_BYTE
    + r")"
    + _HOST_LABELS
    + r"[A-Za-z]{2,}(?::[0-9]+)?"
    + _ESCAPED_SLASH
    + r"|(?:"
    + _ESCAPED_NAME_START
    + r"|(?<=\\/)|"
    + _AFTER_ENCODED_BYTE
    + r")repos"
    + _ESCAPED_SLASH
    + r"|(?P<team>@)"
    + r"|"
    + _ESCAPED_NAME_START
    + _ESCAPED_SLASH
    + r"|"
    + _ESCAPED_NAME_START
    + r")"
)

# The address of a GitHub Pages site: `<organization>.github.io/<name>`, also
# with the escaped slash of JSON or of a URL after `.github.io`. The
# organization is the first label, so no name comes before it. The label may
# follow a slash that is encoded, as in `https%3A%2F%2F<organization>.github.io`.
_PAGES_SEPARATOR = r"(?i:\.github\.io)(?:/|" + _ESCAPED_SLASH + r")"
_NAME = r"(?P<name>[A-Za-z0-9._-]+)"

# The address of a team: `orgs/<organization>/teams/<team>`, in the web
# address of the team and in the path of the API, with a plain or an escaped
# slash. The word `orgs` starts a token, or it follows an escaped slash.
_TEAM_PATH_START = r"(?:(?<![A-Za-z0-9._-])|(?<=%2[Ff]))orgs"


def _pattern_finder(*patterns: str) -> Finder:
    """Build a finder that yields every match of every pattern.

    Args:
        *patterns: Regular expressions. The whole match is the leak.
    """
    compiled = [re.compile(pattern) for pattern in patterns]

    def find(text: str) -> Iterator[Leak]:
        """Yield the matches of every pattern, pattern by pattern."""
        for pattern in compiled:
            for match in pattern.finditer(text):
                yield Leak(match.start(), match.group(0))

    return find


def _match_finder(pattern: re.Pattern[str], exempt: Exemption) -> Finder:
    """Build a finder that yields the matches that are not public.

    Args:
        pattern: The regular expression. The whole match is the leak.
        exempt: Tells whether a match names something public.
    """

    def find(text: str) -> Iterator[Leak]:
        """Yield each match of the pattern that `exempt` does not accept."""
        for match in pattern.finditer(text):
            if not exempt(match):
                yield Leak(match.start(), match.group(0))

    return find


def _is_managed_policy_arn(match: re.Match[str]) -> bool:
    """Tell whether an ARN has the literal account `aws` of a managed policy."""
    fields = match.group(0).split(":", _ARN_ACCOUNT_FIELD + 1)
    return len(fields) > _ARN_ACCOUNT_FIELD and (
        fields[_ARN_ACCOUNT_FIELD] == _AWS_MANAGED_ACCOUNT
    )


def _is_service_principal(match: re.Match[str]) -> bool:
    """Tell whether an AWS host names a service and not a resource.

    A service has exactly one label before the domain and no path that starts
    with a name after the host. A path after one label is the path-style
    address of a bucket.
    """
    if match["labels"].count(".") != 1:
        return False
    return _PATH_AFTER_HOST.match(match.string, match.end()) is None


def _is_public_bot(match: re.Match[str]) -> bool:
    """Tell whether a bot address belongs to one of the three public bots."""
    return match["slug"].lower() in _PUBLIC_BOT_SLUGS


def _expression_spans(text: str) -> list[tuple[int, int]]:
    """Return the start and the end of each closed `${{ ... }}` in a text.

    A `${{` with no `}}` after it ends the search: no later `${{` can close
    either. This keeps the scan linear on a line with many unclosed openings,
    which a lazy pattern would rescan from each of them.

    Args:
        text: One value or one line.
    """
    spans = []
    position = 0
    while (start := text.find("${{", position)) != -1:
        close = text.find("}}", start + 3)
        if close == -1:
            break
        spans.append((start, close + 2))
        position = close + 2
    return spans


def _mask_spans(text: str, spans: list[tuple[int, int]]) -> str:
    """Return a text of the same length with a placeholder in each span.

    Args:
        text: The text.
        spans: The ordered, disjoint `(start, end)` pairs to hide.
    """
    parts = []
    cursor = 0
    for start, end in spans:
        parts.append(text[cursor:start])
        parts.append(_PLACEHOLDER * (end - start))
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)


def _is_hosted_label(label: str) -> bool:
    """Tell whether a label has the shape of a label of a hosted runner.

    Args:
        label: One token of a `runs-on` value, with a placeholder in the place
            of each expression.
    """
    return bool(
        _HOSTED_LABEL.fullmatch(label) or _HOSTED_LABEL_WITH_EXPRESSION.fullmatch(label)
    )


def _label_tokens(masked: str, shown: str, offset: int) -> Iterator[Leak]:
    """Yield the tokens of a masked text that are not labels of hosted runners.

    A token that starts with a placeholder is skipped: an expression decides
    it. The leak shows the token of `shown`, so it holds the expression text.

    Args:
        masked: The text with a placeholder for each expression.
        shown: The text of the same length without the placeholders.
        offset: The index of the text in the file.
    """
    for token in _LABEL.finditer(masked):
        label = token.group(0)
        if label[0] != _PLACEHOLDER and not _is_hosted_label(label):
            yield Leak(offset + token.start(), shown[token.start() : token.end()])


def _expression_labels(expression: str, offset: int) -> Iterator[Leak]:
    """Yield the labels in the quoted literals of one expression.

    The literals of `${{ c && 'ubuntu-latest' || 'self-hosted' }}` are runner
    labels, and the words outside the literals are names of the expression.

    Args:
        expression: The text of one `${{ ... }}`.
        offset: The index of the expression in the file.
    """
    for literal in _QUOTED.finditer(expression):
        start = literal.start() + 1
        content = literal.group(0)[1:-1]
        yield from _label_tokens(content, content, offset + start)


def _visible_end(line: str, start: int = 0) -> int:
    """Return the index where the labels of a line end.

    The labels end at a comment or at a backquote. A comment starts with a `#`
    after a blank, or with a `#` at `start`. The search starts at an index and
    does not copy the rest of the line, because a line can be long.

    Args:
        line: One line of a file.
        start: The index where the value starts.
    """
    if line.startswith("#", start):
        return start
    end = _VALUE_END.search(line, start)
    return end.start() if end else len(line)


def _labels(value: str, offset: int) -> Iterator[Leak]:
    """Yield the runner labels of one `runs-on` value that are not hosted.

    An expression such as `${{ matrix.os }}` is not a label: its value is not
    in the file. The quoted literals inside an expression are labels. The
    labels of the runners that GitHub hosts are public, also with an
    expression after the prefix, as in `ubuntu-${{ matrix.version }}`.

    Args:
        value: The text of one value or one list item, up to its comment.
        offset: The index of `value` in the text of the file.
    """
    spans = _expression_spans(value)
    for start, end in spans:
        yield from _expression_labels(value[start:end], offset + start)
    yield from _label_tokens(_mask_spans(value, spans), value, offset)


def _opens_flow_list(value: str) -> bool:
    """Tell whether a value has a `[` with no `]` after it."""
    return value.rfind("[") > value.rfind("]")


def _flow_continuation(lines: list[tuple[int, str]], index: int) -> Iterator[Leak]:
    """Yield the labels of the lines that continue a flow list.

    The list continues on the lines below the line `index`, up to the first
    line with a `]`. The text after that bracket is not a label. A line with
    another `runs-on:` key ends the list, because the next key reads it.

    Args:
        lines: The offset and the text of each line of the file.
        index: The index of the line that opens the list.
    """
    for offset, line in lines[index + 1 : index + 1 + _MAX_FLOW_LINES]:
        if _RUNS_ON_KEY in line:
            return
        visible = line[: _visible_end(line)]
        close = visible.find("]")
        yield from _labels(visible if close == -1 else visible[:close], offset)
        if close != -1:
            return


def _value_labels(
    lines: list[tuple[int, str]], index: int, column: int
) -> Iterator[Leak]:
    """Yield the labels of the value that starts at a column of a line.

    Args:
        lines: The offset and the text of each line of the file.
        index: The index of the line with the value.
        column: The index of the first character of the value in the line.
    """
    offset, line = lines[index]
    value = line[column : _visible_end(line, column)]
    yield from _labels(value, offset + column)
    if _opens_flow_list(value):
        yield from _flow_continuation(lines, index)


def _block_labels(lines: list[tuple[int, str]], index: int) -> Iterator[Leak]:
    """Yield the labels below a `runs-on` key that has no value on its line.

    The lines below the key are list items and the `group` and `labels` of a
    runner mapping, as long as they are indented deeper than the key. A list
    item may also have the indentation of the key. Any other deeper line, such
    as the `description` of a workflow input, holds no label.

    Args:
        lines: The offset and the text of each line of the file.
        index: The index of the line with the key.
    """
    indent = _indent(lines[index][1])
    last = min(len(lines), index + 1 + _MAX_BLOCK_LINES)
    for position in range(index + 1, last):
        line = lines[position][1]
        if not line.strip(" \t\r") or line.lstrip(" \t").startswith("#"):
            continue
        item = _BLOCK_LINE.match(line)
        depth = _indent(line)
        is_item = item is not None and item["dash"] is not None
        if depth < indent or (depth == indent and not is_item):
            return
        if item is not None:
            yield from _value_labels(lines, position, item.end())


def _skip_blanks(line: str, start: int = 0) -> int:
    """Return the index of the first character from `start` that is not blank.

    A blank is a space, a tab or the carriage return of a CRLF line end. The
    search does not copy the rest of the line, because a line can be long.

    Args:
        line: One line of a file.
        start: The index where the search starts.
    """
    match = _BLANKS.match(line, start)
    return match.end() if match else start


def _indent(line: str) -> int:
    """Return the number of spaces and tabs that start a line."""
    return _skip_blanks(line)


def _runs_on_labels(
    lines: list[tuple[int, str]], index: int, column: int
) -> Iterator[Leak]:
    """Yield the labels of the `runs-on` key that ends at a column of a line.

    Args:
        lines: The offset and the text of each line of the file.
        index: The index of the line with the key.
        column: The index of the first character after `runs-on:`.
    """
    line = lines[index][1]
    start = _skip_blanks(line, column)
    if start == len(line) or line[start] == "#":
        yield from _block_labels(lines, index)
    else:
        yield from _value_labels(lines, index, start)


def _find_runs_on_labels(text: str) -> Iterator[Leak]:
    """Yield each label of a `runs-on` key that names a self-hosted runner.

    The key takes its labels from the same line, as a word, a YAML list, a
    JSON list or an expression, from a flow list that goes on over several
    lines, from the list items below it, or from the `group` and the `labels`
    of a mapping below it. A line ends with LF or with CRLF.
    """
    if _RUNS_ON_KEY not in text:
        return
    lines = []
    offset = 0
    for line in text.split("\n"):
        lines.append((offset, line))
        offset += len(line) + 1
    for index, (_, line) in enumerate(lines):
        position = line.find(_RUNS_ON_KEY)
        while position != -1:
            column = position + len(_RUNS_ON_KEY)
            yield from _runs_on_labels(lines, index, column)
            # The next key is after the value of this one, so that no text is
            # read twice.
            position = line.find(_RUNS_ON_KEY, _visible_end(line, column))


def _find_self_hosted_lists(text: str) -> Iterator[Leak]:
    """Yield each bracketed list that has `self-hosted` as an element.

    The list is the text from the nearest `[` before the element to the first
    `]` after it, and each side reaches at most `_LIST_REACH` characters on
    the same line. A list with several such elements is one leak.
    """
    last_start = -1
    for element in _SELF_HOSTED_ELEMENT.finditer(text):
        window_start = max(0, element.start() - _LIST_REACH)
        start = text.rfind("[", window_start, element.start() + 1)
        end = text.find("]", element.end(), element.end() + _LIST_REACH)
        if start in (-1, last_start) or end == -1:
            continue
        if "]" in text[start : element.start()] or "\n" in text[start:end]:
            continue
        last_start = start
        yield Leak(start, text[start : end + 1])


def _organization_host_finder(organization: str) -> Finder:
    """Build a finder of host names below a domain of the organization.

    A domain of the organization has the organization name as its first label,
    whatever the top-level domain. Every name below it is a leak, except the
    public `www` site.

    Args:
        organization: The name of the organization.
    """
    pattern = re.compile(
        _NO_NAME_BEFORE
        + r"(?P<labels>"
        + _HOST_LABELS
        + r")(?i:"
        + re.escape(organization)
        + r")\.[A-Za-z]{2,}(?![A-Za-z0-9-])"
    )

    def find(text: str) -> Iterator[Leak]:
        """Yield each host name of the organization except the `www` site."""
        for match in pattern.finditer(text):
            if match["labels"].lower() != "www.":
                yield Leak(match.start(), match.group(0))

    return find


def _organization_name_finder(organization: str) -> Finder:
    """Build a finder of resource names that start with the organization name.

    Buckets, GitHub Apps and cloud profiles carry the lower-case name of the
    organization and a dash as a prefix.

    Args:
        organization: The name of the organization.
    """
    return _pattern_finder(
        r"(?<![A-Za-z0-9-])"
        + re.escape(organization.lower())
        + r"-[a-z0-9][a-z0-9-]*(?![A-Za-z0-9-])"
    )


def _team_path_pattern(organization: str, slash: str) -> re.Pattern[str]:
    """Compile the pattern of the address of a team of the organization.

    Args:
        organization: The pattern of the name of the organization.
        slash: The pattern of the slash: a plain or an escaped one.
    """
    return re.compile(
        _TEAM_PATH_START + slash + organization + slash + "teams" + slash + _NAME
    )


def _repository_finder(policy: Policy) -> Finder:
    """Build a finder of repository and team names that are not public.

    The finder reads the name of the organization in any letter case after
    one of these prefixes: a host name and a slash, a colon or a port (the
    address of GitHub, of its raw-content hosts, of its registry and of any
    other forge), the path of the API with or without its first slash, the
    flake form `github:`, a path that starts with a slash at a word boundary,
    the mention of a team `@<organization>/<team>`, or nothing, in the short
    form `<organization>/<name>`. The short form does not follow a character
    of a path: a folder with the name of the organization, such as
    `styles/<Organization>/rule.yml`, and the name of another owner, such as
    `example/<organization>/name`, are not a repository.

    The finder also reads the escaped slash of JSON (a backslash before the
    slash) and of a URL (`%2F`, in any letter case of the hex) in the place of
    each slash, with the same prefixes, and the address of a GitHub Pages
    site (`<organization>.github.io/<name>`, also with an escaped slash). A
    percent-encoded delimiter may come before the organization, as in
    `q=repo%3A<organization>%2F<name>`: any encoded byte except `%2D`, `%2E`,
    `%5F`, `%7E` and `%2F` is one.

    The address of a team, `orgs/<organization>/teams/<team>`, with a plain or
    an escaped slash and with any host or none, names a team: the finder
    compares its name with the public teams.

    Args:
        policy: The organization and the names that are public.
    """
    organization = r"(?i:" + re.escape(policy.organization) + r")"
    patterns = [
        (re.compile(_REPOSITORY_PREFIX + organization + "/" + _NAME), False),
        (
            re.compile(
                _ESCAPED_REPOSITORY_PREFIX + organization + _ESCAPED_SLASH + _NAME
            ),
            False,
        ),
        (re.compile(_HOST_START + organization + _PAGES_SEPARATOR + _NAME), False),
        (_team_path_pattern(organization, "/"), True),
        (_team_path_pattern(organization, _ESCAPED_SLASH), True),
    ]

    def find(text: str) -> Iterator[Leak]:
        """Yield each repository or team name that is not on the public list."""
        for pattern, is_team_path in patterns:
            for match in pattern.finditer(text):
                name = match["name"].rstrip(".").removesuffix(".git").lower()
                is_team = is_team_path or bool(match.groupdict().get("team"))
                public = policy.public_teams if is_team else policy.public_repositories
                if name not in public:
                    yield Leak(match.start(), match.group(0))

    return find


def _chain(*finders: Finder) -> Finder:
    """Build a finder that yields the leaks of each finder in turn."""

    def find(text: str) -> Iterator[Leak]:
        """Yield the leaks of each finder in turn."""
        for finder in finders:
            yield from finder(text)

    return find


def build_rules(policy: Policy) -> tuple[Rule, ...]:
    """Return the rules for one organization.

    Args:
        policy: The organization and the names that are public.
    """
    return (
        Rule(
            "aws-account",
            "A 12-digit number reads as an AWS account identifier. Remove it.",
            _pattern_finder(*_AWS_ACCOUNT),
        ),
        Rule(
            "aws-resource",
            "An ARN or an AWS endpoint names a private resource. Remove it.",
            _chain(
                _match_finder(_ARN, _is_managed_policy_arn),
                _match_finder(_AWS_HOST, _is_service_principal),
            ),
        ),
        Rule(
            "bucket",
            "A bucket address, the value of a bucket key or a resource name "
            "with the organization prefix is private. Describe the resource "
            "without its name.",
            _chain(
                _pattern_finder(*_BUCKET),
                _organization_name_finder(policy.organization),
            ),
        ),
        Rule(
            "runner-label",
            "A label of a self-hosted runner is private. Use a label of a "
            "hosted runner or an expression.",
            _chain(
                _find_runs_on_labels,
                _find_self_hosted_lists,
                _pattern_finder(*_RUNNER_TYPE),
            ),
        ),
        Rule(
            "internal-host",
            "An internal host name or a private address is private. Remove it.",
            _chain(
                _pattern_finder(*_INTERNAL_HOST),
                _organization_host_finder(policy.organization),
            ),
        ),
        Rule(
            "github-app",
            "A GitHub App identifier is private. Remove it.",
            _chain(
                _pattern_finder(*_GITHUB_APP),
                _match_finder(_BOT_ADDRESS, _is_public_bot),
            ),
        ),
        Rule(
            "repository",
            "A repository or a team that is not on the public list. Describe "
            "it without its name.",
            _repository_finder(policy),
        ),
    )
