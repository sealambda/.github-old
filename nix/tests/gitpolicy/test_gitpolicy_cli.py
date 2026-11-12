"""Tests for the command line of `gitpolicy`: files, exit codes and the hook."""

import os
import stat
import sys
import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path
from unittest import mock

from gitpolicy_repo import RepoTestCase, run_main
from release.runner import CommandError


class CommitMsgCommandTest(RepoTestCase):
    """`gitpolicy commit-msg FILE` checks the message in a file.

    The command reads `commit.cleanup` from the repository, so each test runs
    in the temporary repository of `RepoTestCase`.
    """

    def write(self, text: str) -> Path:
        """Write a message file in the scratch folder and return its path."""
        path = self.scratch / "COMMIT_EDITMSG"
        path.write_text(text, encoding="utf-8")
        return path

    def test_valid_message_with_editor_comments_passes(self) -> None:
        """The comment lines of the editor template are not part of the message."""
        path = self.write("feat: add x\n\nwhy\n# Please enter the message\n#\n")
        result = self.run_cli("commit-msg", str(path))
        self.assertEqual((0, "", ""), (result.code, result.stdout, result.stderr))

    def test_problem_is_printed_with_the_file(self) -> None:
        """A bad header prints `<file>: <problem>` and exits 1."""
        path = self.write("added a thing\n")
        result = self.run_cli("commit-msg", str(path))
        self.assertEqual(1, result.code)
        self.assertTrue(result.stdout.startswith(f"{path}: "), result.stdout)
        self.assertIn("1 problem(s)", result.stderr)

    def test_a_file_of_comments_has_no_header(self) -> None:
        """A message that is all comments is empty."""
        result = self.run_cli("commit-msg", str(self.write("# nothing\n")))
        self.assertEqual(1, result.code)
        self.assertIn("the message has no header", result.stdout)

    def test_autosquash_is_refused_unless_allowed(self) -> None:
        """`--allow-autosquash` lets a `fixup!` header pass."""
        path = str(self.write("fixup! feat: add x\n"))
        self.assertEqual(1, self.run_cli("commit-msg", path).code)
        self.assertEqual(0, self.run_cli("commit-msg", "--allow-autosquash", path).code)

    def test_missing_file_is_a_usage_error(self) -> None:
        """A file that cannot be read gives status 2."""
        result = self.run_cli("commit-msg", str(self.scratch / "absent"))
        self.assertEqual(2, result.code)
        self.assertIn("absent", result.stderr)

    def test_file_that_is_not_utf8_is_a_usage_error(self) -> None:
        """A message that is not UTF-8 text gives status 2, not a traceback."""
        path = self.scratch / "binary"
        path.write_bytes(b"feat: \xff\xfe\n")
        result = self.run_cli("commit-msg", str(path))
        self.assertEqual(2, result.code)
        self.assertIn("not UTF-8 text", result.stderr)

    def test_cleanup_setting_decides_what_a_comment_is(self) -> None:
        """With `commit.cleanup` set to `whitespace` a `#` line stays.

        Git keeps the comment lines of such a commit, so a `#` second line is
        the line that must be blank, and the check fails. With `strip` or no
        setting Git removes it, and the message passes.
        """
        path = str(self.write("feat: x\n# a note\n\nbody\n"))
        self.assertEqual(0, self.run_cli("commit-msg", path).code)
        for value, code in (("strip", 0), ("default", 0), ("whitespace", 1)):
            with self.subTest(value):
                self.git(["config", "commit.cleanup", value])
                self.assertEqual(code, self.run_cli("commit-msg", path).code)

    def test_verbatim_setting_keeps_leading_blank_lines(self) -> None:
        """With `commit.cleanup` set to `verbatim` nothing is removed."""
        self.git(["config", "commit.cleanup", "verbatim"])
        result = self.run_cli("commit-msg", str(self.write("\nfeat: x\n")))
        self.assertEqual(1, result.code)
        self.assertIn("the message has no header", result.stdout)

    def test_unknown_cleanup_setting_is_a_usage_error(self) -> None:
        """A value that Git does not define gives status 2 and names it."""
        self.git(["config", "commit.cleanup", "tidy"])
        result = self.run_cli("commit-msg", str(self.write("feat: x\n")))
        self.assertEqual(2, result.code)
        self.assertIn("commit.cleanup has the unknown value 'tidy'", result.stderr)

    def write_bytes(self, content: bytes) -> str:
        """Write a message file of raw bytes in the scratch folder, return its path."""
        path = self.scratch / "COMMIT_EDITMSG"
        path.write_bytes(content)
        return str(path)

    def test_a_lone_carriage_return_is_not_a_line_end(self) -> None:
        r"""Git ends a line at a line feed only, so a `\r` stays inside its line.

        `feat: x\rbody` is one line for Git, and a header with no body. A read
        in text mode would make two lines of it and refuse it for the missing
        blank line. In the second message the `#` does not start a line, so it
        is no comment: a text mode read would strip it, and the header would
        end with a period.
        """
        for label, content in (
            ("body after a carriage return", b"feat: x\rbody\n"),
            ("hash after a carriage return", b"feat: x.\r# note\n"),
        ):
            with self.subTest(label):
                result = self.run_cli("commit-msg", self.write_bytes(content))
                self.assertEqual((0, ""), (result.code, result.stdout))

    def test_crlf_line_ends_are_line_ends(self) -> None:
        r"""A `\r\n` ends a line, and Git strips its `\r` as trailing space."""
        path = self.write_bytes(b"feat: x\r\n\r\nbody\r\n# Please enter\r\n")
        self.assertEqual(0, self.run_cli("commit-msg", path).code)
        result = self.run_cli("commit-msg", self.write_bytes(b"feat: x.\r\n"))
        self.assertEqual(1, result.code)
        self.assertIn("must not end with a period", result.stdout)
        self.assertNotIn("trailing whitespace", result.stdout)

    def test_a_custom_comment_character_decides_what_a_comment_is(self) -> None:
        """With `core.commentChar` set, that character starts a comment line."""
        self.git(["config", "core.commentChar", ";"])
        accepted = str(self.write("feat: x\n; a note\n\nbody\n"))
        self.assertEqual(0, self.run_cli("commit-msg", accepted).code)
        refused = str(self.write("feat: x\n# not a comment now\n\nbody\n"))
        result = self.run_cli("commit-msg", refused)
        self.assertEqual(1, result.code)
        self.assertIn("second line must be blank", result.stdout)

    def test_a_comment_string_of_several_characters_is_read(self) -> None:
        """`core.commentString` takes a string, and so does `core.commentChar`."""
        for key in ("core.commentString", "core.commentChar"):
            with self.subTest(key):
                self.git(["config", key, "//"])
                path = str(self.write("feat: x\n// a note\n\nbody\n"))
                self.assertEqual(0, self.run_cli("commit-msg", path).code)
                self.git(["config", "--unset", key])

    def test_the_comment_setting_that_comes_last_wins(self) -> None:
        """`core.commentChar` and `core.commentString` are aliases: last wins."""
        self.git(["config", "core.commentChar", ";"])
        self.git(["config", "core.commentString", "//"])
        path = str(self.write("feat: x\n// a note\n\nbody\n"))
        self.assertEqual(0, self.run_cli("commit-msg", path).code)
        path = str(self.write("feat: x\n; a note\n\nbody\n"))
        self.assertEqual(1, self.run_cli("commit-msg", path).code)

    def test_an_auto_comment_character_is_a_usage_error(self) -> None:
        """`auto` cannot be resolved by a hook: status 2, a message, no guess.

        Git chooses the character when it commits and does not pass it on. The
        message names the two ways out. `verbatim` needs no comment string, so
        it works with `auto`.
        """
        self.git(["config", "core.commentChar", "auto"])
        path = str(self.write("feat: x\n"))
        result = self.run_cli("commit-msg", path)
        self.assertEqual(2, result.code)
        self.assertIn("core.commentChar is 'auto'", result.stderr)
        self.assertIn("commit.cleanup", result.stderr)
        self.git(["config", "commit.cleanup", "verbatim"])
        self.assertEqual(0, self.run_cli("commit-msg", path).code)

    def test_an_empty_comment_string_is_a_usage_error(self) -> None:
        """Git refuses an empty comment string, and so does the tool."""
        self.git(["config", "core.commentChar", ""])
        result = self.run_cli("commit-msg", str(self.write("feat: x\n")))
        self.assertEqual(2, result.code)
        self.assertIn("core.commentChar is empty", result.stderr)


