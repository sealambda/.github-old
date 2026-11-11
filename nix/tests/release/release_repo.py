"""Helpers for the release tests: a temporary git repository and a fake `gh`."""

import contextlib
import io
import os
import tempfile
import unittest
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

from release.cli import main
from release.runner import CommandError, Runner, command_runner


class FakeGh:
    """A stand-in for `gh` that records its calls and reaches no network.

    It answers the two commands that the tool uses, as `gh` 2.103 does:
    `release view <tag>` succeeds for a tag in `releases`, and otherwise it
    fails with the standard error `release not found`. `release create <tag>`
    adds the tag to `releases`. Any other call is a bug of the test.

    Attributes:
        calls: The arguments and the standard input of each call, in order.
        releases: The tags that have a release on the fake GitHub.
        failure: A message. When set, every call raises `CommandError` with it,
            as a failing `gh` does.
        view_failure: A message. When set, `release view` fails with it as its
            standard error, for a reason other than a missing release.
        create_failure: A message. When set, `release create` fails with it as
            its standard error.
    """

    def __init__(self) -> None:
        """Create a fake that has no call, no release and no failure."""
        self.calls: list[tuple[list[str], str | None]] = []
        self.releases: set[str] = set()
        self.failure: str | None = None
        self.view_failure: str | None = None
        self.create_failure: str | None = None

    def __call__(self, args: Sequence[str], *, stdin: str | None = None) -> str:
        """Record the call, then answer it or fail as the attributes say."""
        self.calls.append((list(args), stdin))
        if self.failure is not None:
            raise CommandError(self.failure)
        if list(args[:2]) == ["release", "view"]:
            return self._view(args[2])
        if list(args[:2]) == ["release", "create"]:
            self._create(args[2])
            return ""
        raise AssertionError(f"unexpected gh call: {list(args)}")

    def _view(self, tag: str) -> str:
        """Answer `release view`: the JSON of a release, or a failure."""
        stderr = self.view_failure
        if stderr is None and tag not in self.releases:
            stderr = "release not found"
        if stderr is not None:
            raise CommandError(f"gh release view {tag} failed: {stderr}", stderr)
        return f'{{"tagName":"{tag}"}}\n'

    def _create(self, tag: str) -> None:
        """Answer `release create`: add the release, or fail."""
        if self.create_failure is not None:
            message = self.create_failure
            raise CommandError(f"gh release create {tag} failed: {message}", message)
        self.releases.add(tag)


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


class RepoTestCase(unittest.TestCase):
    """A test case with a git repository in `self.root` and a fake `gh`.

    Git runs with a private `HOME` and no system or global configuration, so
    the settings of the person who runs the tests cannot change a result:
    signing is off and the identity is fixed.

    Attributes:
        root: The work tree of the repository.
        git: A runner of git in the work tree.
        gh: The fake `gh` that `run_cli` passes to the tool.
    """

    root: Path
    git: Runner
    gh: FakeGh

    def setUp(self) -> None:
        """Create an isolated, empty repository on the branch `main`."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home = Path(temporary.name) / "home"
        home.mkdir()
        self.root = Path(temporary.name) / "work"
        self.root.mkdir()
        self.enterContext(
            mock.patch.dict(
                os.environ,
                {
                    "HOME": str(home),
                    "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_CONFIG_NOSYSTEM": "1",
                },
            )
        )
        self.git = command_runner(["git", "-C", str(self.root)])
        self.gh = FakeGh()
        self.git(["init", "--quiet", "--initial-branch=main"])
        for key, value in (
            ("user.name", "Test Maker"),
            ("user.email", "maker@example.com"),
            ("commit.gpgsign", "false"),
            ("tag.gpgsign", "false"),
        ):
            self.git(["config", key, value])

    def commit(self, files: Mapping[str, str | None], message: str = "change") -> str:
        """Write or delete files, commit every change and return the commit.

        Args:
            files: The text of each path below the root. A value of `None`
                deletes the file.
            message: The commit message.
        """
        for relative, text in files.items():
            path = self.root / relative
            if text is None:
                path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git(["add", "--all"])
        self.git(["commit", "--quiet", "--allow-empty", "--message", message])
        return self.git(["rev-parse", "HEAD"]).strip()

    def tag(self, name: str, *, commit: str = "HEAD", annotated: bool = False) -> None:
        """Create a tag. An annotated tag is its own git object."""
        if annotated:
            self.git(["tag", "--annotate", "--message", name, name, commit])
        else:
            self.git(["tag", name, commit])

    def tag_names(self) -> list[str]:
        """Return the names of all tags of the repository."""
        return self.git(["tag", "--list"]).split()

    def run_cli(self, *args: str) -> CliResult:
        """Run `release.cli.main` on the repository and capture its output.

        The tool gets a runner of git for the work tree and the fake `gh`.
        """
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(list(args), git=self.git, gh=self.gh)
        return CliResult(code, stdout.getvalue(), stderr.getvalue())
