"""Retire a decision record: delete it and list it in the ledger.

`retire` validates everything first and changes the tree only when no check
refuses. The changes are three: the ledger file, written through a temporary
file and a rename, `git rm` of the record, and `git add` of the ledger, so that
`git commit` records the deletion with its entry. The ledger comes first. A
failure of a later step is undone: the ledger text that the plan holds comes
back, and so does the record, in the index and in the work tree. The rules are
in `docs/reference/decision-records.md`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath

import yaml

from decisions import git
from decisions.check import run_checks
from decisions.findings import Finding
from decisions.git import GitError
from decisions.ledger import LedgerEntry, parse_ledger
from decisions.ledger_edit import (
    LedgerEditError,
    NewEntry,
    append_entry,
    rewrite_successors,
    write_text_atomically,
)
from decisions.records import LEDGER_PATH, Record, collect_records, record_title
from decisions.remote import parse_github_remote, permalink
from decisions.schemas import LEDGER_SCHEMA, load_schema
from decisions.walk import list_files

ORIGIN_REMOTE = "origin"
"""The remote whose URL names the repository for the permalink."""

PUBLISHED_REF = "origin/main"
"""The local ref that holds the published text of a record. `retire` never
fetches it."""


class RetireError(Exception):
    """The record cannot be retired, or retiring failed.

    The message says what to change. Unless it says otherwise, the work tree
    and the index are as they were.
    """


@dataclass(frozen=True)
class RetirePlan:
    """Everything that `apply_plan` writes, computed and validated.

    Attributes:
        root: The root of the repository.
        record: The record to delete.
        entry: The ledger entry of the record.
        repository: The `owner/name` of the repository, from `origin`.
        ledger_before: The ledger text now, `None` when the file is missing.
        ledger_after: The ledger text after the retirement.
        rewritten: The numbers of the entries whose successor changes.
    """

    root: Path
    record: Record
    entry: NewEntry
    repository: str
    ledger_before: str | None
    ledger_after: str
    rewritten: tuple[str, ...]


@dataclass(frozen=True)
class RetireResult:
    """What a finished retirement reports.

    Attributes:
        entry: The ledger entry that was added.
        permalink: The GitHub URL of the record at its last text.
        rewritten: The numbers of the entries whose successor changed.
        findings: The findings of the check on the tree after the change. Empty
            when the check could not run.
        check_error: Why the final check could not run, or `None` when it ran.
            The record is retired in both cases.
    """

    entry: NewEntry
    permalink: str
    rewritten: tuple[str, ...]
    findings: list[Finding]
    check_error: str | None = None


def retire(
    directory: Path,
    number: str,
    successor: str | None,
    excludes: Sequence[PurePosixPath],
    today: date,
) -> RetireResult:
    """Retire record `number` into the ledger and check the tree.

    Args:
        directory: A directory inside the repository.
        number: The four-digit number of the record to retire.
        successor: The number of the record that replaces it, or `None` to
            retire it as withdrawn.
        excludes: The normalized `exclude` prefixes for the final check.
        today: The date of the ledger entry.

    Returns:
        The entry, the permalink and the findings that the change leaves. When
        the final check cannot read the tree, the result holds no findings and
        says why in `check_error`: the record is retired by then, so the error
        must not hide that.

    Raises:
        RetireError: A rule refuses the retirement, or a step failed.
        OSError: A schema or a file cannot be read or written, before the
            change. After the change, an `OSError` of the final check goes to
            `check_error`.
    """
    try:
        root = git.toplevel(directory)
        plan = plan_retirement(root, number, successor, today)
        apply_plan(plan)
    except GitError as error:
        raise RetireError(str(error)) from error
    link = permalink(plan.repository, plan.entry.commit, plan.entry.path)
    try:
        findings = run_checks(root, plan.repository, excludes)
    except OSError as error:
        return RetireResult(plan.entry, link, plan.rewritten, [], str(error))
    return RetireResult(plan.entry, link, plan.rewritten, findings)


def plan_retirement(
    root: Path, number: str, successor: str | None, today: date
) -> RetirePlan:
    """Check every rule and compute the new ledger, without changing the tree.

    Args:
        root: The root of the repository.
        number: The number of the record to retire.
        successor: The replacing record, or `None` for a withdrawn record.
        today: The date of the ledger entry.

    Returns:
        The plan for `apply_plan`.

    Raises:
        RetireError: A rule refuses the retirement.
        GitError: A read-only git command failed.
        OSError: A file cannot be read.
    """
    ledger_before = _read_ledger(root)
    entries = _ledger_entries(ledger_before)
    records, _ = collect_records(list_files(root))
    record = _find_record(records, entries, number)
    _check_successor(records, entries, number, successor)
    published_path, commit = _published(root, record)
    entry = NewEntry(
        number=number,
        title=_title(root, record),
        commit=commit,
        path=published_path,
        successor=successor,
        date=today.isoformat(),
    )
    repository = _repository(root)
    ledger_after, rewritten = _new_ledger(ledger_before, entries, entry)
    return RetirePlan(
        root, record, entry, repository, ledger_before, ledger_after, rewritten
    )


def apply_plan(plan: RetirePlan) -> None:
    """Write the ledger, `git rm` the record, then `git add` the ledger.

    Raises:
        RetireError: A git step failed. The ledger and the record are restored
            and the message says so, or says how to finish the restoration
            when that failed too.
        OSError: The ledger could not be written. Nothing has changed.
    """
    write_text_atomically(plan.root / LEDGER_PATH, plan.ledger_after)
    record_removed = False
    try:
        git.remove_file(plan.root, plan.record.path)
        record_removed = True
        git.stage_file(plan.root, LEDGER_PATH)
    except GitError as error:
        _undo(plan, error, record_removed)
        raise RetireError(
            f"{error}\nnothing changed: the ledger is restored and "
            f"{plan.record.path} stays"
        ) from error


def _undo(plan: RetirePlan, cause: GitError, record_removed: bool) -> None:
    """Restore the ledger and, when `git rm` ran, the record.

    `git add` changes the index in one step or not at all, so after its
    failure the ledger has its old index entry and only the text needs to come
    back.

    Raises:
        RetireError: A restoration failed. The message says what is left and
            which command finishes the work.
    """
    left = _restore_ledger(plan)
    if record_removed:
        left += _restore_record(plan)
    if left:
        raise RetireError(f"{cause}\nthe tree is not as it was:\n" + "\n".join(left))


def _restore_ledger(plan: RetirePlan) -> list[str]:
    """Put the ledger text back as it was, and return what could not be undone."""
    ledger = plan.root / LEDGER_PATH
    try:
        if plan.ledger_before is None:
            ledger.unlink(missing_ok=True)
        else:
            write_text_atomically(ledger, plan.ledger_before)
    except OSError as error:
        return [
            f"- {LEDGER_PATH} still holds the entry for {plan.entry.number} "
            f"({error}): remove the entry by hand"
        ]
    return []


def _restore_record(plan: RetirePlan) -> list[str]:
    """Put the record back in the index and the tree, and return what failed."""
    try:
        git.restore_file(plan.root, plan.record.path)
    except GitError as error:
        return [
            f"- {plan.record.path} is deleted and staged ({error}): run "
            f"`git restore --source=HEAD --staged --worktree -- {plan.record.path}`"
        ]
    return []


def _read_ledger(root: Path) -> str | None:
    """Return the ledger text, or `None` when the file does not exist."""
    ledger = root / LEDGER_PATH
    if not ledger.is_file():
        return None
    try:
        return ledger.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise RetireError(f"{LEDGER_PATH} is not valid UTF-8 text") from error


def _ledger_entries(text: str | None) -> list[LedgerEntry]:
    """Parse the ledger, and refuse when the check would report it."""
    if text is None:
        return []
    entries, findings = parse_ledger(text, load_schema(LEDGER_SCHEMA))
    if findings:
        problems = "\n".join(finding.format() for finding in findings)
        raise RetireError(
            "the ledger is not valid; fix it first (run `decisions check`):\n"
            + problems
        )
    return entries


def _find_record(
    records: Sequence[Record], entries: Sequence[LedgerEntry], number: str
) -> Record:
    """Return the one record file of `number`, or raise `RetireError`."""
    if any(entry.number == number for entry in entries):
        raise RetireError(f"record {number} is already in the ledger")
    matches = [record for record in records if record.number == number]
    if not matches:
        raise RetireError(f"no record file docs/decisions/{number}-*.md")
    if len(matches) > 1:
        names = ", ".join(record.name for record in matches)
        raise RetireError(f"several record files have the number {number}: {names}")
    return matches[0]


def _check_successor(
    records: Sequence[Record],
    entries: Sequence[LedgerEntry],
    number: str,
    successor: str | None,
) -> None:
    """Refuse a successor that is not a record in force, or a bad withdrawal."""
    if successor is None:
        _check_withdrawal(entries, number)
    elif successor == number:
        raise RetireError(f"record {number} cannot be its own successor")
    elif successor not in {record.number for record in records}:
        raise RetireError(
            f"--by {successor} is not a record in force: no file "
            f"docs/decisions/{successor}-*.md. Name the record that took over"
        )


def _check_withdrawal(entries: Sequence[LedgerEntry], number: str) -> None:
    """Refuse a withdrawal that leaves a ledger entry without a live successor."""
    chained = [entry.number for entry in entries if entry.successor == number]
    if chained:
        raise RetireError(
            f"record {number} is the successor of {', '.join(chained)} in the "
            "ledger, so a withdrawal would leave those entries with a successor "
            "that is not in force. Retire it with --by, naming the record that "
            "took over, or change those entries by hand first"
        )


def _published(root: Path, record: Record) -> tuple[str, str]:
    """Return the path and the last commit of the record on `origin/main`.

    The ledger permalink is `<commit>/<path>`, so the text there must be the
    last text of the record, the text that this tree deletes. Two rules give
    that. The file has no local change, so the tree text is the text on `HEAD`.
    And the file on `origin/main` at the published path has that same text. The
    published path can differ from the path here: a parent branch of a stack,
    not merged yet, may have moved the record.

    Raises:
        RetireError: `origin/main` is missing, the record never reached it, or
            its text there differs from the text that this tree deletes.
    """
    if not git.ref_exists(root, PUBLISHED_REF):
        raise RetireError(f"{PUBLISHED_REF} does not exist here: run `git fetch`")
    path = _published_path(root, record)
    if git.has_local_changes(root, record.path):
        raise RetireError(f"{record.path} has uncommitted changes: restore it first")
    _require_same_text(root, record.path, path)
    commit = git.last_commit(root, PUBLISHED_REF, path)
    if commit is None:
        raise RetireError(f"{PUBLISHED_REF} has no commit for {path}")
    return path, commit


def _published_path(root: Path, record: Record) -> str:
    """Return the path where `origin/main` holds the record, or refuse.

    The candidates are the path here and every earlier name of the file in the
    history of `HEAD`, the most recent first. History finds a file that a
    commit not yet on `origin/main` renamed, whatever the old folder was. The
    first candidate that exists on `origin/main` is the answer.
    """
    for path in (record.path, *git.earlier_paths(root, record.path)):
        if _exists_on_published_ref(root, path):
            return path
    raise RetireError(
        f"{record.path} has never been on {PUBLISHED_REF}, and a ledger "
        "entry needs a commit that others can open. Merge the record "
        "first, or delete the file with `git rm` if it never mattered. "
        f"If it was merged lately, run `git fetch`: {PUBLISHED_REF} is the "
        "local ref and this command does not fetch"
    )


def _exists_on_published_ref(root: Path, path: str) -> bool:
    """Tell whether `origin/main` has a file at `path`."""
    try:
        git.blob_id(root, PUBLISHED_REF, path)
    except GitError:
        return False
    return True


def _require_same_text(root: Path, local_path: str, published_path: str) -> None:
    """Refuse a record whose text on `HEAD` differs from its text on `origin/main`.

    Comparing with `HEAD`, and not with the merge base, is deliberate: a branch
    that edits a record would otherwise link to the text before its edit.
    """
    if git.blob_id(root, "HEAD", local_path) != git.blob_id(
        root, PUBLISHED_REF, published_path
    ):
        where = "" if published_path == local_path else f" at {published_path}"
        raise RetireError(
            f"{local_path} on HEAD differs from {PUBLISHED_REF}{where}, so the "
            "permalink would show other text. Rebase onto origin/main, or fetch, "
            "first"
        )


def _title(root: Path, record: Record) -> str:
    """Return the first level-1 heading of the record, or refuse."""
    try:
        text = (root / record.path).read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise RetireError(f"{record.path} is not valid UTF-8 text") from error
    title = record_title(text)
    if title is None:
        raise RetireError(f"{record.path} has no level-1 heading for the title")
    return title


def _repository(root: Path) -> str:
    """Return the `owner/name` of the `origin` remote, or refuse."""
    url = git.remote_url(root, ORIGIN_REMOTE)
    try:
        return parse_github_remote(url)
    except ValueError as error:
        raise RetireError(f"remote {ORIGIN_REMOTE}: {error}") from error


def _new_ledger(
    before: str | None, entries: Sequence[LedgerEntry], entry: NewEntry
) -> tuple[str, tuple[str, ...]]:
    """Compute the ledger text after the retirement, and validate it.

    Raises:
        RetireError: The edit does not fit the ledger, or its result is not a
            valid ledger that holds the old entries and the new one.
    """
    rewritten: list[str] = []
    text = before
    try:
        if text is not None and entry.successor is not None:
            text, rewritten = rewrite_successors(text, entry.number, entry.successor)
        after = append_entry(text, entry)
    except (LedgerEditError, yaml.YAMLError) as error:
        raise RetireError(str(error)) from error
    _validate_ledger(after, entries, entry)
    return after, tuple(rewritten)


def _validate_ledger(
    after: str, before: Sequence[LedgerEntry], entry: NewEntry
) -> None:
    """Refuse an edited ledger that is invalid or lost an entry.

    Args:
        after: The edited ledger text.
        before: The entries of the ledger before the edit.
        entry: The entry that the edit adds.
    """
    entries, findings = parse_ledger(after, load_schema(LEDGER_SCHEMA))
    expected = [*(kept.number for kept in before), entry.number]
    problem = None
    if findings:
        problem = "\n".join(finding.format() for finding in findings)
    elif [kept.number for kept in entries] != expected:
        problem = "the new text does not hold the old entries and the new one"
    elif any(kept.successor == entry.number for kept in entries):
        problem = f"an entry still names {entry.number} as its successor"
    if problem is not None:
        raise RetireError(
            f"cannot add the entry to {LEDGER_PATH} by appending text: "
            f"{problem}\nedit the ledger by hand"
        )
