"""The command line of the tool.

Usage:

    workflows ROOT

Exit status: 0 when every job has a time limit and every pull request workflow
has a concurrency group, 1 when a check finds a problem, 2 for a usage error or
a file that cannot be read, 3 for an internal error. Each finding is printed to
standard output as `path:line: message`, all in one run.

An internal error is an exception that the tool does not expect, which means a
bug in the tool. The traceback goes to standard error. Status 1 stays reserved
for findings, so that a caller can tell a bug from a problem in the tree.
"""

import argparse
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from workflows.check import check_tree

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3


class UsageError(Exception):
    """The command line is wrong, not the checked tree."""


class _Parser(argparse.ArgumentParser):
    """An argument parser that raises `UsageError` instead of exiting."""

    def error(self, message: str) -> NoReturn:
        """Raise `UsageError` with the usage text and the problem."""
        raise UsageError(f"{self.format_usage().strip()}\n{self.prog}: {message}")


def _parse(argv: Sequence[str]) -> Path:
    """Parse the arguments and return the root to check.

    Raises:
        UsageError: ROOT is missing or isn't a directory, or an option is
            unknown.
    """
    parser = _Parser(
        prog="workflows",
        description="Check that every job of the workflows has a time limit and "
        "that every pull request workflow has a concurrency group.",
    )
    parser.add_argument("root", type=Path, metavar="ROOT", help="the tree to check")
    root: Path = parser.parse_args(argv).root
    if not root.is_dir():
        raise UsageError(f"ROOT is not a directory: {root}")
    return root


def main(argv: Sequence[str] | None = None) -> int:
    """Check a tree and return the exit status.

    Args:
        argv: The arguments after the program name. `None` reads `sys.argv`.

    Returns:
        `EXIT_CLEAN`, `EXIT_FINDINGS`, `EXIT_USAGE` or `EXIT_INTERNAL`. An
        exception that no other clause handles is a bug in the tool: its
        traceback goes to standard error and the status is `EXIT_INTERNAL`.
    """
    try:
        findings = check_tree(_parse(sys.argv[1:] if argv is None else argv))
    except UsageError as error:
        print(error, file=sys.stderr)
        return EXIT_USAGE
    except OSError as error:
        print(f"workflows: {error}", file=sys.stderr)
        return EXIT_USAGE
    except Exception:  # the last resort: report any bug with its trace
        traceback.print_exc()
        print("workflows: internal error, the traceback is above", file=sys.stderr)
        return EXIT_INTERNAL
    for finding in findings:
        print(finding.format())
    if findings:
        print(f"workflows: {len(findings)} finding(s)", file=sys.stderr)
        return EXIT_FINDINGS
    return EXIT_CLEAN
