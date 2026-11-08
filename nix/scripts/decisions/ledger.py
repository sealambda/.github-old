"""The ledger of deleted records: loading, schema validation and its rules."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from decisions.findings import Finding
from decisions.records import LEDGER_PATH, Record
from decisions.schemas import validate_document
from decisions.yamlio import YamlDocument, describe_error, line_of, parse_yaml

# The shape of the file name of a ledger `path`, as `schemas/superseded.schema.json`
# requires it: four digits, a dash, a slug and `.md`. The slug is free there, for
# the records of other repositories had other slug rules.
_RECORD_FILE_NAME = re.compile(r"[0-9]{4}-[^/\n]+\.md")


@dataclass(frozen=True)
class LedgerEntry:
    """The part of a ledger entry that the rules read.

    Attributes:
        number: The number of the deleted record.
        successor: The number of the record that replaced it, or `None` for a
            withdrawn record.
        line: The line of the entry in the ledger.
        path: The `path` of the entry, or `None` when it is not a string.
        path_line: The line of the `path` key, or the line of the entry when
            the key is missing.
    """

    number: str
    successor: str | None
    line: int
    path: str | None = None
    path_line: int = 0


def load_ledger(
    root: Path, schema: Mapping[str, Any]
) -> tuple[list[LedgerEntry], list[Finding]]:
    """Read the ledger and validate it against its schema.

    A missing ledger is not a finding: the first deletion creates it. Entries
    that break the schema in some field still count as entries, when their
    `number` is readable, so that the other rules report in the same run.

    Args:
        root: The checked root.
        schema: The JSON Schema of the ledger.

    Returns:
        The entries and the findings of the schema validation.
    """
    ledger_file = root / LEDGER_PATH
    if not ledger_file.is_file():
        return [], []
    try:
        document = parse_yaml(ledger_file.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return [], [Finding(LEDGER_PATH, 1, "the file is not valid UTF-8 text")]
    except yaml.YAMLError as error:
        line, problem = describe_error(error)
        message = f"the ledger is not valid YAML: {problem}"
        return [], [Finding(LEDGER_PATH, line, message)]
    findings = validate_document(LEDGER_PATH, document, schema)
    return _entries(document), findings


def _entries(document: YamlDocument) -> list[LedgerEntry]:
    """Build an entry for each list item that has a readable number."""
    if not isinstance(document.data, list):
        return []
    entries = []
    for index, item in enumerate(document.data):
        if isinstance(item, dict) and isinstance(item.get("number"), str):
            successor = item.get("successor")
            path = item.get("path")
            entries.append(
                LedgerEntry(
                    number=item["number"],
                    successor=successor if isinstance(successor, str) else None,
                    line=line_of(document.root, [index]),
                    path=path if isinstance(path, str) else None,
                    path_line=line_of(document.root, [index, "path"]),
                )
            )
    return entries


def check_entries(
    entries: Sequence[LedgerEntry], records: Sequence[Record]
) -> list[Finding]:
    """Check the rules that link the ledger to the record folder.

    The rules: a number appears once, no record file has a number of the
    ledger, a successor is a record that exists, and the file name of the
    `path` starts with the number of its entry.

    Args:
        entries: The ledger entries, in file order.
        records: The record files.

    Returns:
        The findings, each on the line of its entry, or of its `path`.
    """
    record_numbers = {record.number for record in records}
    seen: set[str] = set()
    findings = []
    for entry in entries:
        findings.extend(_check_entry(entry, record_numbers, seen))
        seen.add(entry.number)
    return findings


def _check_entry(
    entry: LedgerEntry, record_numbers: set[str], seen: set[str]
) -> list[Finding]:
    """Check one entry against the numbers that exist and the earlier entries."""
    findings = []
    if entry.number in seen:
        findings.append(_finding(entry, f"number {entry.number} is listed twice"))
    if entry.number in record_numbers:
        findings.append(
            _finding(
                entry,
                f"number {entry.number} is in the ledger and has a record file: "
                "a deleted record has no file",
            )
        )
    if entry.successor is not None and entry.successor not in record_numbers:
        findings.append(
            _finding(
                entry,
                f"the successor {entry.successor} of {entry.number} "
                "is not a record in force",
            )
        )
    findings.extend(_check_path(entry))
    return findings


def _check_path(entry: LedgerEntry) -> list[Finding]:
    """Check that the file name of the `path` starts with the number of the entry.

    The folder can be any: a record may have been published under another
    folder name. A file name that starts with another number would make a
    permalink that shows another record. The schema already reports a path
    whose file name is not `NNNN-slug.md`, so only a name of that shape is
    compared with the number here.
    """
    if entry.path is None:
        return []
    name = PurePosixPath(entry.path).name
    if _RECORD_FILE_NAME.fullmatch(name) is None:
        return []
    if name.startswith(f"{entry.number}-"):
        return []
    message = (
        f"the file name of the path {entry.path} must start with "
        f"{entry.number}- and end in .md"
    )
    return [Finding(LEDGER_PATH, entry.path_line, message)]


def _finding(entry: LedgerEntry, message: str) -> Finding:
    """Build a finding on the line of `entry` in the ledger."""
    return Finding(LEDGER_PATH, entry.line, message)
