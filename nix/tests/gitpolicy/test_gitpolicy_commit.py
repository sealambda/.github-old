"""Tests for the commit message rules.

The expected results come from the Conventional Commits 1.0.0 grammar and from
the hub's limits: a type from the list in lower case, a header of at most 100
characters with no final period, and a blank line before the body. The limit
of 100 is the `header-max-length` of the `config-conventional` preset of
commitlint.
"""

import unittest

from gitpolicy.commit import check_commit_message, check_stored_commit
from gitpolicy.vocabulary import BRANCH_TYPES, COMMIT_TYPES

NINE_TYPES = [
    "feat",
    "fix",
    "docs",
    "refactor",
    "test",
    "ci",
    "build",
    "chore",
    "perf",
]


def problems(message: str, *, allow_autosquash: bool = False) -> list[str]:
    """Return the problems of a message, with autosquash headers refused."""
    return check_commit_message(message, allow_autosquash=allow_autosquash)


class ValidMessageTest(unittest.TestCase):
    """Messages that follow the policy have no problem."""

    def test_accepted_messages(self) -> None:
        """Each message in the table passes."""
        accepted = {
            "plain header": "feat: add the release tool",
            "scope": "fix(parser): handle an empty file",
            "path scope": "refactor(nix/lib): move the docs functions",
            "scope with hyphen, underscore and dot": "ci(a-b_c.d): x",
            "breaking mark": "feat!: drop the old function",
            "breaking mark with scope": "feat(api)!: drop the old function",
            "revert type": "revert: undo the change of the release job",
            "body after a blank line": "docs: explain it\n\nThe body says why.",
            "several paragraphs": "fix: x\n\nWhy.\n\nAssisted-by: tool (model)",
            "header of 72 characters": "feat: " + "a" * 66,
            "header of 100 characters": "feat: " + "a" * 94,
            "header of 100 non-ASCII characters": "feat: " + "é" * 94,
            "description with a colon": "feat: add a: b",
            "description with a period inside": "docs: add v1.2 notes",
        }
        for label, message in accepted.items():
            with self.subTest(label):
                self.assertEqual([], problems(message))

    def test_every_listed_type_is_accepted(self) -> None:
        """The nine types of the policy and `revert` pass as a type."""
        for commit_type in [*NINE_TYPES, "revert"]:
            with self.subTest(commit_type):
                self.assertEqual([], problems(f"{commit_type}: x"))


