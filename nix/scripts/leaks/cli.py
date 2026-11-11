"""The command line of the tool.

Usage:

    leaks --organization NAME [--public-repository NAME]...
          [--public-team NAME]... [--exclude PATH]... ROOT

Exit status: 0 when no rule finds a leak, 1 when a rule finds one, 2 for a
usage error or a file that cannot be read, 3 for an internal error. Each
finding is printed to standard output as `path:line: rule: text. advice`, all
in one run.

An internal error is an exception that the tool does not expect, which means a
bug in the tool. The traceback goes to standard error. Status 1 stays reserved
for findings, so that a caller can tell a bug from a leak in the scanned tree.
"""

import argparse
import re
import sys
import traceback
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import NoReturn

from decisions.walk import parse_exclude
from leaks.rules import Policy
from leaks.scan import scan_tree

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3

_ORGANIZATION = re.compile(r"^[A-Za-z0-9-]+$")
_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


class UsageError(Exception):
    """The command line is wrong, not the scanned tree."""


class _Parser(argparse.ArgumentParser):
    """An argument parser that raises `UsageError` instead of exiting."""

    def error(self, message: str) -> NoReturn:
        """Raise `UsageError` with the usage text and the problem."""
        raise UsageError(f"{self.format_usage().strip()}\n{self.prog}: {message}")


@dataclass(frozen=True)
class Args:
    """The validated arguments.

    Attributes:
        root: The directory to scan.
        policy: The organization and the names that are public.
        excludes: The normalized path prefixes that the scan skips.
    """

    root: Path
    policy: Policy
    excludes: list[PurePosixPath]


def _build_parser() -> _Parser:
    """Build the argument parser."""
    parser = _Parser(
        prog="leaks",
        description="Report the private facts of an organization in a public "
        "source tree: account identifiers, buckets, runner labels, internal "
        "hosts, GitHub App identifiers and the names of repositories that are "
        "not public.",
    )
    parser.add_argument("root", type=Path, metavar="ROOT", help="the directory to scan")
    parser.add_argument(
        "--organization",
        required=True,
        metavar="NAME",
        help="the GitHub login of the organization",
    )
    parser.add_argument(
        "--public-repository",
        action="append",
        default=[],
        metavar="NAME",
        help="a repository of the organization that the tree may name; repeat "
        "for several",
    )
    parser.add_argument(
        "--public-team",
        action="append",
        default=[],
        metavar="NAME",
        help="a team of the organization that the tree may mention; repeat for several",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATH",
        help="a path prefix relative to the root whose files are not scanned; "
        "repeat for several",
    )
    return parser


def _names(label: str, values: Sequence[str]) -> frozenset[str]:
    """Validate a list of repository or team names and lower their case.

    Raises:
        UsageError: A value is not a GitHub name.
    """
    for value in values:
        if not _NAME.match(value):
            raise UsageError(f"{label} is not a name: {value}")
    return frozenset(value.lower() for value in values)


def _parse(argv: Sequence[str]) -> Args:
    """Parse and validate the arguments.

    Raises:
        UsageError: An argument is missing or malformed, or ROOT is not a
            directory.
    """
    args = _build_parser().parse_args(argv)
    if not _ORGANIZATION.match(args.organization):
        raise UsageError(f"--organization is not a GitHub login: {args.organization}")
    try:
        excludes = [parse_exclude(prefix) for prefix in args.exclude]
    except ValueError as error:
        raise UsageError(str(error)) from error
    if not args.root.is_dir():
        raise UsageError(f"ROOT is not a directory: {args.root}")
    policy = Policy(
        organization=args.organization,
        public_repositories=_names("--public-repository", args.public_repository),
        public_teams=_names("--public-team", args.public_team),
    )
    return Args(args.root, policy, excludes)


def main(argv: Sequence[str] | None = None) -> int:
    """Scan a tree and return the exit status.

    Args:
        argv: The arguments after the program name. `None` reads `sys.argv`.

    Returns:
        `EXIT_CLEAN`, `EXIT_FINDINGS`, `EXIT_USAGE` or `EXIT_INTERNAL`. An
        exception that no other clause handles is a bug in the tool: its
        traceback goes to standard error and the status is `EXIT_INTERNAL`.
    """
    try:
        args = _parse(sys.argv[1:] if argv is None else argv)
        findings = scan_tree(args.root, args.policy, args.excludes)
    except UsageError as error:
        print(error, file=sys.stderr)
        return EXIT_USAGE
    except OSError as error:
        print(f"leaks: {error}", file=sys.stderr)
        return EXIT_USAGE
    except Exception:  # the last resort: report any bug with its trace
        traceback.print_exc()
        print("leaks: internal error, the traceback is above", file=sys.stderr)
        return EXIT_INTERNAL
    for finding in findings:
        print(finding.format())
    if findings:
        print(f"leaks: {len(findings)} finding(s)", file=sys.stderr)
        return EXIT_FINDINGS
    return EXIT_CLEAN