class CarriageReturnAgreementTest(RepoTestCase):
    r"""`commit-msg` and `range` read one message the same way, as Git does.

    Each message is stored with its bytes unchanged, and the hook reads the same
    bytes from a file with `commit.cleanup` set to `verbatim`, so that neither
    command cleans anything. The expected status is what the rules give for the
    lines that Git sees: it splits lines at `\n` only, so a lone `\r` belongs
    to its line.
    """

    MESSAGES = {
        "body after a carriage return": (b"feat: x\rbody\n", 0),
        "hash after a carriage return": (b"feat: x\r# not a comment\n", 0),
        "carriage return opens the second line": (b"feat: x\n\rbody\n", 1),
        "carriage return alone is a blank line": (b"feat: x\n\r\nbody\n", 0),
        "carriage return ends the header": (b"feat: x\r\n\r\nbody\n", 1),
    }

    def test_both_commands_give_the_status_of_the_lines_that_git_sees(self) -> None:
        """The hook and the range check agree with each other and with the table."""
        self.git(["config", "commit.cleanup", "verbatim"])
        self.commit("chore: start")
        path = self.scratch / "COMMIT_EDITMSG"
        for label, (content, expected) in self.MESSAGES.items():
            with self.subTest(label):
                self.commit_bytes(content)
                path.write_bytes(content)
                hook = self.run_cli("commit-msg", str(path)).code
                stored = self.run_cli("range", "HEAD~1..HEAD").code
                self.assertEqual((expected, expected), (hook, stored))