class HeaderRuleTest(unittest.TestCase):
    """Each rule of the header rejects what it names."""

    def assert_one_problem(self, message: str, expected: str) -> None:
        """Assert that the message has exactly one problem that holds `expected`."""
        found = problems(message)
        self.assertEqual(1, len(found), found)
        self.assertIn(expected, found[0])

    def test_empty_message(self) -> None:
        """An empty message and a blank one have no header."""
        for message in ("", "   ", "\n\nbody"):
            with self.subTest(repr(message)):
                self.assertEqual(["the message has no header"], problems(message))

    def test_header_without_the_form(self) -> None:
        """A header that is not `type(scope)!: description` names the form."""
        for header in (
            "Add a thing",
            "feat add x",
            "feat",
            "feat(scope: x",
            "feat!(scope): x",
            "feat (scope): x",
            "Merge branch 'a' into b",
            "(scope): x",
            ": x",
        ):
            with self.subTest(header):
                self.assert_one_problem(header, "type(scope)!: description")

    def test_git_revert_header_points_to_the_revert_type(self) -> None:
        """The default header of `git revert` gets the hint for `revert`."""
        self.assert_one_problem(
            'Revert "feat: add x"', "write 'revert: description' instead"
        )

    def test_git_merge_header_names_the_case_and_gives_the_advice_of_range(
        self,
    ) -> None:
        """The header of `git merge` or `git pull` says that merges are refused.

        The advice is the text that `range` gives for a merge commit, so a
        person gets the same answer from the hook and from the check of the
        history.
        """
        advice = check_stored_commit("Merge branch 'a'", is_merge=True)[0].removeprefix(
            "this is a merge commit: "
        )
        for header in (
            "Merge branch 'main' of https://example.com/x into topic",
            "Merge remote-tracking branch 'origin/main'",
            "Merge pull request #3 from a/b",
            "Merge tag 'v1'",
        ):
            with self.subTest(header):
                self.assert_one_problem(header, "this is a merge commit: " + advice)
                self.assert_one_problem(header, "type(scope)!: description")

    def test_a_header_that_only_starts_like_a_merge_has_no_merge_hint(self) -> None:
        """`Merged` and `Merge:` are not the header of Git, so the hint is absent."""
        for header in ("Merged the branch", "Merge: x"):
            with self.subTest(header):
                found = check_commit_message(header, allow_autosquash=False)
                self.assertEqual(1, len(found), found)
                self.assertNotIn("merge commit", found[0])

    def test_unknown_or_cased_type(self) -> None:
        """A type outside the list fails, and so does a type in capitals."""
        for header in ("wip: x", "feature: x", "Feat: x", "FIX: x", "style: x"):
            with self.subTest(header):
                self.assert_one_problem(header, "must be one of: feat, fix, docs")

    def test_scope_rules(self) -> None:
        """An empty scope, capitals, spaces and doubled marks fail."""
        for header in (
            "feat(): x",
            "feat(Scope): x",
            "feat(my scope): x",
            "feat(a--b): x",
            "feat(-a): x",
            "feat(a-): x",
        ):
            with self.subTest(header):
                self.assert_one_problem(header, "the scope")

    def test_colon_needs_one_space(self) -> None:
        """The description follows the colon after exactly one space."""
        for header in ("feat:x", "feat:", "feat:  x", "feat(a):x"):
            with self.subTest(header):
                self.assert_one_problem(header, "exactly one space")

    def test_description_is_required(self) -> None:
        """A header with only a space after the colon has no description."""
        self.assert_one_problem("feat: ", "no description")

    def test_final_period(self) -> None:
        """A header does not end with a period."""
        self.assert_one_problem("feat: add x.", "must not end with a period")

    def test_trailing_whitespace(self) -> None:
        """A header does not end with whitespace."""
        self.assert_one_problem("feat: add x ", "trailing whitespace")

    def test_length_limit_is_100_characters(self) -> None:
        """101 characters fail and 100 pass."""
        too_long = "feat: " + "a" * 95
        self.assertEqual(101, len(too_long))
        self.assert_one_problem(too_long, "has 101 characters; the limit is 100")
        self.assertEqual([], problems(too_long[:-1]))

    def test_length_counts_characters_not_bytes(self) -> None:
        """A header of 100 non-ASCII characters passes, and 101 fail.

        The header of 100 characters has 194 bytes in UTF-8, so a count of
        bytes would reject it.
        """
        at_limit = "feat: " + "é" * 94
        self.assertEqual(194, len(at_limit.encode("utf-8")))
        self.assertEqual([], problems(at_limit))
        self.assert_one_problem(at_limit + "é", "has 101 characters; the limit is 100")

    def test_byte_order_mark_before_the_type_is_not_ignored(self) -> None:
        """A BOM is part of the type, which is then not in the list."""
        byte_order_mark = "\N{ZERO WIDTH NO-BREAK SPACE}"
        self.assert_one_problem(
            f"{byte_order_mark}feat: x", "must be one of: feat, fix, docs"
        )

    def test_all_problems_of_a_message_are_listed(self) -> None:
        """A header with several faults reports each one."""
        found = problems("Feat(Scope):x." + "a" * 100)
        self.assertEqual(4, len(found), found)


