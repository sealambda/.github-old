"""Tests of the plan of the actions series against real temporary repositories.

Each test builds a history with tags of both series and plans one commit. The
hub tests in `test_release_plan.py` cover the hub series alone.
"""

from release.plan import (
    AlreadyReleased,
    Covered,
    NoRelease,
    Plan,
    ReleaseError,
    plan_for_existing_tag,
    plan_release,
)
from release.series import ACTIONS, HUB
from release.tags import Bump
from release_repo import RepoTestCase

ACTION_FILE = ".github/actions/setup-nix/action.yml"
LABEL_YES = "workflow or action files changed: yes"
LABEL_NO = "workflow or action files changed: no"


class ActionsPlanTest(RepoTestCase):
    """`plan_release` for the actions series reads only the tags of that series."""

    def planned(self, revision: str = "HEAD") -> Plan:
        """Plan `revision` in the actions series and expect a new release."""
        outcome = plan_release(self.git, revision, ACTIONS)
        assert isinstance(outcome, Plan), outcome
        return outcome

    def test_without_a_tag_the_first_release_is_1_0_0(self) -> None:
        """A tree with an action file and no actions tag gives `actions-v1.0.0`."""
        self.commit({ACTION_FILE: "a\n", "versions.json": "{}\n"}, "feat: add action")
        head = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        plan = self.planned()
        self.assertEqual(plan.tag, "actions-v1.0.0")
        self.assertEqual(plan.commit, head)
        self.assertIsNone(plan.previous)
        self.assertIs(plan.bump, Bump.MINOR)
        self.assertFalse(plan.make_latest)
        self.assertEqual(
            plan.notes,
            f"{LABEL_YES}\n\n- `docs: add a page`\n- `feat: add action`\n",
        )

    def test_the_first_release_ignores_the_hub_tags(self) -> None:
        """Hub tags are no previous release of the actions series."""
        self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        self.tag("v1.4.2")
        self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        plan = self.planned()
        self.assertEqual((plan.tag, plan.previous), ("actions-v1.0.0", None))

    def test_a_tree_with_only_versions_json_gives_no_first_release(self) -> None:
        """A data file alone starts nothing: the first tag can't move or go."""
        head = self.commit(
            {"versions.json": "{}\n", "README.md": "r\n"}, "feat: add pins"
        )
        self.assertEqual(plan_release(self.git, "HEAD", ACTIONS), NoRelease(head, None))

    def test_the_first_action_file_starts_the_series_after_a_data_file(self) -> None:
        """The first tag lands on the commit that adds the file, as `yes`."""
        self.commit({"versions.json": "{}\n"}, "feat: add pins")
        head = self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        plan = self.planned()
        self.assertEqual(
            (plan.tag, plan.commit, plan.previous), ("actions-v1.0.0", head, None)
        )
        self.assertIs(plan.bump, Bump.MINOR)
        self.assertEqual(
            plan.notes, f"{LABEL_YES}\n\n- `feat: add action`\n- `feat: add pins`\n"
        )

    def test_a_tree_without_an_actions_path_has_no_release(self) -> None:
        """No tag and no actions path in the tree: nothing to release."""
        head = self.commit({"flake.nix": "{}\n", "README.md": "r\n"}, "feat: flake")
        self.assertEqual(plan_release(self.git, "HEAD", ACTIONS), NoRelease(head, None))

    def test_a_workflow_or_action_file_raises_the_minor(self) -> None:
        """The previous actions tag is `actions-v1.1.0`: a file gives `v1.2.0`."""
        self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        self.tag("actions-v1.1.0")
        self.commit({ACTION_FILE: "b\n"}, "fix: change action")
        plan = self.planned()
        self.assertEqual(
            (plan.tag, plan.previous), ("actions-v1.2.0", "actions-v1.1.0")
        )
        self.assertIs(plan.bump, Bump.MINOR)
        self.assertTrue(plan.notes.startswith(f"{LABEL_YES}\n"))

    def test_only_versions_json_raises_the_patch(self) -> None:
        """A change of the pinned version alone gives `actions-v1.1.1`."""
        self.commit({ACTION_FILE: "a\n", "versions.json": "1\n"}, "feat: add action")
        self.tag("actions-v1.1.0")
        self.commit({"versions.json": "2\n"}, "chore: bump the pin")
        plan = self.planned()
        self.assertEqual(plan.tag, "actions-v1.1.1")
        self.assertIs(plan.bump, Bump.PATCH)
        self.assertEqual(plan.notes, f"{LABEL_NO}\n\n- `chore: bump the pin`\n")

    def test_versions_json_with_an_action_file_raises_the_minor(self) -> None:
        """The higher kind wins when both change in the range."""
        self.commit({ACTION_FILE: "a\n", "versions.json": "1\n"}, "feat: add action")
        self.tag("actions-v1.1.0")
        self.commit({"versions.json": "2\n"}, "chore: bump the pin")
        self.commit({ACTION_FILE: "b\n"}, "fix: change action")
        self.assertEqual(self.planned().tag, "actions-v1.2.0")

    def test_a_documentation_only_range_gives_no_release(self) -> None:
        """The commit is not released: the outcome names the previous tag."""
        self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        self.tag("actions-v1.0.0")
        head = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.assertEqual(
            plan_release(self.git, "HEAD", ACTIONS), NoRelease(head, "actions-v1.0.0")
        )

    def test_a_hub_rule_change_gives_no_actions_release(self) -> None:
        """A change of `flake.nix` or `secrets.yml` is no actions path."""
        self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        self.tag("actions-v1.0.0")
        head = self.commit(
            {"flake.nix": "{}\n", ".github/workflows/secrets.yml": "s\n"}, "feat: hub"
        )
        self.assertEqual(
            plan_release(self.git, "HEAD", ACTIONS), NoRelease(head, "actions-v1.0.0")
        )

    def test_the_two_series_count_only_their_own_tags_in_one_history(self) -> None:
        """Each series finds its previous tag, whatever tags the other holds."""
        self.commit({"flake.nix": "{}\n", ACTION_FILE: "a\n"}, "feat: start")
        self.tag("v1.4.2")
        self.tag("actions-v1.1.0")
        self.commit({"flake.nix": "{ }\n"}, "fix: hub rule")
        self.tag("v1.5.0")
        self.commit({ACTION_FILE: "b\n"}, "fix: change action")
        actions = self.planned()
        self.assertEqual(
            (actions.tag, actions.previous), ("actions-v1.2.0", "actions-v1.1.0")
        )
        self.assertEqual(
            actions.notes,
            f"{LABEL_YES}\n\n- `fix: change action`\n- `fix: hub rule`\n",
        )
        hub = plan_release(self.git, "HEAD", HUB)
        assert isinstance(hub, Plan), hub
        self.assertEqual((hub.tag, hub.previous), ("v1.5.1", "v1.5.0"))
        self.assertIs(hub.bump, Bump.PATCH)
        self.assertTrue(hub.make_latest)

    def test_the_hub_plan_ignores_actions_tags(self) -> None:
        """An actions tag is no release of the hub series, so the plan is first."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("actions-v1.0.0")
        outcome = plan_release(self.git, "HEAD", HUB)
        assert isinstance(outcome, Plan), outcome
        self.assertEqual((outcome.tag, outcome.previous), ("v1.0.0", None))

    def test_a_commit_with_a_tag_of_the_other_series_is_not_released(self) -> None:
        """A hub tag does not release the commit for the actions series."""
        self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        self.tag("v1.0.0")
        outcome = plan_release(self.git, "HEAD", ACTIONS)
        self.assertIsInstance(outcome, Plan)
        self.assertIsInstance(plan_release(self.git, "HEAD", HUB), AlreadyReleased)

    def test_a_commit_with_both_tags_is_released_in_each_series(self) -> None:
        """Each series reports its own tag for the commit."""
        head = self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        self.tag("v1.0.0")
        self.tag("actions-v1.0.0")
        self.assertEqual(
            plan_release(self.git, "HEAD", ACTIONS),
            AlreadyReleased(head, "actions-v1.0.0"),
        )
        self.assertEqual(
            plan_release(self.git, "HEAD", HUB), AlreadyReleased(head, "v1.0.0")
        )

    def test_a_later_actions_tag_covers_the_commit(self) -> None:
        """The covering tag is the lowest actions tag that contains the commit."""
        self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        self.tag("actions-v1.0.0")
        skipped = self.commit({ACTION_FILE: "b\n"}, "fix: change action")
        self.commit({ACTION_FILE: "c\n"}, "fix: change action again")
        self.tag("actions-v1.10.0")
        self.tag("actions-v1.9.0")
        self.assertEqual(
            plan_release(self.git, skipped, ACTIONS), Covered(skipped, "actions-v1.9.0")
        )

    def test_a_later_hub_tag_does_not_cover_the_commit_for_actions(self) -> None:
        """Only a tag of the series covers a commit of that series."""
        skipped = self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.assertIsInstance(plan_release(self.git, skipped, ACTIONS), Plan)
        self.assertEqual(
            plan_release(self.git, skipped, HUB), Covered(skipped, "v1.0.0")
        )

    def test_an_actions_tag_on_another_branch_means_the_version_is_taken(self) -> None:
        """The error names the actions tag and the commit that holds it."""
        self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        self.tag("actions-v1.0.0")
        self.git(["switch", "--quiet", "--create", "side"])
        other = self.commit({ACTION_FILE: "s\n"}, "fix: side")
        self.tag("actions-v1.1.0")
        self.git(["switch", "--quiet", "main"])
        main_commit = self.commit({ACTION_FILE: "b\n"}, "fix: change action")
        with self.assertRaises(ReleaseError) as raised:
            plan_release(self.git, main_commit, ACTIONS)
        self.assertIn("actions-v1.1.0", str(raised.exception))
        self.assertIn(other, str(raised.exception))

    def test_a_hub_tag_with_the_next_number_does_not_block_actions(self) -> None:
        """`v1.1.0` and `actions-v1.1.0` are different tags."""
        self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        self.tag("actions-v1.0.0")
        self.git(["switch", "--quiet", "--create", "side"])
        self.commit({"flake.nix": "{}\n"}, "feat: side")
        self.tag("v1.1.0")
        self.git(["switch", "--quiet", "main"])
        self.commit({ACTION_FILE: "b\n"}, "fix: change action")
        self.assertEqual(self.planned().tag, "actions-v1.1.0")


class ActionsExistingTagTest(RepoTestCase):
    """`plan_for_existing_tag` for the actions series."""

    def test_the_previous_release_is_the_nearest_actions_tag(self) -> None:
        """A hub tag below the commit is not the previous release."""
        self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        self.tag("actions-v1.0.0")
        self.commit({"flake.nix": "{}\n"}, "feat: hub")
        self.tag("v1.1.0")
        head = self.commit({ACTION_FILE: "b\n"}, "fix: change action")
        self.tag("actions-v1.1.0")
        plan = plan_for_existing_tag(
            self.git, AlreadyReleased(head, "actions-v1.1.0"), ACTIONS
        )
        self.assertEqual(
            (plan.tag, plan.commit, plan.previous),
            ("actions-v1.1.0", head, "actions-v1.0.0"),
        )
        self.assertIs(plan.bump, Bump.MINOR)
        self.assertFalse(plan.make_latest)
        self.assertEqual(
            plan.notes, f"{LABEL_YES}\n\n- `fix: change action`\n- `feat: hub`\n"
        )

    def test_the_first_actions_tag_reads_the_tree(self) -> None:
        """Without an earlier actions tag the answer comes from the tree."""
        head = self.commit({"versions.json": "{}\n"}, "feat: add pins")
        self.tag("actions-v1.0.0")
        plan = plan_for_existing_tag(
            self.git, AlreadyReleased(head, "actions-v1.0.0"), ACTIONS
        )
        self.assertIsNone(plan.previous)
        self.assertIs(plan.bump, Bump.NONE)
        self.assertEqual(plan.notes, f"{LABEL_NO}\n\n- `feat: add pins`\n")

    def test_the_first_actions_tag_on_an_action_file_says_yes(self) -> None:
        """A manual first tag on a tree with an action file gets `yes`."""
        head = self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        self.tag("actions-v1.0.0")
        plan = plan_for_existing_tag(
            self.git, AlreadyReleased(head, "actions-v1.0.0"), ACTIONS
        )
        self.assertIs(plan.bump, Bump.MINOR)
        self.assertEqual(plan.notes, f"{LABEL_YES}\n\n- `feat: add action`\n")

    def test_a_tag_on_a_docs_only_commit_gets_no_and_no_latest_label(self) -> None:
        """A tag after the previous one with no workflow file in the range.

        The tag exists, so the plan never refuses it: the answer is `no`, the
        kind is `NONE` and the release does not take the "latest" label.
        """
        self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        self.tag("actions-v1.0.0")
        head = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.tag("actions-v1.0.1")
        plan = plan_for_existing_tag(
            self.git, AlreadyReleased(head, "actions-v1.0.1"), ACTIONS
        )
        self.assertEqual(
            (plan.tag, plan.previous), ("actions-v1.0.1", "actions-v1.0.0")
        )
        self.assertIs(plan.bump, Bump.NONE)
        self.assertFalse(plan.make_latest)
        self.assertEqual(plan.notes, f"{LABEL_NO}\n\n- `docs: add a page`\n")
