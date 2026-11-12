"""Helpers for the gitpolicy tests: a temporary git repository and a CLI runner."""

import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

from gitpolicy.cli import main
from gitpolicy.history import git_runner
from release.runner import Runner


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


def run_main(argv: list[str], git: Runner | None = None) -> CliResult:
    """Run `gitpolicy.cli.main` and capture its output.

    Args:
        argv: The arguments after the program name.
        git: The runner of git, or `None` for git in the current directory.
    """
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(argv, git=git)
    return CliResult(code, stdout.getvalue(), stderr.getvalue())


class RepoTestCase(unittest.TestCase):
    """A test case with a git repository in `self.root`.

    Git runs with a private `HOME` and no system or global configuration, so
    the settings of the person who runs the tests cannot change a result:
    signing is off, no hook is installed and the identity is fixed. The
    repository starts on the branch `main` with no commit.

    Attributes:
        root: The work tree of the repository.
        git: A runner of git in the work tree.
        scratch: A folder outside the work tree, for files that a test writes.
    """

    root: Path
    git: Runner
    scratch: Path

    def setUp(self) -> None:
        """Create an isolated, empty repository on the branch `main`."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        (base / "home").mkdir()
        self.root = base / "work"
        self.root.mkdir()
        self.scratch = base / "scratch"
        self.scratch.mkdir()
        self.enterContext(
            mock.patch.dict(
                os.environ,
                {
                    "HOME": str(base / "home"),
                    "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_CONFIG_NOSYSTEM": "1",
                },
            )
        )
        self.git = git_runner(["git", "-C", str(self.root)])
        self.git(["init", "--quiet", "--initial-branch=main"])
        for key, value in (
            ("user.name", "Test Maker"),
            ("user.email", "maker@example.com"),
        ):
            self.git(["config", key, value])

    def commit(self, message: str) -> str:
        """Record an empty commit with a message and return its hash.

        The message is stored as it is: Git does not strip comment lines from
        a message that `--message` gives.
        """
        self.git(["commit", "--quiet", "--allow-empty", "--message", message])
        return self.git(["rev-parse", "HEAD"]).strip()

    def commit_bytes(
        self,
        message: bytes,
        *,
        encoding: str | None = None,
        signature: bool = False,
    ) -> str:
        """Record an empty commit with a message of raw bytes, return its hash.

        `git commit` and `git commit-tree` convert a message that is not UTF-8
        text, so the helper writes the commit object itself with
        `git hash-object` and moves the current branch to it. The new commit
        has the tree of HEAD and HEAD as its parent, so the repository needs a
        commit already.

        Args:
            message: The bytes of the message, stored as they are. A NUL byte
                is allowed: Git refuses it in a commit that it checks, so the
                helper then writes the object with `--literally`.
            encoding: The value of an `encoding` header, or `None` for none.
            signature: Whether the commit carries a `gpgsig` header. The
                signature is a placeholder: only a verifier that accepts it,
                as `use_stub_verifier` installs, makes Git print a result.
        """
        parent = self.git(["rev-parse", "HEAD"]).strip()
        tree = self.git(["rev-parse", "HEAD^{tree}"]).strip()
        person = "Test Maker <maker@example.com> 1700000000 +0000"
        headers = [f"tree {tree}", f"parent {parent}"]
        headers += [f"author {person}", f"committer {person}"]
        if encoding:
            headers.append(f"encoding {encoding}")
        if signature:
            headers += [
                "gpgsig -----BEGIN PGP SIGNATURE-----",
                " ",
                " placeholder",
                " -----END PGP SIGNATURE-----",
            ]
        literally = ["--literally"] if b"\0" in message else []  # skips the fsck
        completed = subprocess.run(
            ["git", "-C", str(self.root), "hash-object", "-t", "commit", "-w"]
            + [*literally, "--stdin"],
            input="\n".join(headers).encode() + b"\n\n" + message,
            capture_output=True,
            check=True,
        )
        sha = completed.stdout.decode().strip()
        self.git(["update-ref", "HEAD", sha])
        return sha

    def use_stub_verifier(self) -> None:
        """Make `git log` print a signature result, as `log.showSignature` does.

        The repository gets `log.showSignature=true` and a `gpg.program` that
        accepts every signature and prints one line of result. The stub speaks
        the status protocol of GnuPG, so no key and no GnuPG are needed.
        """
        stub = self.scratch / "verifier"
        fingerprint = "0" * 40
        validsig = f"[GNUPG:] VALIDSIG {fingerprint} 2023-11-14 1700000000 0 4 0 1 8 00"
        stub.write_text(
            "#!/bin/sh\n"
            "echo '[GNUPG:] GOODSIG 0000000000000000 Stub Signer'\n"
            f"echo '{validsig} {fingerprint}'\n"
            "echo '[GNUPG:] TRUST_ULTIMATE 0 pgp'\n"
            "echo 'gpg: Good signature from \"Stub Signer\"' >&2\n",
            encoding="utf-8",
        )
        stub.chmod(0o755)
        self.git(["config", "gpg.program", str(stub)])
        self.git(["config", "log.showSignature", "true"])

    def run_cli(self, *args: str) -> CliResult:
        """Run `gitpolicy.cli.main` on the repository and capture its output."""
        return run_main(list(args), self.git)