class BodySeparatorTest(unittest.TestCase):
    """The body starts after a blank line."""

    def test_body_without_a_blank_line_fails(self) -> None:
        """A second line that holds text breaks the rule."""
        found = problems("feat: x\nbody right after")
        self.assertEqual(1, len(found), found)
        self.assertIn("second line must be blank", found[0])

    def test_whitespace_only_second_line_is_blank(self) -> None:
        """A second line of spaces counts as the blank line."""
        self.assertEqual([], problems("feat: x\n  \nbody"))

    def test_header_alone_has_no_separator_problem(self) -> None:
        """A message of one line, with or without a final newline, passes."""
        self.assertEqual([], problems("feat: x"))
        self.assertEqual([], problems("feat: x\n"))


class AutosquashTest(unittest.TestCase):
    """The commits that `git rebase --autosquash` folds pass only in the hook."""

    HEADERS = (
        "fixup! feat: add x",
        "squash! fix(a): change y",
        "amend! docs: z",
        "fixup! fixup! feat: add x",
    )

    def test_allowed_in_the_hook(self) -> None:
        """With `allow_autosquash` an autosquash header passes unchecked."""
        for header in self.HEADERS:
            with self.subTest(header):
                self.assertEqual([], problems(header, allow_autosquash=True))

    def test_refused_in_finished_history(self) -> None:
        """Without `allow_autosquash` an autosquash header is the problem."""
        for header in self.HEADERS:
            with self.subTest(header):
                found = problems(header, allow_autosquash=False)
                self.assertEqual(1, len(found), found)
                self.assertIn("git rebase --autosquash", found[0])
                self.assertIn(header.split(" ")[0], found[0])

    def test_prefix_without_a_space_is_an_ordinary_header(self) -> None:
        """`fixup!feat: x` is not an autosquash header: the form rule fails it."""
        found = problems("fixup!feat: x", allow_autosquash=True)
        self.assertEqual(1, len(found), found)
        self.assertIn("type(scope)!: description", found[0])


class StoredCommitTest(unittest.TestCase):
    """A commit that Git stores is checked as finished history."""

    def test_ordinary_commit_gets_the_message_rules(self) -> None:
        """A commit with one parent has the problems of its message."""
        self.assertEqual([], check_stored_commit("feat: x", is_merge=False))
        found = check_stored_commit("added x", is_merge=False)
        self.assertEqual(1, len(found), found)
        self.assertIn("type(scope)!: description", found[0])

    def test_autosquash_header_is_refused(self) -> None:
        """A stored commit never gets the pass of the hook."""
        found = check_stored_commit("fixup! feat: x", is_merge=False)
        self.assertEqual(1, len(found), found)
        self.assertIn("git rebase --autosquash", found[0])

    def test_merge_commit_names_the_case_and_the_fix(self) -> None:
        """A merge commit fails, even with a valid header, and says what to do."""
        for message in ("feat: merge the side", "Merge branch 'a'"):
            with self.subTest(message):
                found = check_stored_commit(message, is_merge=True)
                self.assertEqual(1, len(found), found)
                self.assertIn("merge commit", found[0])
                self.assertIn("rebase the branch", found[0])
                self.assertIn("Update branch", found[0])

    def test_message_that_is_not_utf8_names_the_case(self) -> None:
        """A message of `None` is the message that is not UTF-8 text."""
        found = check_stored_commit(None, is_merge=False)
        self.assertEqual(1, len(found), found)
        self.assertIn("not valid UTF-8", found[0])


class OneTypeListTest(unittest.TestCase):
    """Commit headers and branch names share one list of types."""

    def test_the_policy_lists_exactly_nine_types_and_revert(self) -> None:
        """Branches have the nine types, and commits have them and `revert`."""
        self.assertEqual(NINE_TYPES, list(BRANCH_TYPES))
        self.assertEqual([*NINE_TYPES, "revert"], list(COMMIT_TYPES))


if __name__ == "__main__":
    unittest.main()
