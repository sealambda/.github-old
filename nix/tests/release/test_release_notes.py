"""Tests of the text of a release."""

import unittest

from release.notes import MAX_NOTES_BYTES, render_notes

GITHUB_BODY_LIMIT = 125_000
"""The length in characters at which the GitHub API rejects a release body.

The API answers `body is too long (maximum is 125000 characters)`. The number
is an observed message, not a documented limit, and it is typed here on its own
so that the test does not read the constant that it checks.
"""


class RenderNotesTest(unittest.TestCase):
    """The first line is the answer, then one bullet for each commit."""

    def test_changed_rules(self) -> None:
        """The answer `yes` is the first line, then a blank line and bullets."""
        text = render_notes(True, ["feat: add a rule", "fix: repair a rule"])
        self.assertEqual(
            text,
            "rules changed: yes\n\n- `feat: add a rule`\n- `fix: repair a rule`\n",
        )

    def test_unchanged_rules(self) -> None:
        """The answer `no` is the first line."""
        self.assertEqual(
            render_notes(False, ["docs: fix a typo"]),
            "rules changed: no\n\n- `docs: fix a typo`\n",
        )

    def test_default_bound_is_below_the_limit_that_github_reports(self) -> None:
        """The bound stays under the length at which GitHub rejects a body.

        The bound counts bytes and the limit counts characters. A byte count is
        never lower than the character count, so a bound below the limit keeps
        the notes below it.
        """
        self.assertLess(MAX_NOTES_BYTES, GITHUB_BODY_LIMIT)

    def test_notes_at_the_limit_stay_whole(self) -> None:
        """Header 20 bytes and two bullets of 15 bytes fill exactly 50 bytes."""
        subjects = ["aaaaaaaaaa", "bbbbbbbbbb"]
        text = render_notes(True, subjects, limit=50)
        self.assertEqual(text, "rules changed: yes\n\n- `aaaaaaaaaa`\n- `bbbbbbbbbb`\n")

    def test_notes_over_the_limit_keep_the_newest_and_count_the_rest(self) -> None:
        """Five bullets of 15 bytes do not fit in 60 bytes with the last line.

        The last line `older commits omitted: 4` takes 25 bytes, the first
        line and the blank line take 20, so one bullet of 15 bytes fits.
        """
        subjects = [
            "newest0000",
            "second0000",
            "third00000",
            "fourth0000",
            "oldest0000",
        ]
        text = render_notes(True, subjects, limit=60)
        self.assertEqual(
            text,
            "rules changed: yes\n\n- `newest0000`\nolder commits omitted: 4\n",
        )
        self.assertLessEqual(len(text.encode()), 60)

    def test_one_byte_under_the_whole_text_drops_the_bullets_that_cannot_fit(
        self,
    ) -> None:
        """A limit of 49 leaves room for the last line only."""
        text = render_notes(True, ["aaaaaaaaaa", "bbbbbbbbbb"], limit=49)
        self.assertEqual(text, "rules changed: yes\n\nolder commits omitted: 2\n")
        self.assertLessEqual(len(text.encode()), 49)

    def test_limit_counts_bytes_not_characters(self) -> None:
        """A subject of 20 two-byte characters takes 45 bytes with its bullet.

        The whole text is 65 bytes but only 45 characters.
        """
        subject = "é" * 20
        self.assertEqual(
            render_notes(True, [subject], limit=65),
            f"rules changed: yes\n\n- `{subject}`\n",
        )
        self.assertEqual(
            render_notes(True, [subject], limit=64),
            "rules changed: yes\n\nolder commits omitted: 1\n",
        )

    def test_a_subject_longer_than_the_limit_is_omitted(self) -> None:
        """One huge subject gives the first line and the count, not an error."""
        text = render_notes(True, ["x" * 500], limit=100)
        self.assertEqual(text, "rules changed: yes\n\nolder commits omitted: 1\n")

    def test_the_first_release_of_a_long_history_stays_under_the_default(self) -> None:
        """A history of 50000 commits gives notes within the default bound."""
        subjects = [f"feat: change number {number}" for number in range(50_000)]
        text = render_notes(True, subjects)
        lines = text.splitlines()
        self.assertEqual(lines[0], "rules changed: yes")
        self.assertEqual(lines[2], "- `feat: change number 0`")
        self.assertLessEqual(len(text.encode()), MAX_NOTES_BYTES)
        listed = len(lines) - 3
        self.assertEqual(lines[-1], f"older commits omitted: {50_000 - listed}")
        self.assertGreater(listed, 0)

    def test_first_line_is_exactly_the_answer(self) -> None:
        """A reader or a script gets the answer from the first line alone."""
        for answer, word in ((True, "yes"), (False, "no")):
            with self.subTest(answer=answer):
                first = render_notes(answer, ["x"]).splitlines()[0]
                self.assertEqual(first, f"rules changed: {word}")


class SubjectMarkdownTest(unittest.TestCase):
    """A subject is the text of a contributor, so it stays plain text."""

    def bullet(self, subject: str) -> str:
        """Return the one bullet that the notes of `subject` hold."""
        return render_notes(False, [subject]).splitlines()[2]

    def test_a_link_and_a_mention_sit_inside_a_code_span(self) -> None:
        """Markdown that makes a link or a mention is not live in the notes."""
        self.assertEqual(
            self.bullet("[security update](https://attacker.example)"),
            "- `[security update](https://attacker.example)`",
        )
        self.assertEqual(
            self.bullet("fix: ask @sealambda/maintainers"),
            "- `fix: ask @sealambda/maintainers`",
        )

    def test_the_fence_is_longer_than_every_run_of_backticks_in_the_subject(
        self,
    ) -> None:
        """A backtick in the subject cannot end the span early."""
        self.assertEqual(self.bullet("use `foo` here"), "- ``use `foo` here``")
        self.assertEqual(self.bullet("a``b"), "- ```a``b```")

    def test_a_backtick_at_an_end_of_the_subject_gets_a_space_from_the_fence(
        self,
    ) -> None:
        """The padding keeps the backtick of the subject out of the fence."""
        self.assertEqual(self.bullet("`x` first"), "- `` `x` first ``")
        self.assertEqual(self.bullet("last `x`"), "- `` last `x` ``")
