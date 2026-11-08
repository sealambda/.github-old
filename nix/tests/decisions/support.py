"""Helpers that the tests share: temporary trees and a command line runner."""

import contextlib
import io
import subprocess
import tempfile
import unittest
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from unittest import mock

from decisions import cli
from decisions.check import run_checks
from decisions.walk import parse_exclude

REPOSITORY = "sealambda/hub-test"
"""The repository name that the tests check as."""

LEDGER = "docs/decisions/superseded.yaml"
"""The ledger path in a test tree."""


FRONT_MATTER = (
    "---\nstatus: accepted\ndate: 2026-01-01\ndecision-makers: Test Maker\n---\n\n"
)
"""Valid record front matter and the blank line after it: six lines."""


def record_text(body: str = "") -> str:
    """Return a record with valid front matter and a title, followed by `body`.

    A `body` that starts with a level-1 heading brings its own title. Otherwise
    the title is `A decision` on line 7, and the first line of a non-empty
    `body` is line 9.
    """
    if body.startswith("# "):
        return FRONT_MATTER + body
    return FRONT_MATTER + "# A decision\n" + (f"\n{body}" if body else "")


def ledger_entry(
    number: str, successor: str | None = None, line_suffix: str = ""
) -> str:
    """Return one valid ledger entry as YAML text.

    Args:
        number: The number of the deleted record.
        successor: The number of its successor, or `None` for a withdrawn one.
        line_suffix: Text appended to the `title` line, to make a title unique.
    """
    lines = [
        f'- number: "{number}"',
        f"  title: Deleted record {number}{line_suffix}",
        f"  commit: {'a1' * 20}",
        f"  path: docs/decisions/{number}-deleted.md",
    ]
    if successor is not None:
        lines.append(f'  successor: "{successor}"')
    lines.append("  date: 2026-02-03")
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class CliResult:
    """The outcome of one run of the command line.

    Attributes:
        code: The exit status.
        stdout: What the run printed to standard output.
        stderr: What the run printed to standard error.
    """

    code: int
    stdout: str
    stderr: str


class TreeTestCase(unittest.TestCase):
    """A test case with a fresh temporary directory in `self.root`."""

    root: Path

    def setUp(self) -> None:
        """Create the temporary tree root and schedule its removal."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write(self, files: Mapping[str, str]) -> None:
        """Write text files below the root, creating folders as needed."""
        for relative, text in files.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def without_git(self) -> None:
        """Make `git` unavailable to the walker for the rest of the test.

        A test that writes a fake `.git` entry needs this: the walker would
        otherwise ask `git` about a repository that does not exist.
        """
        self.enterContext(mock.patch("decisions.walk.shutil.which", return_value=None))

    def git_init(self) -> None:
        """Turn the root into a Git work tree, with no commit and no identity."""
        self.git("init", "--quiet")

    def git(self, *args: str) -> str:
        """Run `git` with `args` in the root and return its trimmed output.

        Raises:
            subprocess.CalledProcessError: Git exited with a nonzero status.
        """
        completed = subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            capture_output=True,
            encoding="utf-8",
        )
        return completed.stdout.strip()

    def findings(self, exclude: Sequence[str] = ()) -> list[str]:
        """Run all checks on the tree and return the findings as text."""
        excludes = [parse_exclude(prefix) for prefix in exclude]
        return [
            finding.format() for finding in run_checks(self.root, REPOSITORY, excludes)
        ]

    def run_cli(self, *args: str, today: Callable[[], date] = date.today) -> CliResult:
        """Run `decisions.cli.main` with `args` and capture its output.

        Args:
            *args: The command line after the program name.
            today: The clock for `retire`.
        """
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.main(list(args), today=today)
        return CliResult(code, stdout.getvalue(), stderr.getvalue())

    def run_cli_on_root(self, *extra: str) -> CliResult:
        """Run `decisions check` on the tree root as `REPOSITORY`."""
        return self.run_cli("check", "--repository", REPOSITORY, *extra, str(self.root))


def posix(path: str) -> PurePosixPath:
    """Return `path` as a `PurePosixPath`, to compare with walker results."""
    return PurePosixPath(path)
