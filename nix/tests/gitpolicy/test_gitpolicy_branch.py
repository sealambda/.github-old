"""Tests for the branch name rules.

The expected results come from the plan's branch model: `<type>/<short-slug>`
with the nine types, the bot prefix `renovate/`, and `main`.
"""

import unittest

from gitpolicy.branch import check_branch_name

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


class ValidBranchTest(unittest.TestCase):
    """Names that follow the policy have no problem."""

    def test_accepted_names(self) -> None:
        """Each name in the table passes."""
        accepted = {
            "trunk": "main",
            "slug of one word": "fix/listen",
            "slug with hyphens": "fix/listen-address",
            "slug with digits": "docs/adr-0006-git-policy",
            "slug that starts with a digit": "chore/2026-cleanup",
            "Renovate group": "renovate/actions-checkout-3.x",
            "Renovate lock file branch": "renovate/lock-file-maintenance",
            "Renovate branch with a slash": "renovate/major/node-24.x",
        }
        for label, name in accepted.items():
            with self.subTest(label):
                self.assertEqual([], check_branch_name(name))

    def test_every_type_is_accepted(self) -> None:
        """Each of the nine types starts a valid name."""
        for branch_type in NINE_TYPES:
            with self.subTest(branch_type):
                self.assertEqual([], check_branch_name(f"{branch_type}/a-slug"))


class InvalidBranchTest(unittest.TestCase):
    """Each rule rejects what it names."""

    def assert_problem(self, name: str, expected: str) -> None:
        """Assert that the name has a problem that holds `expected`."""
        found = check_branch_name(name)
        self.assertTrue(any(expected in problem for problem in found), found)

    def test_name_without_a_slash(self) -> None:
        """A name with no `/` names the form."""
        for name in ("master", "develop", "feat", "main2", "", "my-branch", "--help"):
            with self.subTest(repr(name)):
                self.assert_problem(name, "<type>/<slug>")

    def test_unknown_type(self) -> None:
        """A type outside the nine fails, `revert` and capitals included."""
        for name in (
            "feature/x",
            "bugfix/x",
            "revert/x",
            "Feat/x",
            "dependabot/npm",
            "renovate-x/y",
            "wip/x",
            "-h/x",
            "--help/x",
        ):
            with self.subTest(name):
                self.assert_problem(name, "must be one of: feat, fix, docs")

    def test_bad_slug(self) -> None:
        """A slug fails on capitals, underscores, dots, spaces and hyphen faults."""
        for name in (
            "feat/Foo",
            "feat/foo_bar",
            "feat/foo bar",
            "feat/foo--bar",
            "feat/-foo",
            "feat/foo-",
            "feat/a/b",
            "feat/",
            "feat/foo.bar",
        ):
            with self.subTest(name):
                self.assert_problem(name, "the slug")

    def test_bot_prefix_needs_a_topic(self) -> None:
        """`renovate/` alone is not a bot branch."""
        self.assertNotEqual([], check_branch_name("renovate/"))

    def test_a_name_with_two_faults_lists_both(self) -> None:
        """A bad type and a bad slug are two problems."""
        self.assertEqual(2, len(check_branch_name("Feature/Foo_Bar")))


if __name__ == "__main__":
    unittest.main()