class UsageTest(unittest.TestCase):
    """A wrong command line gives status 2 and a message."""

    def test_missing_command(self) -> None:
        """No command is a usage error."""
        result = run_main([])
        self.assertEqual(2, result.code)
        self.assertIn("arguments are required: COMMAND", result.stderr)

    def test_unknown_command(self) -> None:
        """An unknown command is a usage error."""
        result = run_main(["lint"])
        self.assertEqual(2, result.code)
        self.assertIn("invalid choice", result.stderr)

    def test_missing_argument(self) -> None:
        """`range` and `commit-msg` need their argument."""
        for command, name in (("range", "A..B"), ("commit-msg", "FILE")):
            with self.subTest(command):
                result = run_main([command])
                self.assertEqual(2, result.code)
                self.assertIn(f"arguments are required: {name}", result.stderr)

    def test_unknown_option(self) -> None:
        """An option that the command does not have is a usage error."""
        self.assertEqual(2, run_main(["branch", "--no-such-option"]).code)

    def test_help_prints_the_help_and_exits_zero(self) -> None:
        """`--help` and `-h` print the usage on standard output: status 0."""
        for argv in (
            ["--help"],
            ["-h"],
            ["branch", "--help"],
            ["branch", "-h"],
            ["range", "--help"],
            ["commit-msg", "-h"],
        ):
            with self.subTest(argv):
                result = run_main(argv)
                self.assertEqual(0, result.code, result.stderr)
                self.assertIn("usage: gitpolicy", result.stdout)
                self.assertEqual("", result.stderr)

    def test_abbreviated_option_is_a_usage_error(self) -> None:
        """`--he` is not `--help`: options are spelled in full."""
        for argv in (["branch", "--he"], ["--he"], ["commit-msg", "--allow", "f"]):
            with self.subTest(argv):
                result = run_main(argv)
                self.assertEqual(2, result.code, result.stdout)
                self.assertEqual("", result.stdout)
                self.assertIn("gitpolicy", result.stderr)

    def test_internal_error_has_its_own_status(self) -> None:
        """An unexpected exception gives status 3 and a traceback."""
        with mock.patch("gitpolicy.cli._run", side_effect=RuntimeError("boom")):
            result = run_main(["branch", "fix/x"])
        self.assertEqual(3, result.code)
        self.assertIn("RuntimeError: boom", result.stderr)
        self.assertIn("internal error", result.stderr)

    def test_git_that_is_missing_is_a_usage_error(self) -> None:
        """A failing git command gives status 2, never a traceback."""

        def failing_git(args: Sequence[str], *, stdin: str | None = None) -> str:
            """Fail as a missing `git` does."""
            raise CommandError("git is not installed or not on PATH")

        result = run_main(["range", "a..b"], failing_git)
        self.assertEqual(2, result.code)
        self.assertIn("git is not installed", result.stderr)

    def test_commit_msg_needs_git_to_read_the_setting(self) -> None:
        """`commit-msg` asks git for `commit.cleanup`: no git gives status 2."""

        def failing_git(args: Sequence[str], *, stdin: str | None = None) -> str:
            """Fail as a missing `git` does."""
            raise CommandError("git is not installed or not on PATH")

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "COMMIT_EDITMSG"
            path.write_text("feat: x\n", encoding="utf-8")
            result = run_main(["commit-msg", str(path)], failing_git)
        self.assertEqual(2, result.code)
        self.assertIn("git is not installed", result.stderr)


