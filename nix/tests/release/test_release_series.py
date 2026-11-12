"""Tests of the two tag series and the rule that each one follows."""

import unittest

from release.series import ACTIONS, ALL_SERIES, HUB, Bump
from release.tags import ACTIONS_PREFIX, HUB_PREFIX


class SeriesDefinitionTest(unittest.TestCase):
    """The two series differ in the prefix, the label and the latest flag."""

    def test_each_series_has_its_own_name_and_prefix(self) -> None:
        """The command line selects a series by name, and a tag by prefix."""
        self.assertEqual((HUB.name, HUB.prefix), ("hub", HUB_PREFIX))
        self.assertEqual((ACTIONS.name, ACTIONS.prefix), ("actions", ACTIONS_PREFIX))
        self.assertEqual(len({series.name for series in ALL_SERIES}), len(ALL_SERIES))

    def test_the_default_series_is_the_hub_series(self) -> None:
        """The first series of the list is the default of the command line."""
        self.assertIs(ALL_SERIES[0], HUB)

    def test_only_the_hub_release_takes_the_latest_label(self) -> None:
        """The actions release must leave the label on the hub release."""
        self.assertTrue(HUB.make_latest)
        self.assertFalse(ACTIONS.make_latest)

    def test_the_hub_label_is_the_label_that_the_notes_always_had(self) -> None:
        """The notes of the hub series start with `rules changed`."""
        self.assertEqual(HUB.label, "rules changed")


class HubBumpTest(unittest.TestCase):
    """The hub series releases every commit: a rule gives a minor, else a patch."""

    def test_a_rule_path_gives_minor(self) -> None:
        """A change to `flake.nix` raises the minor number."""
        self.assertIs(HUB.bump_for_changes(["flake.nix"]), Bump.MINOR)

    def test_the_reusable_secrets_workflow_gives_minor(self) -> None:
        """`secrets.yml` stays in the hub series."""
        self.assertIs(
            HUB.bump_for_changes([".github/workflows/secrets.yml"]), Bump.MINOR
        )

    def test_documentation_and_actions_paths_give_patch(self) -> None:
        """No consumer reads them through the hub series."""
        paths = [
            "docs/reference/a.txt",
            ".github/actions/setup-nix/action.yml",
            "versions.json",
        ]
        self.assertIs(HUB.bump_for_changes(paths), Bump.PATCH)

    def test_no_path_gives_patch_never_none(self) -> None:
        """The hub series always releases."""
        self.assertIs(HUB.bump_for_changes([]), Bump.PATCH)

    def test_the_first_release_is_minor_whatever_the_tree(self) -> None:
        """The first release says `yes`, even for a tree of pages only."""
        self.assertIs(HUB.bump_for_first_release(["docs/reference/a.txt"]), Bump.MINOR)
        self.assertIs(HUB.bump_for_first_release([]), Bump.MINOR)


class ActionsBumpTest(unittest.TestCase):
    """The actions series releases only a change of its own paths."""

    def test_an_action_file_gives_minor(self) -> None:
        """A file below `.github/actions/` changes the steps that run."""
        self.assertIs(
            ACTIONS.bump_for_changes([".github/actions/setup-nix/action.yml"]),
            Bump.MINOR,
        )

    def test_the_standards_workflow_gives_minor(self) -> None:
        """A change of the reusable workflow `standards.yml` changes the steps."""
        self.assertIs(
            ACTIONS.bump_for_changes([".github/workflows/standards.yml"]),
            Bump.MINOR,
        )

    def test_versions_json_alone_gives_patch(self) -> None:
        """Only the value that the steps read moves, so the patch rises."""
        self.assertIs(ACTIONS.bump_for_changes(["versions.json"]), Bump.PATCH)

    def test_versions_json_with_a_path_of_no_series_gives_patch(self) -> None:
        """A page next to `versions.json` doesn't raise the minor number."""
        paths = ["docs/reference/versions.md", "versions.json"]
        self.assertIs(ACTIONS.bump_for_changes(paths), Bump.PATCH)

    def test_versions_json_with_a_workflow_file_gives_minor(self) -> None:
        """The higher kind wins, whatever the order of the paths."""
        paths = ["versions.json", ".github/actions/setup-nix/action.yml"]
        self.assertIs(ACTIONS.bump_for_changes(paths), Bump.MINOR)
        self.assertIs(ACTIONS.bump_for_changes(paths[::-1]), Bump.MINOR)

    def test_other_paths_give_no_release(self) -> None:
        """A page, a test, the flake and `secrets.yml` are not actions paths."""
        paths = [
            "docs/reference/a.txt",
            "nix/tests/release/test_release_tags.py",
            "flake.nix",
            ".github/workflows/secrets.yml",
            ".github/workflows/ci.yml",
        ]
        self.assertIs(ACTIONS.bump_for_changes(paths), Bump.NONE)

    def test_no_path_gives_no_release(self) -> None:
        """An empty range has nothing to release."""
        self.assertIs(ACTIONS.bump_for_changes([]), Bump.NONE)

    def test_the_first_release_needs_a_workflow_or_action_file_in_the_tree(
        self,
    ) -> None:
        """A tree with an action file gives minor, whatever else it holds."""
        tree = ["README.md", ".github/actions/setup-nix/action.yml", "versions.json"]
        self.assertIs(ACTIONS.bump_for_first_release(tree), Bump.MINOR)

    def test_a_data_file_alone_does_not_start_the_series(self) -> None:
        """The first tag can't move or go, so `versions.json` alone gives none."""
        self.assertIs(
            ACTIONS.bump_for_first_release(["README.md", "versions.json"]),
            Bump.NONE,
        )

    def test_a_tree_without_an_actions_path_has_no_first_release(self) -> None:
        """Nothing to release: the series stays without a tag."""
        self.assertIs(ACTIONS.bump_for_first_release(["README.md"]), Bump.NONE)
        self.assertIs(ACTIONS.bump_for_first_release([]), Bump.NONE)
