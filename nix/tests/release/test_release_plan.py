"""Tests of the plan of a release against real temporary git repositories."""

from release.plan import (
    AlreadyReleased,
    Covered,
    Plan,
    ReleaseError,
    plan_for_existing_tag,
    plan_release,
)
from release_repo import RepoTestCase


class PlanReleaseTest(RepoTestCase):
    """`plan_release` reads tags, paths and commits from git."""

    def planned(self, revision: str = "HEAD") -> Plan:
        """Plan `revision` and check that the commit is not yet released."""
        outcome = plan_release(self.git, revision)
        assert isinstance(outcome, Plan), outcome
        return outcome

    def test_first_release_is_1_0_0_with_changed_rules(self) -> None:
        """Without a release tag the plan is `v1.0.0`, `yes`, for all commits."""
        self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        head = self.commit({"README.md": "r\n"}, "docs: add a readme")
        plan = self.planned()
        self.assertEqual(plan.tag, "v1.0.0")
        self.assertEqual(plan.commit, head)
        self.assertIsNone(plan.previous)
        self.assertTrue(plan.rules_changed)
        self.assertEqual(
            plan.notes,
            "rules changed: yes\n\n- `docs: add a readme`\n- `docs: add a page`\n",
        )

    def test_documentation_only_change_raises_the_patch(self) -> None:
        """A change of rule-free paths gives `no` and the next patch."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.4.2")
        self.commit(
            {"docs/reference/a.txt": "a\n", "nix/tests/t.py": "t\n"}, "docs: add a page"
        )
        plan = self.planned()
        self.assertEqual(plan.tag, "v1.4.3")
        self.assertEqual(plan.previous, "v1.4.2")
        self.assertFalse(plan.rules_changed)
        self.assertEqual(plan.notes, "rules changed: no\n\n- `docs: add a page`\n")

    def test_rule_change_raises_the_minor_and_resets_the_patch(self) -> None:
        """A change of a rule path gives `yes` and the next minor."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.4.2")
        self.commit({"flake.nix": "{ }\n"}, "fix: change the flake")
        plan = self.planned()
        self.assertEqual(plan.tag, "v1.5.0")
        self.assertTrue(plan.rules_changed)

    def test_mixed_change_counts_as_a_rule_change(self) -> None:
        """One rule path among documentation paths gives `yes`."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.commit(
            {"docs/reference/a.txt": "a\n", "default.json": "{}\n"}, "feat: mixed"
        )
        self.assertTrue(self.planned().rules_changed)

    def test_unknown_path_counts_as_a_rule_change(self) -> None:
        """A path that no pattern names gives `yes`."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.commit({"brand-new-dir/file.txt": "x\n"}, "feat: new area")
        self.assertTrue(self.planned().rules_changed)

    def test_changes_are_measured_across_all_commits_since_the_release(self) -> None:
        """A rule change in an earlier commit counts for the later release."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.commit({"flake.nix": "{ }\n"}, "fix: change the flake")
        self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        plan = self.planned()
        self.assertTrue(plan.rules_changed)
        self.assertEqual(
            plan.notes,
            "rules changed: yes\n\n- `docs: add a page`\n- `fix: change the flake`\n",
        )

    def test_deleting_or_renaming_a_rule_path_changes_the_rules(self) -> None:
        """A deleted rule file, and a rule file moved into `docs/`, count."""
        self.commit({"default.json": "{}\n", "keep.json": "{}\n"}, "feat: add files")
        self.tag("v1.0.0")
        self.commit({"default.json": None}, "fix: remove a file")
        self.assertTrue(self.planned().rules_changed)
        self.tag("v1.1.0")
        self.commit(
            {"docs/reference/keep.json": "{}\n", "keep.json": None}, "fix: move"
        )
        self.assertTrue(self.planned().rules_changed)

    def test_malformed_tags_are_ignored(self) -> None:
        """Tags of another form never act as the previous release."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        for name in ("v9.9", "v2.0.0-rc1", "latest", "1.8.0"):
            self.tag(name)
        self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        plan = self.planned()
        self.assertEqual((plan.tag, plan.previous), ("v1.0.1", "v1.0.0"))

    def test_a_malformed_tag_alone_means_no_previous_release(self) -> None:
        """Without a release tag the plan is the first release."""
        self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.tag("v1.0")
        self.assertEqual(self.planned().tag, "v1.0.0")

    def test_previous_release_is_the_highest_tag_by_number(self) -> None:
        """`v1.10.0` outranks `v1.9.0`, although it sorts lower as text."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.9.0")
        self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.tag("v1.10.0")
        self.commit({"docs/reference/b.txt": "b\n"}, "docs: add another page")
        self.assertEqual(self.planned().tag, "v1.10.1")

    def test_a_tag_on_an_unmerged_branch_is_not_a_previous_release(self) -> None:
        """Only tags that the released commit contains count."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.git(["switch", "--quiet", "--create", "side"])
        self.commit({"docs/reference/side.txt": "s\n"}, "docs: side page")
        self.tag("v1.7.0")
        self.git(["switch", "--quiet", "main"])
        self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        plan = self.planned()
        self.assertEqual((plan.tag, plan.previous), ("v1.0.1", "v1.0.0"))

    def test_annotated_previous_tag_counts(self) -> None:
        """An annotated tag is a release tag like a lightweight one."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0", annotated=True)
        self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.assertEqual(self.planned().tag, "v1.0.1")

    def test_commit_that_carries_a_release_tag_is_already_released(self) -> None:
        """A tagged commit gets no plan, and a lightweight or annotated tag counts."""
        for annotated in (False, True):
            with self.subTest(annotated=annotated):
                head = self.commit(
                    {f"docs/reference/{annotated}.txt": "a\n"}, "docs: a page"
                )
                self.tag("v1.3.0" if annotated else "v1.2.0", annotated=annotated)
                outcome = plan_release(self.git, "HEAD")
                self.assertEqual(
                    outcome,
                    AlreadyReleased(head, "v1.3.0" if annotated else "v1.2.0"),
                )

    def test_commit_with_several_release_tags_reports_the_highest(self) -> None:
        """Two release tags on one commit give the higher one."""
        head = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.tag("v1.2.0")
        self.tag("v1.10.0")
        self.assertEqual(
            plan_release(self.git, "HEAD"), AlreadyReleased(head, "v1.10.0")
        )

    def test_malformed_tag_on_the_commit_is_not_a_release(self) -> None:
        """A commit with only a malformed tag still gets released."""
        self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.tag("v1.0")
        self.assertIsInstance(plan_release(self.git, "HEAD"), Plan)

    def test_tag_on_a_commit_that_does_not_contain_this_one_fails(self) -> None:
        """A version that a release on another branch holds is taken."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.git(["switch", "--quiet", "--create", "side"])
        other = self.commit({"docs/reference/side.txt": "s\n"}, "docs: side page")
        self.tag("v1.0.1")
        self.git(["switch", "--quiet", "main"])
        main_commit = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        with self.assertRaises(ReleaseError) as raised:
            plan_release(self.git, main_commit)
        self.assertIn("v1.0.1", str(raised.exception))
        self.assertIn(other, str(raised.exception))

    def test_commit_that_a_later_release_contains_is_covered(self) -> None:
        """No tag points at the commit, but a later one contains it."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        skipped = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.commit({"flake.nix": "{ }\n"}, "fix: change the flake")
        self.tag("v1.1.0")
        self.assertEqual(plan_release(self.git, skipped), Covered(skipped, "v1.1.0"))

    def test_covering_tag_is_the_lowest_by_number(self) -> None:
        """`v1.9.0` is lower than `v1.10.0`, although it sorts higher as text."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        skipped = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.commit({"flake.nix": "{ }\n"}, "fix: change the flake")
        self.tag("v1.10.0")
        self.tag("v1.9.0")
        self.assertEqual(plan_release(self.git, skipped), Covered(skipped, "v1.9.0"))

    def test_a_tag_on_the_commit_wins_over_a_covering_tag(self) -> None:
        """A commit that carries a release tag is released, not merely covered."""
        carried = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.tag("v1.0.0")
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.1.0")
        self.assertEqual(
            plan_release(self.git, carried), AlreadyReleased(carried, "v1.0.0")
        )

    def test_tag_on_another_branch_does_not_cover(self) -> None:
        """A tag that does not contain the commit leaves it unreleased."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.git(["switch", "--quiet", "--create", "side"])
        self.commit({"docs/reference/side.txt": "s\n"}, "docs: side page")
        self.tag("v1.7.0")
        self.git(["switch", "--quiet", "main"])
        main_commit = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.assertIsInstance(plan_release(self.git, main_commit), Plan)

    def test_commit_without_a_changed_path_gives_no(self) -> None:
        """An empty commit after the release gives `no` and an empty diff."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.commit({}, "chore: empty commit")
        plan = self.planned()
        self.assertFalse(plan.rules_changed)
        self.assertEqual(plan.tag, "v1.0.1")
        self.assertEqual(plan.notes, "rules changed: no\n\n- `chore: empty commit`\n")

    def test_commit_argument_names_the_commit_to_release(self) -> None:
        """The plan is for the named commit, not for `HEAD`."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        middle = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.commit({"flake.nix": "{ }\n"}, "fix: change the flake")
        plan = self.planned(middle)
        self.assertEqual((plan.commit, plan.tag), (middle, "v1.0.1"))
        self.assertFalse(plan.rules_changed)


class PlanForExistingTagTest(RepoTestCase):
    """`plan_for_existing_tag` plans the release of a tag that exists."""

    def test_previous_release_is_the_nearest_tag_below_the_commit(self) -> None:
        """The answer and the notes come from the release before the tag."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.commit({"flake.nix": "{ }\n"}, "fix: change the flake")
        head = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.tag("v1.1.0")
        plan = plan_for_existing_tag(self.git, AlreadyReleased(head, "v1.1.0"))
        self.assertEqual(
            (plan.tag, plan.commit, plan.previous), ("v1.1.0", head, "v1.0.0")
        )
        self.assertTrue(plan.rules_changed)
        self.assertEqual(
            plan.notes,
            "rules changed: yes\n\n- `docs: add a page`\n- `fix: change the flake`\n",
        )

    def test_a_second_tag_on_the_commit_is_not_the_previous_release(self) -> None:
        """A sibling tag would give an empty diff and `no`: it must not count."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        head = self.commit({"flake.nix": "{ }\n"}, "fix: change the flake")
        self.tag("v1.1.0")
        self.tag("v1.1.1")
        plan = plan_for_existing_tag(self.git, AlreadyReleased(head, "v1.1.1"))
        self.assertEqual(plan.previous, "v1.0.0")
        self.assertTrue(plan.rules_changed)

    def test_first_tag_has_no_previous_release(self) -> None:
        """Without an earlier release tag the answer is `yes`."""
        head = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.tag("v1.0.0")
        plan = plan_for_existing_tag(self.git, AlreadyReleased(head, "v1.0.0"))
        self.assertIsNone(plan.previous)
        self.assertTrue(plan.rules_changed)