class GitHookTest(RepoTestCase):
    """The tool, installed as a real `commit-msg` hook, gates `git commit`.

    Git gives the hook the message file before it cleans the file up, so the
    file still holds the comment lines of the editor. These tests prove that the
    tool copes with that, which no test of the pure rules can.
    """

    def setUp(self) -> None:
        """Install a `commit-msg` hook that runs the tool, and an editor."""
        super().setUp()
        self.enterContext(
            mock.patch.dict(
                os.environ, {"PYTHONPATH": os.pathsep.join(p for p in sys.path if p)}
            )
        )
        hook = self.root / ".git" / "hooks" / "commit-msg"
        hook.parent.mkdir(exist_ok=True)
        hook.write_text(
            f'#!/bin/sh\nexec "{sys.executable}" -m gitpolicy commit-msg '
            '--allow-autosquash "$1"\n',
            encoding="utf-8",
        )
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR)

    def commit_through_editor(self, message: str, comment: str = "#") -> None:
        """Run `git commit` with an editor that writes `message` and a comment.

        Args:
            message: The text that the editor writes first.
            comment: The string that starts the comment line that the editor
                writes after the message, as the template of Git does.

        Raises:
            CommandError: The hook refused the commit.
        """
        body = self.scratch / "body.txt"
        body.write_text(f"{message}\n{comment} Please enter the commit message\n")
        editor = self.scratch / "editor.sh"
        editor.write_text(f'#!/bin/sh\ncp "{body}" "$1"\n')
        editor.chmod(editor.stat().st_mode | stat.S_IXUSR)
        with mock.patch.dict(os.environ, {"GIT_EDITOR": str(editor)}):
            self.git(["commit", "--quiet", "--allow-empty"])

    def subjects(self) -> list[str]:
        """Return the subjects of the commits of the repository."""
        return self.git(["log", "--format=%s"]).splitlines()

    def test_valid_message_is_committed(self) -> None:
        """A message with a valid header gets through, comments and all."""
        self.commit_through_editor("feat: add x\n\nwhy")
        self.assertEqual(["feat: add x"], self.subjects())

    def test_invalid_message_is_refused(self) -> None:
        """The hook stops a commit with a bad header: no commit is made."""
        with self.assertRaises(CommandError):
            self.commit_through_editor("added a thing")
        self.assertEqual([], self.subjects_or_empty())

    def test_autosquash_commit_passes_the_hook(self) -> None:
        """A commit made by `git commit --fixup` gets through."""
        self.commit_through_editor("feat: add x")
        self.git(["commit", "--quiet", "--allow-empty", "--fixup", "HEAD"])
        self.assertEqual(["fixup! feat: add x", "feat: add x"], self.subjects())

    def test_hook_follows_the_cleanup_setting(self) -> None:
        """With `commit.cleanup=whitespace` the hook sees the `#` line, as Git does.

        Git keeps the line in the stored message, so it is the second line and
        breaks the rule of the blank line: the hook refuses the commit that the
        range check would refuse later.
        """
        self.git(["config", "commit.cleanup", "whitespace"])
        with self.assertRaises(CommandError):
            self.git(
                ["commit", "--quiet", "--allow-empty", "-m", "feat: x\n# note\n\nbody"]
            )
        self.assertEqual([], self.subjects_or_empty())

    def commit_file(self, content: bytes) -> None:
        """Run `git commit --file` on a file of raw bytes.

        Raises:
            CommandError: The hook refused the commit.
        """
        path = self.scratch / "message.txt"
        path.write_bytes(content)
        self.git(["commit", "--quiet", "--allow-empty", "--file", str(path)])

    def test_messages_with_carriage_returns_pass_the_hook_and_the_range(self) -> None:
        """A message that the hook lets in does not fail the range check later.

        The first two messages hold a lone carriage return: for Git it is part
        of the line, so no line is a comment and no blank line is missing. The
        third uses CRLF line ends, and Git strips the carriage return of each.
        """
        base = self.commit("chore: start")
        for label, content in (
            ("hash after a carriage return", b"feat: x\r# not a comment\n"),
            ("body after a carriage return", b"feat: y\rbody\n"),
            ("CRLF line ends", b"feat: z\r\n\r\nbody\r\n"),
        ):
            with self.subTest(label):
                self.commit_file(content)
        self.assertEqual(3, len(self.git(["rev-list", f"{base}..HEAD"]).split()))
        result = self.run_cli("range", f"{base}..HEAD")
        self.assertEqual((0, ""), (result.code, result.stdout), result.stderr)

    def test_hook_follows_a_custom_comment_character(self) -> None:
        """With `core.commentChar` set, Git strips that character's lines.

        The line `; a note` is a comment for Git, so the stored message has a
        blank second line, and the hook must see the same message.
        """
        self.git(["config", "core.commentChar", ";"])
        self.commit_through_editor("feat: x\n; a note\n\nbody", comment=";")
        self.assertEqual(
            "feat: x\n\nbody", self.git(["log", "-1", "--format=%B"]).strip()
        )
        self.assertEqual(["feat: x"], self.subjects())

    def test_hook_keeps_a_hash_line_when_the_comment_character_is_another(
        self,
    ) -> None:
        """Git keeps `# note` as the second line, so the hook refuses it.

        With the default character the same text would pass, because `#` would
        start a comment.
        """
        self.git(["config", "core.commentChar", ";"])
        with self.assertRaises(CommandError):
            self.commit_through_editor("feat: x\n# note\n\nbody", comment=";")
        self.assertEqual([], self.subjects_or_empty())

    def test_hook_reads_a_comment_string_of_several_characters(self) -> None:
        """`core.commentString`, set after `core.commentChar`, is the one in force."""
        self.git(["config", "core.commentChar", ";"])
        self.git(["config", "core.commentString", "//"])
        self.commit_through_editor("feat: x\n// a note\n\nbody", comment="//")
        self.assertEqual(
            "feat: x\n\nbody", self.git(["log", "-1", "--format=%B"]).strip()
        )

    def test_message_option_without_a_setting_is_the_known_difference(self) -> None:
        """The hook cannot tell `--message` from an editor: that difference stays.

        Without `commit.cleanup` the hook assumes the editor and strips the `#`
        line. Git keeps it for `--message`, so the stored message fails the range
        check. `docs/reference/git-policy.md` documents this case.
        """
        base = self.commit("chore: start")
        self.git(["commit", "--quiet", "--allow-empty", "-m", "feat: x\n# note\n\nb"])
        self.assertIn("# note", self.git(["log", "-1", "--format=%B"]))
        result = self.run_cli("range", f"{base}..HEAD")
        self.assertEqual(1, result.code)
        self.assertIn("second line must be blank", result.stdout)

    def subjects_or_empty(self) -> list[str]:
        """Return the subjects, or an empty list when there is no commit yet."""
        try:
            return self.subjects()
        except CommandError:
            return []


if __name__ == "__main__":
    unittest.main()
