"""Shared fixtures of the tests of the workflow check.

A test builds a tree in a temporary directory, writes the workflow text that it
needs and runs the tool on it. The helpers build the text from small parts, so
each test shows the one line that it is about.
"""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from workflows.cli import main

WORKFLOW_PATH = ".github/workflows/ci.yml"
"""The path of the workflow that the tests write most often."""

TIMEOUT_ADVICE = (
    "set timeout-minutes to a whole number from 1 to 360 or to an expression"
)
"""The end of every finding about a time limit."""


def job(job_id: str, *extra_lines: str) -> str:
    """Return a job as text that has a checkout step and the given key lines.

    The hub's `leaks` check reads test files too. Its rule `runner-label`
    reads the text that follows every `runs-on` key in a file, up to the end
    of the line, and reports each label that isn't a label of a runner hosted
    by GitHub. If one Python string held the key and the next line, the source
    line would carry an escape sequence and more text after the hosted label,
    and the rule would read them as more labels. So each line of the job is
    its own string in the list `lines`: the source line of the key ends right
    after the hosted label `ubuntu-latest`.

    Args:
        job_id: The key of the job.
        extra_lines: Lines for the job, such as `timeout-minutes: 5`. Each one
            is indented as a key of the job.
    """
    lines = [
        f"  {job_id}:",
        "    runs-on: ubuntu-latest",
        *(f"    {line}" for line in extra_lines),
        "    steps:",
        "      - run: echo done",
    ]
    return "\n".join(lines) + "\n"


def call_job(job_id: str, *extra_lines: str) -> str:
    """Return a job that calls a reusable workflow, with the given key lines."""
    lines = [
        f"  {job_id}:",
        "    uses: ./.github/workflows/reusable.yml",
        *(f"    {line}" for line in extra_lines),
    ]
    return "\n".join(lines) + "\n"


def workflow(on: str, *parts: str, header: tuple[str, ...] = ()) -> str:
    """Return a workflow text.

    Args:
        on: The text after the key `on`, on the same line, such as `push`.
            Text that starts with a line break and indented lines writes a
            list or a mapping out.
        parts: The jobs, from `job` and `call_job`.
        header: Top-level lines between the `on` key and the jobs, such as
            `concurrency: group`.
    """
    lines = ["name: Test", f"on: {on}", *header, "jobs:"]
    return "\n".join(lines) + "\n" + "".join(parts)


def line_of_text(text: str, needle: str) -> int:
    """Return the 1-based number of the first line of `text` that holds `needle`."""
    for number, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return number
    raise AssertionError(f"{needle!r} is not in the text")


class TreeTestCase(unittest.TestCase):
    """A test case with an empty directory in `self.root`.

    Attributes:
        root: The directory that the test fills and checks.
    """

    root: Path

    def setUp(self) -> None:
        """Create the directory and remove it after the test."""
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)

    def write(self, path: str, content: str | bytes) -> None:
        """Write one file below the root, with its parent folders."""
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")

    def run_cli(self) -> tuple[int, list[str], str]:
        """Run the tool on the root.

        Returns:
            The exit status, the lines of standard output and standard error.
        """
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = main([str(self.root)])
        return status, stdout.getvalue().splitlines(), stderr.getvalue()

    def findings_of(self, text: str, path: str = WORKFLOW_PATH) -> list[str]:
        """Write a workflow, run the tool and return the lines of findings."""
        self.write(path, text)
        return self.run_cli()[1]
