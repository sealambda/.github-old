"""The command line of the checker.

Usage: `decisions --repository OWNER/NAME [--exclude PATH]... ROOT`

Exit status: 0 when no check finds a problem, 1 when a check finds one, 2 for
a usage error, 3 for an internal error. Each finding is printed to standard
output as `path:line: message`, all in one run.

An internal error is an exception that the tool does not expect, which means a
bug in the tool. The traceback goes to standard error. Status 1 stays reserved
for findings, so that a caller can tell a bug from a problem in the checked tree.
"""

import argparse
import re
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import NoReturn

from decisions.check import run_checks
from decisions.walk import parse_exclude

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3

_REPOSITORY = re.compile(r"^[\w.-]+/[\w.-]+$")


class UsageError(Exception):
    """The command line or the environment is wrong, not the checked tree."""


class _Parser(argparse.ArgumentParser):
    """An argument parser that raises `UsageError` instead of exiting."""

    def error(self, message: str) -> NoReturn:
        """Raise `UsageError` with the usage text and the problem."""
        raise UsageError(f"{self.format_usage().strip()}\n{self.prog}: {message}")


def _build_parser() -> _Parser:
    """Build the argument parser."""
    parser = _Parser(
        prog="decisions",
        description="Check decision records, specs and the citations that name them.",
    )
    parser.add_argument("root", type=Path, help="the directory to check")
    parser.add_argument(
        "--repository",
        required=True,
        metavar="OWNER/NAME",
        help="the repository that holds ROOT; a citation that another "
        "repository qualifies, as in 'sealambda/infra ADR 0038', is skipped",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATH",
        help="a path prefix relative to ROOT whose files are not scanned for "
        "citations; repeat for several",
    )
    return parser


def _parse(argv: Sequence[str]) -> tuple[Path, str, list[PurePosixPath]]:
    """Parse and validate the arguments.

    Raises:
        UsageError: An argument is missing or malformed, or ROOT is not a folder.
    """
    args = _build_parser().parse_args(argv)
    if not _REPOSITORY.match(args.repository):
        raise UsageError(f"--repository must look like OWNER/NAME: {args.repository}")
    if not args.root.is_dir():
        raise UsageError(f"ROOT is not a directory: {args.root}")
    try:
        excludes = [parse_exclude(prefix) for prefix in args.exclude]
    except ValueError as error:
        raise UsageError(str(error)) from error
    return args.root, args.repository, excludes


def main(argv: Sequence[str] | None = None) -> int:
    """Run the checker and return the exit status.

    Args:
        argv: The arguments after the program name. `None` reads `sys.argv`.

    Returns:
        `EXIT_CLEAN`, `EXIT_FINDINGS`, `EXIT_USAGE` or `EXIT_INTERNAL`. An
        exception that no other clause handles is a bug in the tool: its
        traceback goes to standard error and the status is `EXIT_INTERNAL`.
    """
    try:
        root, repository, excludes = _parse(sys.argv[1:] if argv is None else argv)
        findings = run_checks(root, repository, excludes)
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
    for finding in findings:
        print(finding.format())
    if findings:
        print(f"decisions: {len(findings)} finding(s)", file=sys.stderr)
        return EXIT_FINDINGS
    return EXIT_CLEAN
