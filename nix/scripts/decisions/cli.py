"""The command line of the tool.

Usage:

- `decisions check --repository OWNER/NAME [--exclude PATH]... ROOT`
- `decisions retire NNNN (--by MMMM | --withdrawn) [--exclude PATH]... [--root DIR]`

Exit status of `check`: 0 when no check finds a problem, 1 when a check finds
one, 2 for a usage error, 3 for an internal error. Each finding is printed to
standard output as `path:line: message`, all in one run.

Exit status of `retire`: 0 when the record is retired, whatever the check
finds afterwards, 2 when a rule or a usage error refuses the retirement or a
step fails, and 3 for an internal error. A refusal changes nothing. After an
internal error, check the work tree with `git status`.

An internal error is an exception that the tool does not expect, which means a
bug in the tool. The traceback goes to standard error. Status 1 stays reserved
for findings, so that a caller can tell a bug from a problem in the checked tree.
"""

import argparse
import re
import sys
import traceback
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import NoReturn

from decisions.check import run_checks
from decisions.retire import RetireError, RetireResult, retire
from decisions.walk import parse_exclude

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3

_REPOSITORY = re.compile(r"^[\w.-]+/[\w.-]+$")
_NUMBER = re.compile(r"^[0-9]{4}$")


class UsageError(Exception):
    """The command line or the environment is wrong, not the checked tree."""


class _Parser(argparse.ArgumentParser):
    """An argument parser that raises `UsageError` instead of exiting."""

    def error(self, message: str) -> NoReturn:
        """Raise `UsageError` with the usage text and the problem."""
        raise UsageError(f"{self.format_usage().strip()}\n{self.prog}: {message}")


@dataclass(frozen=True)
class CheckArgs:
    """The validated arguments of `decisions check`.

    Attributes:
        root: The directory to check.
        repository: The `owner/name` of the repository that holds `root`.
        excludes: The normalized path prefixes that the citation scan skips.
    """

    root: Path
    repository: str
    excludes: list[PurePosixPath]


@dataclass(frozen=True)
class RetireArgs:
    """The validated arguments of `decisions retire`.

    Attributes:
        root: A directory inside the repository.
        number: The number of the record to retire.
        successor: The replacing record, `None` for `--withdrawn`.
        excludes: The normalized path prefixes for the final check.
    """

    root: Path
    number: str
    successor: str | None
    excludes: list[PurePosixPath]


def _add_exclude(parser: argparse.ArgumentParser) -> None:
    """Add the repeatable `--exclude` option, shared by both commands."""
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATH",
        help="a path prefix relative to the root whose files are not scanned "
        "for citations; repeat for several",
    )


def _build_parser() -> _Parser:
    """Build the argument parser with its two commands."""
    parser = _Parser(
        prog="decisions",
        description="Check decision records, specs and the citations that name "
        "them, and retire a record into the ledger.",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    check = commands.add_parser(
        "check", help="report the findings of the checks on a directory"
    )
    check.add_argument("root", type=Path, help="the directory to check")
    check.add_argument(
        "--repository",
        required=True,
        metavar="OWNER/NAME",
        help="the repository that holds ROOT; a citation that another "
        "repository qualifies, as in 'sealambda/infra ADR 0038', is skipped",
    )
    _add_exclude(check)

    retire_parser = commands.add_parser(
        "retire", help="delete a record and list it in the ledger"
    )
    retire_parser.add_argument("number", metavar="NNNN", help="the record to retire")
    how = retire_parser.add_mutually_exclusive_group(required=True)
    how.add_argument(
        "--by", metavar="MMMM", help="the record in force that replaces it"
    )
    how.add_argument(
        "--withdrawn",
        action="store_true",
        help="the record no longer applies and has no replacement",
    )
    retire_parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        metavar="DIR",
        help="a directory inside the repository (default: the current one)",
    )
    _add_exclude(retire_parser)
    return parser


