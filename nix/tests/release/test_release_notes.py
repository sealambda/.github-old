"""Tests of the text of a release."""

import unittest

from release.notes import MAX_NOTES_BYTES, render_notes


class RenderNotesTest(unittest.TestCase):
    """The first line is the answer, then one bullet for each commit."""

    def test_changed_rules(self) -> None:
        """The answer `yes` is the first line, then a blank line and bullets."""
        text = render_notes(True, ["feat: add a rule", "fix: repair a rule"])
        self.assertEqual(
            text, "rules changed: yes\n\n- feat: add a rule\n- fix: repair a rule\n"
        )

    def test_unchanged_rules(self) -> None:
        """The answer `no` is the first line."""
        self.assertEqual(
            render_notes(False, ["docs: fix a typo"]),
            "rules changed: no\n\n- docs: fix a typo\n",
        )

    def test_default_bound_is_far_below_the_limit_that_github_reports(self) -> None:
        """GitHub rejects 125000 characters or more, and bytes never undercount."""
        self.assertLessEqual(MAX_NOTES_BYTES, 100_000)

    def test_notes_at_the_limit_stay_whole(self) -> None:
        """Header 20 bytes and two bullets of 13 bytes fill exactly 46 bytes."""
        subjects = ["aaaaaaaaaa", "bbbbbbbbbb"]
        text = render_notes(True, subjects, limit=46)
        self.assertEqual(text, "rules changed: yes\n\n- aaaaaaaaaa\n- bbbbbbbbbb\n")

    def test_notes_over_the_limit_keep_the_newest_and_count_the_rest(self) -> None:
        """Five bullets of 13 bytes do not fit in 60 bytes with the last line.

        The last line `older commits omitted: 4` takes 25 bytes, the first
        line and the blank line take 20, so one bullet of 13 bytes fits.
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
            "rules changed: yes\n\n- newest0000\nolder commits omitted: 4\n",
        )
        self.assertLessEqual(len(text.encode()), 60)

    def test_one_byte_under_the_whole_text_drops_the_bullets_that_cannot_fit(
        self,
    ) -> None:
        """A limit of 45 leaves room for the last line only."""
        text = render_notes(True, ["aaaaaaaaaa", "bbbbbbbbbb"], limit=45)
        self.assertEqual(text, "rules changed: yes\n\nolder commits omitted: 2\n")
        self.assertLessEqual(len(text.encode()), 45)

    def test_limit_counts_bytes_not_characters(self) -> None:
        """A subject of 20 two-byte characters takes 43 bytes with its bullet.

        The whole text is 63 bytes but only 43 characters.
        """
        subject = "é" * 20
        self.assertEqual(
            render_notes(True, [subject], limit=63),
            f"rules changed: yes\n\n- {subject}\n",
        )
        self.assertEqual(
            render_notes(True, [subject], limit=62),
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
        self.assertEqual(lines[2], "- feat: change number 0")
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
