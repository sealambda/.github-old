"""Edit the text of the ledger without re-dumping it.

A re-dump through a YAML library rewrites quotes, spacing and comments, and a
reviewer then sees a diff of lines that nobody changed. These functions append
text and change single lines instead, so every other byte of the ledger stays.
The caller validates the result.
"""

import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from decisions.yamlio import line_of, parse_yaml

LEDGER_HEADER = (
    "# Decision records that a pull request deleted. `decisions retire` adds an\n"
    "# entry. The format is in docs/reference/decision-records.md of the hub:\n"
    "# https://github.com/sealambda/.github\n"
)
"""The comment at the top of a ledger that `decisions retire` creates."""

_NEW_FILE_MODE = 0o644

_EMPTY_LIST_LINE = re.compile(r"^\[[ \t]*\][ \t]*(?:#.*)?(?:\r?\n|\Z)", re.MULTILINE)
"""A line that holds the empty list `[]`, the ledger of a repository with no
deleted record. An entry cannot follow it, so `append_entry` removes it."""


class LedgerEditError(Exception):
    """The ledger text has a shape that these edits cannot change safely."""


@dataclass(frozen=True)
class NewEntry:
    """The ledger entry of a record that is being retired.

    Attributes:
        number: The four-digit number of the record.
        title: The title of the record at its last text.
        commit: The full hash of the last commit that holds the text.
        path: The path of the record in that commit.
        successor: The number of the replacing record, `None` when withdrawn.
        date: The day of the retirement, as `YYYY-MM-DD`.
    """

    number: str
    title: str
    commit: str
    path: str
    successor: str | None
    date: str


def format_entry(entry: NewEntry) -> str:
    """Return the YAML text of one entry, with a final newline.

    The fields follow the order of the reference page. PyYAML writes the
    title, so that a colon or a leading symbol gets the quotes that it needs.
    """
    title = yaml.safe_dump(
        {"title": entry.title}, allow_unicode=True, width=2**31 - 1
    ).rstrip("\n")
    lines = [f'- number: "{entry.number}"', f"  {title}"]
    lines.append(f"  commit: {entry.commit}")
    lines.append(f"  path: {entry.path}")
    if entry.successor is not None:
        lines.append(f'  successor: "{entry.successor}"')
    lines.append(f"  date: {entry.date}")
    return "\n".join(lines) + "\n"


def append_entry(text: str | None, entry: NewEntry) -> str:
    """Return the ledger text with `entry` after the last line.

    A line that holds only the empty list `[]` is removed first: it is the
    ledger of a repository with no deleted record.

    Args:
        text: The current ledger text, or `None` when the file does not exist.
            A new ledger starts with `LEDGER_HEADER`.
        entry: The entry to add.
    """
    if text is None:
        return LEDGER_HEADER + format_entry(entry)
    text = _EMPTY_LIST_LINE.sub("", text, count=1)
    separator = "" if text == "" or text.endswith("\n") else "\n"
    return text + separator + format_entry(entry)


def rewrite_successors(text: str, old: str, new: str) -> tuple[str, list[str]]:
    """Point every entry whose successor is `old` to `new`.

    Only the number inside the `successor` line changes: its quotes, its
    indentation and a trailing comment stay.

    Args:
        text: The ledger text.
        old: The number that entries name as their successor.
        new: The number that they name afterwards.

    Returns:
        The new text and the numbers of the entries that changed, in file order.

    Raises:
        LedgerEditError: The text is not a YAML list of mappings, or a
            `successor` is not on a line of the form `successor: "NNNN"`.
        yaml.YAMLError: The text is not valid YAML.
    """
    document = parse_yaml(text)
    items = document.data if isinstance(document.data, list) else []
    lines = text.splitlines(keepends=True)
    changed = []
    for index, item in enumerate(items):
        if not (isinstance(item, dict) and item.get("successor") == old):
            continue
        line_number = line_of(document.root, [index, "successor"]) - 1
        lines[line_number] = _rewrite_line(lines[line_number], old, new)
        changed.append(str(item.get("number")))
    return "".join(lines), changed


def _rewrite_line(line: str, old: str, new: str) -> str:
    """Replace the number on one `successor:` line, or raise `LedgerEditError`."""
    body = line.rstrip("\r\n")
    ending = line[len(body) :]
    pattern = re.compile(
        r"^(?P<head>\s*(?:-\s+)?successor:\s*)(?P<quote>[\"']?)"
        + re.escape(old)
        + r"(?P=quote)(?P<tail>\s*(?:#.*)?)$"
    )
    match = pattern.match(body)
    if match is None:
        raise LedgerEditError(
            f"cannot rewrite the successor {old} on this line of the ledger: "
            f"{body.strip()!r}; change it by hand to {new}"
        )
    quote = match["quote"]
    return f"{match['head']}{quote}{new}{quote}{match['tail']}{ending}"


def write_text_atomically(path: Path, text: str) -> None:
    """Write `text` to `path` through a temporary file and a rename.

    A reader sees the old file or the new one, never half of it. The new file
    keeps the permission bits of the old one, or gets `0644` when it is new.
    The temporary file lives in the same folder, so the rename stays on one
    file system.

    Raises:
        OSError: The write or the rename failed. The temporary file is removed
            and `path` is unchanged.
    """
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else _NEW_FILE_MODE
    handle, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=".ledger-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
        os.chmod(temporary_name, mode)
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