def _parse(argv: Sequence[str]) -> CheckArgs | RetireArgs:
    """Parse and validate the arguments.

    Raises:
        UsageError: An argument is missing or malformed, or a directory that
            the command reads does not exist.
    """
    args = _build_parser().parse_args(argv)
    try:
        excludes = [parse_exclude(prefix) for prefix in args.exclude]
    except ValueError as error:
        raise UsageError(str(error)) from error
    if args.command == "check":
        return _check_args(args, excludes)
    return _retire_args(args, excludes)


def _check_args(args: argparse.Namespace, excludes: list[PurePosixPath]) -> CheckArgs:
    """Validate the arguments of `check`."""
    if not _REPOSITORY.match(args.repository):
        raise UsageError(f"--repository must look like OWNER/NAME: {args.repository}")
    if not args.root.is_dir():
        raise UsageError(f"ROOT is not a directory: {args.root}")
    return CheckArgs(args.root, args.repository, excludes)


def _retire_args(args: argparse.Namespace, excludes: list[PurePosixPath]) -> RetireArgs:
    """Validate the arguments of `retire`."""
    for label, value in (("NNNN", args.number), ("--by", args.by)):
        if value is not None and not _NUMBER.match(value):
            raise UsageError(f"{label} must be a four-digit number: {value}")
    if not args.root.is_dir():
        raise UsageError(f"--root is not a directory: {args.root}")
    return RetireArgs(args.root, args.number, args.by, excludes)


def main(
    argv: Sequence[str] | None = None,
    *,
    today: Callable[[], date] = date.today,
) -> int:
    """Run a command and return the exit status.

    Args:
        argv: The arguments after the program name. `None` reads `sys.argv`.
        today: The clock of `retire`: it returns the local date of the ledger
            entry. Tests pass a fixed date.

    Returns:
        `EXIT_CLEAN`, `EXIT_FINDINGS`, `EXIT_USAGE` or `EXIT_INTERNAL`. An
        exception that no other clause handles is a bug in the tool: its
        traceback goes to standard error and the status is `EXIT_INTERNAL`.
    """
    try:
        args = _parse(sys.argv[1:] if argv is None else argv)
        if isinstance(args, CheckArgs):
            return _run_check(args)
        return _run_retire(args, today())
    except RetireError as error:
        print(f"decisions: {error}", file=sys.stderr)
        return EXIT_USAGE
    except UsageError as error:
        print(error, file=sys.stderr)
        return EXIT_USAGE
    except OSError as error:
        print(f"decisions: {error}", file=sys.stderr)
        return EXIT_USAGE
    except Exception:  # the last resort: report any bug with its trace
        traceback.print_exc()
        print("decisions: internal error, the traceback is above", file=sys.stderr)
        return EXIT_INTERNAL


def _run_check(args: CheckArgs) -> int:
    """Run the checks and print the findings."""
    findings = run_checks(args.root, args.repository, args.excludes)
    for finding in findings:
        print(finding.format())
    if findings:
        print(f"decisions: {len(findings)} finding(s)", file=sys.stderr)
        return EXIT_FINDINGS
    return EXIT_CLEAN


def _run_retire(args: RetireArgs, today: date) -> int:
    """Retire a record and print what changed and what is left to fix."""
    result = retire(args.root, args.number, args.successor, args.excludes, today)
    _print_retirement(result)
    return EXIT_CLEAN


def _print_retirement(result: RetireResult) -> None:
    """Print the permalink, the rewritten entries and the findings."""
    entry = result.entry
    print(f"retired record {entry.number}: {entry.title}")
    if result.rewritten:
        print(
            f"successor changed to {entry.successor} in: {', '.join(result.rewritten)}"
        )
    print(f"permalink: {result.permalink}")
    if result.check_error is not None:
        print(
            f"the final check did not run: {result.check_error}\n"
            "the record is retired; fix the cause, then run `decisions check`"
        )
        return
    if not result.findings:
        print("the check reports no finding")
        return
    print(f"the check reports {len(result.findings)} finding(s) to fix:")
    for finding in result.findings:
        print(finding.format())
