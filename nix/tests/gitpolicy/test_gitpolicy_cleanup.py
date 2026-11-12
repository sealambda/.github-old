"""Tests for the cleaning of a commit message file.

The expected texts are what Git records for the same file: Git drops the
comment lines, the text after the scissors line and the blank lines around the
message. `CleanupAgainstGitTest` records messages with a real Git and compares.
The probe that shows the `commit-msg` hook receiving the comment lines is
`GitHookTest` in `test_gitpolicy_cli.py`.
"""

import os
import stat
import unittest
from unittest import mock

from gitpolicy.cleanup import CleanupMode, clean_commit_message
from gitpolicy_repo import RepoTestCase

SCISSORS = "# ------------------------ >8 ------------------------"

NO_BREAK_SPACE = "\N{NO-BREAK SPACE}"


class CleanCommitMessageTest(unittest.TestCase):
    """`clean_commit_message` returns the message that Git records."""

    def test_message_without_comments_is_unchanged(self) -> None:
        """Text that needs no cleaning comes back without its final newline."""
        self.assertEqual("feat: x\n\nbody", clean_commit_message("feat: x\n\nbody\n"))

    def test_comment_lines_go(self) -> None:
        """A line that starts with `#` is a comment, first or last."""
        text = "# top\nfeat: x\n\nbody\n# Please enter the message\n#\n"
        self.assertEqual("feat: x\n\nbody", clean_commit_message(text))

    def test_hash_inside_a_line_stays(self) -> None:
        """Only a line that starts with `#` is a comment."""
        self.assertEqual("fix: close #12", clean_commit_message("fix: close #12\n"))

    def test_text_after_the_scissors_line_goes(self) -> None:
        """The scissors line of `git commit -v` ends the message."""
        text = f"feat: x\n\nbody\n{SCISSORS}\ndiff --git a/f b/f\n+added\n"
        self.assertEqual("feat: x\n\nbody", clean_commit_message(text))

    def test_blank_lines_around_the_message_go(self) -> None:
        """Leading and trailing blank lines go, and inner ones stay."""
        self.assertEqual(
            "feat: x\n\n\nbody", clean_commit_message("\n\nfeat: x\n\n\nbody\n\n\n")
        )

    def test_trailing_whitespace_of_each_line_goes(self) -> None:
        """Git strips the whitespace at the end of each line."""
        self.assertEqual(
            "feat: x\n\nbody", clean_commit_message("feat: x  \n \nbody\t\n")
        )

    def test_only_comments_leave_an_empty_message(self) -> None:
        """A file of comments is an empty message."""
        self.assertEqual("", clean_commit_message("# one\n# two\n"))
        self.assertEqual("", clean_commit_message(""))

    def test_crlf_line_ends_are_line_ends(self) -> None:
        """A carriage return before the line feed is part of the line end."""
        text = "# top\r\nfeat: x\r\n\r\nbody\r\n# Please enter\r\n"
        self.assertEqual("feat: x\n\nbody", clean_commit_message(text))

    def test_only_line_feed_and_crlf_end_a_line(self) -> None:
        """Other separators stay inside the line, as in Git.

        `str.splitlines` would split at a vertical tab, a form feed and the
        Unicode line separators, and would take a `#` after them for the
        start of a comment line.
        """
        for separator in (
            "\x0b",
            "\x0c",
            "\x1c",
            "\x85",
            "\N{LINE SEPARATOR}",
            "\N{PARAGRAPH SEPARATOR}",
            "\r",
        ):
            with self.subTest(repr(separator)):
                text = f"feat: x{separator}# not a comment\n"
                self.assertEqual(
                    f"feat: x{separator}# not a comment", clean_commit_message(text)
                )

    def test_a_custom_comment_string_replaces_the_hash(self) -> None:
        """With another comment string, only its lines are comments."""
        text = "; top\nfeat: x\n# kept\n;; also a comment\nbody ; kept\n"
        self.assertEqual(
            "feat: x\n# kept\nbody ; kept",
            clean_commit_message(text, CleanupMode.STRIP, ";"),
        )

    def test_a_comment_string_of_several_characters(self) -> None:
        """The whole string must start the line."""
        text = "// a comment\nfeat: x\n/ kept\n"
        self.assertEqual(
            "feat: x\n/ kept", clean_commit_message(text, CleanupMode.STRIP, "//")
        )

    def test_the_scissors_line_uses_the_comment_string(self) -> None:
        """The scissors line starts with the comment string, so `#` is no cut."""
        text = f"feat: x\n{SCISSORS}\n;{SCISSORS.removeprefix('#')}\n+diff\n"
        self.assertEqual(
            f"feat: x\n{SCISSORS}",
            clean_commit_message(text, CleanupMode.SCISSORS, ";"),
        )

    def test_unicode_whitespace_at_the_end_of_a_line_stays(self) -> None:
        """Git does not strip a Unicode space, so a no-break space stays."""
        text = f"feat: x{NO_BREAK_SPACE}"
        self.assertEqual(text, clean_commit_message(f"{text}\n"))


