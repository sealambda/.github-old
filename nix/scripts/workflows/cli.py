"""The command line of the tool.

Usage:

    workflows ROOT

Exit status: 0 when every job has a time limit and every pull request workflow
has a concurrency group, 1 when a check finds a problem, 2 for a usage error or
a file that cannot be read, 3 for an internal error. Each finding is printed to
standard output as `path:line: message`, all in one run. `decisions.cli_common`
holds the exit status contract that every tool of the hub shares.
"""

import sys
from collections.abc import Sequence
from pathlib import Path

from decisions.cli_common import RaisingParser, UsageError, report_findings, run_guarded
from workflows.check import check_tree


def _parse(argv: Sequence[str]) -> Path:
    """Parse the arguments and return the root to check.

    Raises:
        UsageError: ROOT is missing or isn't a directory, or an option is
            unknown.
    """
    parser = RaisingParser(
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
        The exit status of `decisions.cli_common.run_guarded`.
    """

    def run() -> int:
        root = _parse(sys.argv[1:] if argv is None else argv)
        return report_findings("workflows", check_tree(root))

    return run_guarded("workflows", run)
