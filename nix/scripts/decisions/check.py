"""Run every check on a tree and return the findings.

The checks are, in order: the layout of the record folder, the numbers, the
front matter of each record, the ledger, and the citations in every text file.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from decisions.citations import (
    MAX_RANGE_NUMBERS,
    PROSE_SUFFIXES,
    Citation,
    CitationKind,
    scan_text,
)
from decisions.findings import Finding
from decisions.ledger import LedgerEntry, check_entries, load_ledger
from decisions.records import (
    LEDGER_PATH,
    RECORD_NAME,
    RECORDS_DIR,
    Record,
    check_record,
    collect_records,
    find_duplicate_numbers,
)
from decisions.schemas import LEDGER_SCHEMA, RECORD_SCHEMA, load_schema
from decisions.walk import iter_candidate_files, list_files, read_text_file

_SPECS_DIR = "docs/specs"

_SPEC_NAME = re.compile(r"^(?P<number>[0-9]{4})-.+\.md$")
"""The name of a spec file. The group `number` holds its number."""


@dataclass(frozen=True)
class Catalog:
    """What exists in the checked tree, for resolving citations.

    Attributes:
        root: The checked root.
        records: The record files by number. For a number that two files share,
            the first by name.
        record_names: The names of all record files.
        ledger: The ledger entries by number.
        spec_numbers: The numbers of the files `docs/specs/NNNN-*.md`.
        files: The paths of the listing of the root, as POSIX text. A cited
            page exists when its path is in this set, compared letter case
            for letter case.
    """

    root: Path
    records: Mapping[str, Record]
    record_names: frozenset[str]
    ledger: Mapping[str, LedgerEntry]
    spec_numbers: frozenset[str]
    files: frozenset[str]

    def may_cite_deleted(self, citing_path: str, number: str) -> bool:
        """Tell whether `citing_path` may cite the deleted record `number`.

        Only the successor of a deleted record may cite it, besides the ledger.

        Args:
            citing_path: The file that holds the citation, relative to the root.
            number: The number of a record in the ledger.
        """
        successor = self.ledger[number].successor
        citing = PurePosixPath(citing_path)
        if successor is None or citing.parent.as_posix() != RECORDS_DIR:
            return False
        match = RECORD_NAME.match(citing.name)
        return match is not None and match["number"] == successor


def run_checks(
    root: Path, repository: str, excludes: Sequence[PurePosixPath]
) -> list[Finding]:
    """Run all the checks on the tree at `root`.

    Args:
        root: The directory to check, normally the root of a repository.
        repository: The `owner/name` of the repository, which tells a
            sentence about this repository from one about another.
        excludes: The normalized path prefixes that the citation scan skips.

    Returns:
        The findings without duplicates, sorted by path, line and message.

    Raises:
        OSError: A schema or a file cannot be read, or Git cannot list the
            files.
    """
    files = list_files(root)
    records, findings = collect_records(files)
    findings.extend(find_duplicate_numbers(records))
    record_schema = load_schema(RECORD_SCHEMA)
    for record in records:
        findings.extend(check_record(root, record, record_schema))
    entries, ledger_findings = load_ledger(root, load_schema(LEDGER_SCHEMA))
    findings.extend(ledger_findings)
    findings.extend(check_entries(entries, records))
    catalog = _build_catalog(root, files, records, entries)
    findings.extend(_check_citations(catalog, files, repository, excludes))
    return sorted(set(findings))


def _build_catalog(
    root: Path,
    files: Sequence[PurePosixPath],
    records: Sequence[Record],
    entries: Sequence[LedgerEntry],
) -> Catalog:
    """Index the records, the ledger entries and the listed files."""
    by_number: dict[str, Record] = {}
    for record in records:
        by_number.setdefault(record.number, record)
    return Catalog(
        root=root,
        records=by_number,
        record_names=frozenset(record.name for record in records),
        ledger={entry.number: entry for entry in entries},
        spec_numbers=_spec_numbers(root),
        files=frozenset(path.as_posix() for path in files),
    )


def _spec_numbers(root: Path) -> frozenset[str]:
    """Return the numbers of the spec files, listing the spec folder once."""
    folder = root / _SPECS_DIR
    if not folder.is_dir():
        return frozenset()
    return frozenset(
        match["number"]
        for entry in folder.iterdir()
        if (match := _SPEC_NAME.match(entry.name))
    )


def _check_citations(
    catalog: Catalog,
    files: Sequence[PurePosixPath],
    repository: str,
    excludes: Sequence[PurePosixPath],
) -> list[Finding]:
    """Scan every text file of the listing and resolve its citations."""
    findings: list[Finding] = []
    for relative in iter_candidate_files(catalog.root, files, excludes):
        path = relative.as_posix()
        if path == LEDGER_PATH:
            continue
        text = read_text_file(catalog.root / relative)
        if text is None:
            continue
        prose = relative.suffix in PROSE_SUFFIXES
        citations = scan_text(text, repository, path=relative, prose=prose)
        findings.extend(_resolve_all(catalog, path, citations))
    return findings


def _resolve_all(
    catalog: Catalog, path: str, citations: Sequence[Citation]
) -> list[Finding]:
    """Resolve the citations of one file: a range gives one finding for a problem.

    A number that the text cites alone is resolved on its own. The numbers of
    one range are resolved together by `_resolve_range`.
    """
    findings: list[Finding] = []
    ranges: dict[int, list[Citation]] = {}
    for citation in citations:
        if citation.range_id is not None:
            ranges.setdefault(citation.range_id, []).append(citation)
        elif (finding := _resolve(catalog, path, citation)) is not None:
            findings.append(finding)
    for members in ranges.values():
        findings.extend(_resolve_range(catalog, path, members))
    return findings


def _resolve_range(
    catalog: Catalog, path: str, members: Sequence[Citation]
) -> list[Finding]:
    """Resolve the numbers of one range of records or of specs.

    The numbers that do not exist give one finding, which names them with
    `_list_runs`. When only one number does not exist, the finding is the one
    that a single citation gets. A record that the ledger holds gives its own
    finding, as a single citation does, because the advice differs for each.

    Args:
        catalog: What exists in the checked tree.
        path: The file that holds the range, relative to the root.
        members: The citations of the range, in ascending order. They are all
            of one kind and on one line.
    """
    numbers = [member.value for member in members]
    if members[0].kind is CitationKind.SPEC_NUMBER:
        problems = _spec_range_problems(catalog, numbers)
    else:
        problems = _record_range_problems(catalog, path, numbers)
    return [Finding(path, members[0].line, problem) for problem in problems]


def _spec_range_problems(catalog: Catalog, numbers: Sequence[str]) -> list[str]:
    """Explain the specs of a range that have no file: one text for all of them."""
    missing = [number for number in numbers if number not in catalog.spec_numbers]
    if len(missing) > 1:
        return [f"specs {_list_runs(missing)} have no file {_SPECS_DIR}/NNNN-*.md"]
    return [
        problem for number in missing if (problem := _spec_problem(catalog, number))
    ]


def _record_range_problems(
    catalog: Catalog, path: str, numbers: Sequence[str]
) -> list[str]:
    """Explain the records of a range that do not resolve.

    The numbers that exist nowhere share one text. Each other number is resolved
    as a single citation of `path`.
    """
    missing: list[str] = []
    problems: list[str] = []
    for number in numbers:
        if _is_unknown_record(catalog, number):
            missing.append(number)
        elif (problem := _record_problem(catalog, path, number)) is not None:
            problems.append(problem)
    if len(missing) > 1:
        problems.append(f"decision records {_list_runs(missing)} do not exist")
    else:
        problems.extend(
            problem
            for number in missing
            if (problem := _record_problem(catalog, path, number))
        )
    return problems


def _is_unknown_record(catalog: Catalog, number: str) -> bool:
    """Tell whether `number` is neither a record in force nor in the ledger."""
    return number not in catalog.records and number not in catalog.ledger


def _list_runs(numbers: Sequence[str]) -> str:
    """Write ascending four-digit numbers with the runs of neighbours collapsed.

    A run of two or more numbers is `first to last`. The runs are joined with
    commas and a last `and`, so `0002 to 0099 and 0101` names the numbers 0002
    to 0099 and 0101, and `0002, 0004 to 0006 and 0009` names four groups.

    Args:
        numbers: At least one number, in ascending order, with no repeat.
    """
    runs: list[list[str]] = []
    for number in numbers:
        if runs and int(number) == int(runs[-1][-1]) + 1:
            runs[-1].append(number)
        else:
            runs.append([number])
    texts = [run[0] if len(run) == 1 else f"{run[0]} to {run[-1]}" for run in runs]
    if len(texts) == 1:
        return texts[0]
    return f"{', '.join(texts[:-1])} and {texts[-1]}"


def _resolve(catalog: Catalog, path: str, citation: Citation) -> Finding | None:
    """Return a finding when `citation` does not resolve, else `None`."""
    problem: str | None
    if citation.kind is CitationKind.RECORD_NUMBER:
        problem = _record_problem(catalog, path, citation.value)
    elif citation.kind is CitationKind.RECORD_FILE:
        problem = _record_file_problem(catalog, path, citation.value)
    elif citation.kind is CitationKind.SPEC_NUMBER:
        problem = _spec_problem(catalog, citation.value)
    elif citation.kind is CitationKind.REVERSED_RANGE:
        problem = (
            "a range must run from the lower number to the higher, "
            f"not {citation.value}"
        )
    elif citation.kind is CitationKind.OVERSIZED_RANGE:
        problem = (
            f"the ranges of a file may name {MAX_RANGE_NUMBERS} numbers in all: "
            f"the range {citation.value} is not expanded"
        )
    else:
        problem = _doc_path_problem(catalog.files, citation.value)
    return None if problem is None else Finding(path, citation.line, problem)


def _record_problem(catalog: Catalog, path: str, number: str) -> str | None:
    """Explain why a citation of record `number` does not resolve, if it does not."""
    if number in catalog.records:
        return None
    entry = catalog.ledger.get(number)
    if entry is None:
        return f"decision record {number} does not exist"
    if catalog.may_cite_deleted(path, number):
        return None
    if entry.successor is None:
        return (
            f"decision record {number} was withdrawn into the ledger: "
            "remove the citation"
        )
    return (
        f"decision record {number} was deleted into the ledger: "
        f"cite its successor, ADR {entry.successor}"
    )


def _record_file_problem(catalog: Catalog, path: str, name: str) -> str | None:
    """Explain why a citation of the record file `name` does not resolve."""
    number = name[:4]
    problem = _record_problem(catalog, path, number)
    # A deleted record that this file may cite has no file to compare with.
    if problem is not None or number not in catalog.records:
        return problem
    if name in catalog.record_names:
        return None
    return f"no decision record file is named {name}"


def _spec_problem(catalog: Catalog, number: str) -> str | None:
    """Explain why a citation of spec `number` does not resolve, if it does not."""
    if number in catalog.spec_numbers:
        return None
    return f"spec {number} has no file {_SPECS_DIR}/{number}-*.md"


def _doc_path_problem(files: frozenset[str], doc_path: str) -> str | None:
    """Explain why a cited documentation path does not exist, if it does not.

    The path is looked up in the listing of the root, whatever the file system:
    a path in another letter case, or a file that `.gitignore` hides, does not
    exist. A Linux CI run, which is case-sensitive and has only the files of
    the repository, reaches the same answer.
    """
    if doc_path in files:
        return None
    return f"the file {doc_path} does not exist"