class CleanupModeTest(unittest.TestCase):
    """The modes of `git commit --cleanup` that `commit.cleanup` can name."""

    TEXT = "feat: x\n\n# a note  \nbody  \n\n"

    def test_strip_removes_comments(self) -> None:
        """`strip` drops the comment lines."""
        self.assertEqual(
            "feat: x\n\nbody", clean_commit_message(self.TEXT, CleanupMode.STRIP)
        )

    def test_whitespace_keeps_comments(self) -> None:
        """`whitespace` is `strip` without the removal of comments."""
        self.assertEqual(
            "feat: x\n\n# a note\nbody",
            clean_commit_message(self.TEXT, CleanupMode.WHITESPACE),
        )

    def test_whitespace_keeps_a_comment_as_the_header(self) -> None:
        """A `#` first line is the header when comments stay."""
        text = "# x\nfeat: y\n"
        self.assertEqual(
            "# x\nfeat: y", clean_commit_message(text, CleanupMode.WHITESPACE)
        )

    def test_scissors_cuts_at_the_scissors_line(self) -> None:
        """`scissors` keeps comments above the line and drops the rest."""
        text = f"feat: x\n# note\n{SCISSORS}\n+diff\n"
        self.assertEqual(
            "feat: x\n# note", clean_commit_message(text, CleanupMode.SCISSORS)
        )

    def test_verbatim_changes_nothing(self) -> None:
        """`verbatim` returns the text as it is."""
        self.assertEqual(
            self.TEXT, clean_commit_message(self.TEXT, CleanupMode.VERBATIM)
        )

    def test_mode_values_are_the_names_that_git_defines(self) -> None:
        """The values match the documented `--cleanup` modes."""
        self.assertEqual(
            ["strip", "whitespace", "verbatim", "scissors"],
            [mode.value for mode in CleanupMode],
        )


class CleanupAgainstGitTest(RepoTestCase):
    """The cleaned text equals what `git commit --cleanup=<mode>` stores.

    Git is the oracle here: each test records the same text with Git and
    compares the stored message with the result of `clean_commit_message`.
    The texts have no run of blank lines, which Git collapses and the function
    does not.
    """

    TEXTS = {
        "comments and whitespace": "\n# top\nfeat: x  \n\n# a note\nbody\t\n# end\n\n",
        "form feed and vertical tab": "feat: x\x0c\n\nbody\x0b# kept\n",
        "carriage returns": "feat: x\r\n\r\nbody\r\n",
        "no-break space": f"feat: x{NO_BREAK_SPACE}\n\nbody\n",
    }

    def stored_message(self, arguments: list[str]) -> str:
        """Run `git commit` with the arguments and return the stored message.

        The runner returns the output of Git as written, carriage returns
        included, so the stored message compares with no change of line ends.
        """
        self.git(["commit", "--quiet", "--allow-empty", *arguments])
        return self.git(["log", "-1", "--format=%B"]).rstrip("\n")

    def test_every_mode_matches_git(self) -> None:
        """A message that `--file` gives is cleaned as Git cleans it."""
        path = self.scratch / "message.txt"
        for label, text in self.TEXTS.items():
            path.write_bytes(text.encode("utf-8"))
            for mode in CleanupMode:
                with self.subTest(label, mode=mode.value):
                    stored = self.stored_message(
                        [f"--cleanup={mode.value}", "--file", str(path)]
                    )
                    self.assertEqual(
                        stored, clean_commit_message(text, mode).rstrip("\n")
                    )

    def test_every_mode_matches_git_with_a_custom_comment_string(self) -> None:
        """`core.commentChar` and `core.commentString` set the comment lines."""
        path = self.scratch / "message.txt"
        text = "feat: x\n; a note\n# kept in strip mode too\n//c\n\nbody\n; end\n"
        path.write_text(text, encoding="utf-8")
        for comment in (";", "//"):
            self.git(["config", "core.commentChar", comment])
            for mode in CleanupMode:
                with self.subTest(comment, mode=mode.value):
                    stored = self.stored_message(
                        [f"--cleanup={mode.value}", "--file", str(path)]
                    )
                    cleaned = clean_commit_message(text, mode, comment)
                    self.assertEqual(stored, cleaned.rstrip("\n"))

    def test_scissors_mode_matches_git(self) -> None:
        """The `scissors` mode cuts at the scissors line, as Git does.

        Git cuts the text only for a message that an editor writes, so the test
        records the message through an editor. Without `--verbose`, the `strip`
        and `whitespace` modes of Git keep the text after the line. The tool
        cuts it in every mode but `verbatim`, because the hook cannot see
        whether `--verbose` wrote the text.
        """
        text = f"feat: x\n\n# note\n{SCISSORS}\ndiff --git a/f b/f\n"
        body = self.scratch / "body.txt"
        body.write_text(text, encoding="utf-8")
        editor = self.scratch / "editor.sh"
        editor.write_text(f'#!/bin/sh\ncp "{body}" "$1"\n', encoding="utf-8")
        editor.chmod(editor.stat().st_mode | stat.S_IXUSR)
        with mock.patch.dict(os.environ, {"GIT_EDITOR": str(editor)}):
            stored = self.stored_message(["--cleanup=scissors"])
        self.assertEqual(stored, clean_commit_message(text, CleanupMode.SCISSORS))

    def test_scissors_mode_matches_git_with_a_custom_comment_string(self) -> None:
        """The scissors line of Git starts with the comment string."""
        self.git(["config", "core.commentChar", ";"])
        text = f"feat: x\n\n; note\n;{SCISSORS.removeprefix('#')}\ndiff --git a/f b/f\n"
        body = self.scratch / "body.txt"
        body.write_text(text, encoding="utf-8")
        editor = self.scratch / "editor.sh"
        editor.write_text(f'#!/bin/sh\ncp "{body}" "$1"\n', encoding="utf-8")
        editor.chmod(editor.stat().st_mode | stat.S_IXUSR)
        with mock.patch.dict(os.environ, {"GIT_EDITOR": str(editor)}):
            stored = self.stored_message(["--cleanup=scissors"])
        self.assertEqual(stored, clean_commit_message(text, CleanupMode.SCISSORS, ";"))


if __name__ == "__main__":
    unittest.main()
