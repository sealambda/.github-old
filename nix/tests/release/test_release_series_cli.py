"""Tests of the option `--series`: output, exit status and the calls to `gh`."""

from release import cli
from release_repo import RepoTestCase

ACTION_FILE = ".github/actions/setup-nix/action.yml"


class SeriesOptionTest(RepoTestCase):
    """`--series` selects the tag series, and the default is the hub series."""

    def test_a_missing_series_equals_the_hub_series(self) -> None:
        """The output is the same with and without `--series hub`, on any command."""
        self.commit({"flake.nix": "{}\n", ACTION_FILE: "a\n"}, "feat: start")
        self.tag("v1.0.0")
        self.tag("actions-v1.0.0")
        self.commit({"flake.nix": "{ }\n"}, "fix: change the flake")
        implicit = self.run_cli("plan")
        explicit = self.run_cli("plan", "--series", "hub")
        self.assertEqual(implicit, explicit)
        self.assertIn("tag: v1.1.0\n", implicit.stdout)

    def test_an_unknown_series_is_a_usage_error(self) -> None:
        """Exit status 2, the choices in the message, and no call."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        for command in ("plan", "publish"):
            with self.subTest(command=command):
                result = self.run_cli(command, "--series", "tools")
                self.assertEqual(result.code, cli.EXIT_USAGE)
                self.assertIn("hub", result.stderr)
                self.assertIn("actions", result.stderr)
                self.assertEqual(result.stdout, "")
        self.assertEqual(self.gh.calls, [])

    def test_the_series_option_needs_a_value(self) -> None:
        """`--series` without a value is a usage error."""
        self.assertEqual(self.run_cli("plan", "--series").code, cli.EXIT_USAGE)


class ActionsPlanCommandTest(RepoTestCase):
    """`release plan --series actions` prints the actions release, or none."""

    def test_the_first_release_prints_actions_v1_0_0(self) -> None:
        """A tree with an action file and no actions tag gets `actions-v1.0.0`."""
        head = self.commit({ACTION_FILE: "a\n", "versions.json": "{}\n"}, "feat: add")
        self.tag("v1.3.0")
        result = self.run_cli("plan", "--series", "actions")
        self.assertEqual(result.code, cli.EXIT_OK)
        self.assertEqual(
            result.stdout,
            f"tag: actions-v1.0.0\ncommit: {head}\nprevious release: none\n"
            "--- notes ---\nworkflow or action files changed: yes\n\n- `feat: add`\n",
        )
        self.assertEqual(self.gh.calls, [])

    def test_the_hub_plan_is_the_same_with_actions_tags_in_the_history(self) -> None:
        """Tags of the actions series never change the plan of the hub series."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        before = self.run_cli("plan")
        self.tag("actions-v9.9.9", commit="HEAD~1")
        self.tag("actions-v1.0.0")
        self.assertEqual(self.run_cli("plan"), before)
        self.assertIn("tag: v1.0.1\n", before.stdout)

    def test_a_commit_without_an_actions_change_gets_no_release_and_exit_0(
        self,
    ) -> None:
        """The information line names the previous tag, and nothing is called."""
        self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        self.tag("actions-v1.0.0")
        head = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        for command in ("plan", "publish"):
            with self.subTest(command=command):
                result = self.run_cli(command, "--series", "actions")
                self.assertEqual(result.code, cli.EXIT_OK)
                self.assertEqual(
                    result.stdout,
                    f"commit {head} changes no path that the series releases "
                    "since actions-v1.0.0: no release\n",
                )
                self.assertEqual(result.stderr, "")
        self.assertEqual(self.gh.calls, [])
        self.assertEqual(self.tag_names(), ["actions-v1.0.0"])

    def test_a_tree_without_an_actions_path_gets_no_release_and_exit_0(self) -> None:
        """No actions tag and no actions path: the line says so, exit 0."""
        head = self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        result = self.run_cli("publish", "--series", "actions")
        self.assertEqual(result.code, cli.EXIT_OK)
        self.assertEqual(
            result.stdout,
            f"commit {head} has no path that starts the series: no release\n",
        )
        self.assertEqual(self.gh.calls, [])

    def test_a_tree_with_only_versions_json_gets_no_first_release(self) -> None:
        """A data file alone doesn't start the series: no tag, no call, exit 0."""
        head = self.commit({"versions.json": "{}\n"}, "feat: add the pins")
        for command in ("plan", "publish"):
            with self.subTest(command=command):
                result = self.run_cli(command, "--series", "actions")
                self.assertEqual(result.code, cli.EXIT_OK)
                self.assertEqual(
                    result.stdout,
                    f"commit {head} has no path that starts the series: no release\n",
                )
        self.assertEqual(self.gh.calls, [])
        self.assertEqual(self.tag_names(), [])

    def test_the_hub_series_never_answers_no_release(self) -> None:
        """A documentation commit still gets the next hub patch."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        result = self.run_cli("plan", "--series", "hub")
        self.assertIn("tag: v1.0.1\n", result.stdout)

    def test_a_covered_commit_is_covered_by_the_actions_tag(self) -> None:
        """The covering release is a tag of the actions series."""
        self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        self.tag("actions-v1.0.0")
        skipped = self.commit({ACTION_FILE: "b\n"}, "fix: change action")
        self.commit({ACTION_FILE: "c\n"}, "fix: change action again")
        self.tag("actions-v1.1.0")
        result = self.run_cli("plan", "--series", "actions", "--commit", skipped)
        self.assertEqual(
            result.stdout, f"commit {skipped} is covered by release actions-v1.1.0\n"
        )


class ActionsPublishCommandTest(RepoTestCase):
    """`release publish --series actions` keeps the hub release as the latest."""

    def test_the_call_adds_latest_false(self) -> None:
        """The call names the actions tag and ends with `--latest=false`."""
        head = self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        result = self.run_cli("publish", "--series", "actions")
        self.assertEqual(result.code, cli.EXIT_OK)
        self.assertEqual(result.stdout, f"released actions-v1.0.0 at commit {head}\n")
        self.assertEqual(
            self.gh.calls,
            [
                (
                    [
                        "release",
                        "create",
                        "actions-v1.0.0",
                        "--target",
                        head,
                        "--title",
                        "actions-v1.0.0",
                        "--notes-file",
                        "-",
                        "--latest=false",
                    ],
                    "workflow or action files changed: yes\n\n- `feat: add action`\n",
                ),
                (["api", "repos/{owner}/{repo}/git/ref/tags/actions-v1.0.0"], None),
            ],
        )

    def test_the_hub_call_has_no_latest_argument(self) -> None:
        """The hub call is the call of the tool before the second series."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("actions-v1.0.0")
        self.run_cli("publish")
        call, _ = self.gh.calls[0]
        self.assertEqual(call[:3], ["release", "create", "v1.0.0"])
        self.assertFalse([argument for argument in call if "latest" in argument])

    def test_a_rerun_after_a_tag_without_a_release_keeps_latest_false(self) -> None:
        """The repair of an existing actions tag uses `--verify-tag --latest=false`."""
        self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        head = self.commit({ACTION_FILE: "b\n"}, "fix: change action")
        self.tag("actions-v1.0.0", commit="HEAD~1")
        self.tag("actions-v1.1.0")
        self.gh.releases.add("actions-v1.0.0")
        result = self.run_cli("publish", "--series", "actions")
        self.assertEqual(result.code, cli.EXIT_OK)
        self.assertEqual(
            result.stdout,
            f"commit {head} carries the tag actions-v1.1.0 without a release: "
            "created the release for the existing tag\n",
        )
        self.assertEqual(
            self.gh.calls,
            [
                (["release", "view", "actions-v1.1.0", "--json", "tagName"], None),
                (
                    [
                        "release",
                        "create",
                        "actions-v1.1.0",
                        "--verify-tag",
                        "--title",
                        "actions-v1.1.0",
                        "--notes-file",
                        "-",
                        "--latest=false",
                    ],
                    "workflow or action files changed: yes\n\n- `fix: change action`\n",
                ),
            ],
        )

    def test_a_second_run_creates_nothing(self) -> None:
        """The release of the tag exists: one question, no creation, exit 0."""
        head = self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        self.tag("actions-v1.0.0")
        self.gh.releases.add("actions-v1.0.0")
        result = self.run_cli("publish", "--series", "actions")
        self.assertEqual(result.code, cli.EXIT_OK)
        self.assertEqual(
            result.stdout, f"commit {head} is already released as actions-v1.0.0\n"
        )
        self.assertEqual(
            self.gh.calls,
            [(["release", "view", "actions-v1.0.0", "--json", "tagName"], None)],
        )

    def test_a_hub_tag_on_the_commit_does_not_release_it_for_actions(self) -> None:
        """The hub run and the actions run on one commit each make their release."""
        head = self.commit({ACTION_FILE: "a\n", "flake.nix": "{}\n"}, "feat: start")
        self.run_cli("publish")
        self.tag("v1.0.0")
        self.gh.releases.add("v1.0.0")
        result = self.run_cli("publish", "--series", "actions")
        self.assertEqual(result.stdout, f"released actions-v1.0.0 at commit {head}\n")
        self.assertEqual(self.gh.releases, {"v1.0.0", "actions-v1.0.0"})

    def test_a_failed_creation_exits_1_and_a_rerun_creates_the_release(self) -> None:
        """A failure leaves no release, and the next run creates it."""
        self.commit({ACTION_FILE: "a\n"}, "feat: add action")
        self.gh.create_failure = "HTTP 502: Bad Gateway"
        failed = self.run_cli("publish", "--series", "actions")
        self.assertEqual(failed.code, cli.EXIT_CANNOT_RELEASE)
        self.assertIn("HTTP 502", failed.stderr)
        self.gh.create_failure = None
        again = self.run_cli("publish", "--series", "actions")
        self.assertEqual(again.code, cli.EXIT_OK)
        self.assertEqual(self.gh.releases, {"actions-v1.0.0"})
