"""Helpers for the tests that run git: a work repository with a bare `origin`."""

import os
import tempfile
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from unittest import mock

from support import CliResult, TreeTestCase, record_text

TODAY = date(2026, 3, 4)
"""The fixed date that the tests give `retire` as its clock."""

FIRST = "docs/decisions/0001-first.md"
"""The path of the first record that `publish_records` creates."""

SECOND = "docs/decisions/0002-second.md"
"""The path of the second record that `publish_records` creates."""

ORIGIN_URL = "git@github.com:acme/hub.git"
"""The URL that the tests give `origin` after the push."""


class GitTestCase(TreeTestCase):
    """A test case with a git work tree in `self.root` and a bare `origin`.

    Git runs with a private `HOME` and no system or global configuration, so
    the settings of the person who runs the tests cannot change a result:
    commit signing is off and the identity is fixed.

    Attributes:
        origin: The directory of the bare repository that `origin` names.
    """

    origin: Path

    def setUp(self) -> None:
        """Create the work tree, the bare origin and an isolated git setup."""
        super().setUp()
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.origin = Path(scratch.name) / "origin.git"
        home = Path(scratch.name) / "home"
        home.mkdir()
        patcher = mock.patch.dict(
            os.environ,
            {
                "HOME": str(home),
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.git("init", "--quiet", "--bare", "--initial-branch=main", str(self.origin))
        self.git("init", "--quiet", "--initial-branch=main")
        for key, value in (
            ("user.name", "Test Maker"),
            ("user.email", "maker@example.com"),
            ("commit.gpgsign", "false"),
            ("tag.gpgsign", "false"),
        ):
            self.git("config", key, value)
        self.git("remote", "add", "origin", str(self.origin))

    def commit(self, files: Mapping[str, str], message: str = "change") -> str:
        """Write `files`, commit every change and return the new commit hash."""
        self.write(files)
        self.git("add", "--all")
        self.git("commit", "--quiet", "--message", message)
        return self.git("rev-parse", "HEAD")

    def push(self) -> None:
        """Push `main` to `origin`, which creates or moves `origin/main` here.

        `set_origin_url` can give `origin` a GitHub URL that no test may reach.
        The push then rewrites that URL to the bare repository for this one
        command, with `url.<base>.insteadOf`.
        """
        url = self.git("config", "--get", "remote.origin.url")
        self.git(
            "-c",
            f"url.{self.origin}.insteadOf={url}",
            "push",
            "--quiet",
            "origin",
            "main",
        )

    def set_origin_url(self, url: str) -> None:
        """Point `origin` at `url`. The ref `origin/main` stays."""
        self.git("remote", "set-url", "origin", url)

    def publish_records(self) -> dict[str, str]:
        """Commit and push two records and a later unrelated change.

        Returns:
            The commit of each record by its path. Both differ from the final
            commit, so a wrong choice of commit shows in a test.
        """
        commits = {
            FIRST: self.commit(
                {FIRST: record_text("# First decision\n")}, "add the first record"
            ),
            SECOND: self.commit(
                {SECOND: record_text("# Second decision\n")}, "add the second record"
            ),
        }
        self.commit({"README.md": "A repository.\n"}, "add a readme")
        self.push()
        self.set_origin_url(ORIGIN_URL)
        return commits

    def run_retire(self, *args: str, root: Path | None = None) -> CliResult:
        """Run `decisions retire` in the work tree with the fixed clock.

        Args:
            *args: The arguments after `retire`.
            root: The value of `--root`, by default the work tree.
        """
        directory = self.root if root is None else root
        return self.run_cli(
            "retire", *args, "--root", str(directory), today=lambda: TODAY
        )

    def ledger_text(self) -> str | None:
        """Return the ledger text, or `None` when the file does not exist."""
        ledger = self.root / "docs/decisions/superseded.yaml"
        return ledger.read_text(encoding="utf-8") if ledger.exists() else None

    def tree_state(self) -> tuple[str, str | None]:
        """Return `git status --porcelain` and the ledger text.

        Two equal states mean that a command changed nothing that matters.
        """
        return self.git("status", "--porcelain"), self.ledger_text()
