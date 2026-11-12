"""Tests for `gitpolicy range` and `gitpolicy branch` on temporary repositories.

Each test builds a real repository, so these tests check how the tool reads
the history of Git, not only the rules: the order of the commits, the range
`A..B`, merge commits and the branch that is checked out.
"""

import unittest
from collections.abc import Sequence

from gitpolicy_repo import RepoTestCase, run_main


class RangeTest(RepoTestCase):
    """`gitpolicy range A..B` checks the commits that B reaches and A does not."""

    def test_clean_range_exits_zero_and_prints_nothing(self) -> None:
        """Commits that follow the policy give no output."""
        base = self.commit("chore: start")
        self.commit("feat: add a")
        self.commit("fix(b): repair b\n\nWhy it broke.")
        result = self.run_cli("range", f"{base}..HEAD")
        self.assertEqual((0, "", ""), (result.code, result.stdout, result.stderr))

    def test_bad_commit_is_named_by_its_short_hash(self) -> None:
        """A failing commit prints `<short hash>: <problem>` and exits 1."""
        base = self.commit("chore: start")
        bad = self.commit("Add a thing")
        result = self.run_cli("range", f"{base}..HEAD")
        self.assertEqual(1, result.code)
        self.assertEqual(1, len(result.stdout.splitlines()), result.stdout)
        self.assertTrue(result.stdout.startswith(f"{bad[:7]}: "), result.stdout)
        self.assertIn("type(scope)!: description", result.stdout)
        self.assertIn("1 problem(s)", result.stderr)

    def test_commits_before_the_range_start_are_not_checked(self) -> None:
        """The base commit and its ancestors are outside `A..B`."""
        self.commit("not a conventional commit")
        base = self.commit("also not one")
        self.commit("feat: fine")
        self.assertEqual(0, self.run_cli("range", f"{base}..HEAD").code)

    def test_every_bad_commit_is_reported_oldest_first(self) -> None:
        """One run reports all failing commits, the oldest first."""
        base = self.commit("chore: start")
        first = self.commit("bad one")
        self.commit("feat: good")
        second = self.commit("Bad two.")
        lines = self.run_cli("range", f"{base}..HEAD").stdout.splitlines()
        prefixes = [line.split(":")[0] for line in lines]
        self.assertEqual([first[:7], second[:7]], prefixes)

    def test_fixup_commit_fails_in_range_mode(self) -> None:
        """A `fixup!` commit that reached the history is a problem."""
        base = self.commit("chore: start")
        target = self.commit("feat: add a")
        self.commit(f"fixup! feat: add a ({target[:7]})")
        result = self.run_cli("range", f"{base}..HEAD")
        self.assertEqual(1, result.code)
        self.assertIn("git rebase --autosquash", result.stdout)

    def test_empty_range_is_clean(self) -> None:
        """A range with no commit has nothing to check."""
        self.commit("chore: start")
        result = self.run_cli("range", "HEAD..HEAD")
        self.assertEqual((0, ""), (result.code, result.stdout))

    def test_merge_commit_fails(self) -> None:
        """A merge commit has a header that is not a Conventional Commit."""
        base = self.commit("chore: start")
        self.git(["switch", "--quiet", "--create", "feat/side"])
        self.commit("feat: on the side")
        self.git(["switch", "--quiet", "main"])
        self.commit("fix: on main")
        self.git(
            ["merge", "--quiet", "--no-ff", "--message", "Merge branch", "feat/side"]
        )
        result = self.run_cli("range", f"{base}..main")
        self.assertEqual(1, result.code)
        self.assertEqual(1, len(result.stdout.splitlines()), result.stdout)
        self.assertIn("merge commit", result.stdout)
        self.assertIn("rebase the branch", result.stdout)

    def test_merge_commit_with_a_valid_header_fails(self) -> None:
        """A merge commit fails for being a merge, not for its message."""
        base = self.commit("chore: start")
        self.git(["switch", "--quiet", "--create", "feat/side"])
        self.commit("feat: on the side")
        self.git(["switch", "--quiet", "main"])
        self.commit("fix: on main")
        self.git(
            [
                "merge",
                "--quiet",
                "--no-ff",
                "--message",
                "chore: merge the side",
                "feat/side",
            ]
        )
        result = self.run_cli("range", f"{base}..main")
        self.assertEqual(1, result.code)
        self.assertIn("merge commit", result.stdout)

    def test_message_that_is_not_utf8_is_a_problem_of_its_commit(self) -> None:
        """A commit with bytes that are not UTF-8 gives status 1, not a crash.

        The other commits of the range are still checked.
        """
        base = self.commit("chore: start")
        broken = self.commit_bytes(b"feat: calf\xe9 \xff\xfe\n")
        bad = self.commit("Add a thing")
        result = self.run_cli("range", f"{base}..HEAD")
        self.assertEqual(1, result.code, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(2, len(lines), result.stdout)
        self.assertTrue(lines[0].startswith(f"{broken[:7]}: "), lines[0])
        self.assertIn("not valid UTF-8", lines[0])
        self.assertTrue(lines[1].startswith(f"{bad[:7]}: "), lines[1])
        self.assertIn("2 problem(s)", result.stderr)

    def test_message_in_another_declared_encoding_is_read(self) -> None:
        """Git re-encodes a message that declares its encoding, so it passes."""
        base = self.commit("chore: start")
        self.commit_bytes("feat: café\n".encode("latin-1"), encoding="ISO-8859-1")
        self.assertEqual("ISO-8859-1", self.git(["log", "-1", "--format=%e"]).strip())
        result = self.run_cli("range", f"{base}..HEAD")
        self.assertEqual((0, ""), (result.code, result.stdout), result.stderr)

    def test_the_signature_setting_of_the_reader_does_not_change_the_message(
        self,
    ) -> None:
        """`log.showSignature` adds a line to `git log`, and not to the message.

        Without `--no-show-signature` the result of the check is the first line
        of the text that `range` reads, and every signed commit fails.
        """
        base = self.commit("chore: start")
        self.commit_bytes(b"feat: signed\n", signature=True)
        self.use_stub_verifier()
        shown = self.git(["log", "-1", "--format=%B"])
        self.assertTrue(shown.startswith("gpg: Good signature"), shown)
        result = self.run_cli("range", f"{base}..HEAD")
        self.assertEqual((0, ""), (result.code, result.stdout), result.stderr)

    def test_the_output_encoding_of_the_reader_does_not_change_the_message(
        self,
    ) -> None:
        """`i18n.logOutputEncoding` re-encodes `git log`, and not the message.

        Without `--encoding=UTF-8` the header below reaches the tool as Latin-1
        bytes and the commit gets the problem "not valid UTF-8".
        """
        base = self.commit("chore: start")
        self.commit("feat: café")
        self.git(["config", "i18n.logOutputEncoding", "ISO-8859-1"])
        with self.assertRaises(UnicodeDecodeError):
            self.git(["log", "-1", "--format=%B"])
        result = self.run_cli("range", f"{base}..HEAD")
        self.assertEqual((0, ""), (result.code, result.stdout), result.stderr)

    def test_commit_with_an_empty_message_is_a_problem(self) -> None:
        """A commit with no message has no header, and the check reports it."""
        base = self.commit("chore: start")
        empty = self.commit_bytes(b"")
        result = self.run_cli("range", f"{base}..HEAD")
        self.assertEqual(1, result.code)
        self.assertEqual(f"{empty[:7]}: the message has no header\n", result.stdout)

    def test_body_line_that_starts_with_a_hash_is_not_a_comment(self) -> None:
        """Stored messages keep `#` lines, so range mode does not strip them."""
        base = self.commit("chore: start")
        self.commit("docs: add a page\n\n# Not a comment\nbody")
        self.assertEqual(0, self.run_cli("range", f"{base}..HEAD").code)

    def test_body_without_a_blank_line_fails(self) -> None:
        """The blank-line rule applies to commits that Git already stores."""
        base = self.commit("chore: start")
        self.commit("feat: x\nbody right after")
        result = self.run_cli("range", f"{base}..HEAD")
        self.assertEqual(1, result.code)
        self.assertIn("second line must be blank", result.stdout)

    def test_unknown_revision_is_a_usage_error(self) -> None:
        """A revision that does not exist makes git fail: status 2."""
        self.commit("chore: start")
        result = self.run_cli("range", "nosuchbranch..HEAD")
        self.assertEqual(2, result.code)
        self.assertIn("nosuchbranch", result.stderr)

    def test_range_must_have_two_dots(self) -> None:
        """A single revision and a three-dot range are refused."""
        self.commit("chore: start")
        for spec in ("HEAD", "HEAD...HEAD"):
            with self.subTest(spec):
                result = self.run_cli("range", spec)
                self.assertEqual(2, result.code)
                self.assertIn("A..B", result.stderr)

    def test_range_needs_both_sides(self) -> None:
        """`..HEAD` and `<sha>..` are usage errors: Git reads an empty side as HEAD."""
        base = self.commit("chore: start")
        self.commit("Add a thing")
        for spec in ("..HEAD", f"{base}..", ".."):
            with self.subTest(spec):
                result = self.run_cli("range", spec)
                self.assertEqual(2, result.code, result.stdout)
                self.assertEqual("", result.stdout)
                self.assertIn("A..B", result.stderr)

    def test_a_side_that_starts_with_a_dash_is_a_usage_error(self) -> None:
        """A side like `--output=file` is never handed to Git."""
        self.commit("chore: start")
        for spec in ("--output=x..HEAD", "HEAD..--output=x", "-n1..HEAD"):
            with self.subTest(spec):
                result = self.run_cli("range", "--", spec)
                self.assertEqual(2, result.code, result.stdout)
                self.assertIn("must not start with '-'", result.stderr)
        self.assertFalse((self.root / "x").exists())


class RangeGitCallTest(unittest.TestCase):
    """The tool ends the options of git before the range it passes."""

    def test_range_follows_end_of_options(self) -> None:
        """`--end-of-options` stands before the range in the listing call."""
        calls: list[list[str]] = []

        def recording_git(args: Sequence[str], *, stdin: str | None = None) -> str:
            """Record the arguments and list no commit."""
            calls.append(list(args))
            return ""

        self.assertEqual(0, run_main(["range", "a..b"], recording_git).code)
        self.assertEqual(1, len(calls))
        self.assertLess(
            calls[0].index("--end-of-options"), calls[0].index("a..b"), calls[0]
        )


class BranchTest(RepoTestCase):
    """`gitpolicy branch [NAME]` checks a name or the checked-out branch."""

    def test_checked_out_branch_is_read_from_git(self) -> None:
        """Without a name, the tool checks the branch of HEAD."""
        self.commit("chore: start")
        self.git(["switch", "--quiet", "--create", "Bad_Name"])
        result = self.run_cli("branch")
        self.assertEqual(1, result.code)
        self.assertTrue(result.stdout.startswith("Bad_Name: "), result.stdout)

    def test_main_passes(self) -> None:
        """The trunk is a valid name."""
        self.commit("chore: start")
        self.assertEqual((0, ""), self.outcome("branch"))

    def test_valid_checked_out_branch_passes(self) -> None:
        """A branch of the form `<type>/<slug>` passes."""
        self.commit("chore: start")
        self.git(["switch", "--quiet", "--create", "feat/git-policy"])
        self.assertEqual((0, ""), self.outcome("branch"))

    def test_name_argument_replaces_the_checked_out_branch(self) -> None:
        """A given name is checked, whatever branch is checked out."""
        self.commit("chore: start")
        self.assertEqual((0, ""), self.outcome("branch", "fix/something"))
        self.assertEqual(1, self.run_cli("branch", "feature/something").code)

    def test_an_empty_name_is_a_bad_name(self) -> None:
        """An explicit empty name is checked as a name, not read as a missing one.

        The checked-out branch here is valid, so a run that fell back to it
        would pass.
        """
        self.commit("chore: start")
        self.git(["switch", "--quiet", "--create", "feat/fine"])
        result = self.run_cli("branch", "")
        self.assertEqual(1, result.code, result.stderr)
        self.assertIn("<type>/<slug>", result.stdout)
        self.assertEqual(1, len(result.stdout.splitlines()), result.stdout)

    def test_an_empty_name_is_a_bad_name_on_a_detached_head(self) -> None:
        """An empty name is a bad name, not the usage error of a detached HEAD."""
        self.commit("chore: start")
        self.git(["switch", "--quiet", "--detach"])
        self.assertEqual(1, self.run_cli("branch", "").code)

    def test_detached_head_needs_a_name(self) -> None:
        """A detached HEAD has no branch: status 2 and a hint."""
        self.commit("chore: start")
        self.git(["switch", "--quiet", "--detach"])
        result = self.run_cli("branch")
        self.assertEqual(2, result.code)
        self.assertIn("HEAD is detached", result.stderr)
        self.assertEqual(0, self.run_cli("branch", "fix/x").code)

    def test_name_that_starts_with_a_dash_is_a_bad_name_after_double_dash(self) -> None:
        """After `--` a name like `--help` is a name, and the check rejects it."""
        self.commit("chore: start")
        for name in ("--help", "-h", "--he", "-x/y", "--no-such-option"):
            with self.subTest(name):
                result = self.run_cli("branch", "--", name)
                self.assertEqual(1, result.code, result.stderr)
                self.assertTrue(result.stdout.startswith(f"{name}: "), result.stdout)

    def test_name_that_starts_with_a_dash_needs_double_dash(self) -> None:
        """Without `--` the dash makes the name an option: help or usage error."""
        self.commit("chore: start")
        self.assertEqual(0, self.run_cli("branch", "--help").code)
        self.assertEqual(2, self.run_cli("branch", "--he").code)
        self.assertEqual(2, self.run_cli("branch", "-x/y").code)

    def test_a_branch_name_that_is_not_utf8_is_a_usage_error(self) -> None:
        """A name that Git prints as bytes outside UTF-8 gives status 2.

        The run is not an internal error: the status 3 is for bugs of the tool.
        """
        self.commit("chore: start")
        (self.root / ".git" / "HEAD").write_bytes(b"ref: refs/heads/caf\xe9\n")
        result = self.run_cli("branch")
        self.assertEqual(2, result.code, result.stderr)
        self.assertIn("not UTF-8", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def outcome(self, *args: str) -> tuple[int, str]:
        """Run the CLI and return the exit status and the standard output."""
        result = self.run_cli(*args)
        return result.code, result.stdout
