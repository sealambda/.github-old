"""Shared fixtures of the tests of the version check.

A test builds a tree in a temporary directory, writes the files that it needs
and runs the tool on it. The Nix version in the fixtures is made up: 2.99.1 isn't
a release, and it differs from the version in the hub's own `versions.json`, so
no test depends on the real value.
"""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from versions.cli import main

NIX_VERSION = "2.99.1"
"""The Nix version that `MANIFEST` holds."""

INSTALL_URL = f"https://releases.nixos.org/nix/nix-{NIX_VERSION}/install"
"""The installer address of `NIX_VERSION`, written out for the tests."""

OTHER_URL = "https://releases.nixos.org/nix/nix-2.30.0/install"
"""The installer address of another version."""

MANIFEST = (
    '{\n  "$schema": "./schemas/versions.schema.json",\n'
    f'  "nix": "{NIX_VERSION}"\n}}\n'
)
"""A valid `versions.json`."""

INSTALLER = "cachix/install-nix-action@0123456789abcdef0123456789abcdef01234567"
"""A pinned `uses` value of the Nix installer action."""

CHECKOUT = "      - uses: actions/checkout@v4\n"
"""A workflow step that doesn't install Nix."""

WORKFLOW_PATH = ".github/workflows/ci.yml"
"""The path of the workflow that the tests write most often."""


def installer_step(*, install_url: str | None, uses: str = INSTALLER) -> str:
    """Return a workflow step as text, indented for `workflow`.

    Args:
        install_url: The value of `with.install_url`, or `None` for a step
            without a `with` key.
        uses: The value of the `uses` key.
    """
    step = f"      - uses: {uses}\n"
    if install_url is not None:
        step += f"        with:\n          install_url: {install_url}\n"
    return step


def run_step(*script_lines: str) -> str:
    """Return a workflow step that runs a script, indented for `workflow`.

    Args:
        script_lines: The lines of the script, written as a block scalar so
            that characters such as `|` and `:` need no quoting.
    """
    body = "".join(f"          {line}\n" for line in script_lines)
    return f"      - run: |\n{body}"


def job(job_id: str, *steps: str) -> str:
    """Return a job as text, with the given steps as text.

    The hub's `leaks` check reads test files too. Its rule `runner-label`
    reads the text that follows every `runs-on` key in a file, up to the end
    of the line, and reports each label that isn't a label of a runner hosted
    by GitHub. If one Python string held the key and the next line, the source
    line would carry an escape sequence and more text after the hosted label,
    and the rule would read them as more labels. So each line of the job is
    its own string in the list `lines`: the source line of the key ends right
    after the hosted label `ubuntu-latest`.
    """
    lines = [
        f"  {job_id}:",
        "    runs-on: ubuntu-latest",
        "    steps:",
    ]
    return "\n".join(lines) + "\n" + "".join(steps)


def jobs_workflow(*jobs: str) -> str:
    """Return a workflow that holds the given jobs, as text from `job`."""
    return "\n".join(["name: CI", "on: push", "jobs:"]) + "\n" + "".join(jobs)


def workflow(*steps: str) -> str:
    """Return a workflow with one job: a checkout step and the given steps."""
    return jobs_workflow(job("check", CHECKOUT, *steps))


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
