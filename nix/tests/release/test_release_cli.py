"""Tests of the command line: output, exit status and the calls to `gh`."""

from unittest import mock

from release import cli
from release_repo import RepoTestCase


class PlanCommandTest(RepoTestCase):
    """`release plan` prints the release and changes nothing."""

    def test_first_release_prints_the_tag_and_the_answer(self) -> None:
        """The hub without a release tag gets `v1.0.0` and `rules changed: yes`."""
        head = self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        result = self.run_cli("plan")
        self.assertEqual(result.code, cli.EXIT_OK)
        self.assertEqual(
            result.stdout,
            f"tag: v1.0.0\ncommit: {head}\nprevious release: none\n"
            "--- notes ---\nrules changed: yes\n\n- `feat: add the flake`\n",
        )
        self.assertEqual(result.stderr, "")

    def test_plan_changes_nothing(self) -> None:
        """No tag appears and `gh` is not called."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.run_cli("plan")
        self.assertEqual(self.tag_names(), [])
        self.assertEqual(self.gh.calls, [])

    def test_plan_of_a_released_commit_says_so(self) -> None:
        """A commit with a release tag prints its tag and exits 0."""
        head = self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        result = self.run_cli("plan")
        self.assertEqual(result.code, cli.EXIT_OK)
        self.assertEqual(
            result.stdout, f"commit {head} is already released as v1.0.0\n"
        )

    def test_commit_option_selects_the_commit(self) -> None:
        """`--commit` takes a revision other than `HEAD`."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        middle = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.commit({"flake.nix": "{ }\n"}, "fix: change the flake")
        result = self.run_cli("plan", "--commit", middle)
        self.assertEqual(result.code, cli.EXIT_OK)
        self.assertIn("tag: v1.0.1\n", result.stdout)
        self.assertIn("--- notes ---\nrules changed: no\n", result.stdout)

    def test_commit_without_a_changed_path_gets_no_and_the_next_patch(self) -> None:
        """An empty commit after the release changes no rule: `no`, patch up."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.3.0")
        head = self.commit({}, "chore: empty commit")
        result = self.run_cli("plan")
        self.assertEqual(result.code, cli.EXIT_OK)
        self.assertEqual(
            result.stdout,
            f"tag: v1.3.1\ncommit: {head}\nprevious release: v1.3.0\n"
            "--- notes ---\nrules changed: no\n\n- `chore: empty commit`\n",
        )

    def test_path_that_is_not_utf8_is_an_unknown_path_and_gives_yes(self) -> None:
        """Raw bytes in a path do not stop the tool: the path is unclassified."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.commit_raw_path(b"unknown/bad\xff.txt", "feat: add a raw path")
        result = self.run_cli("plan")
        self.assertEqual(result.code, cli.EXIT_OK)
        self.assertIn("tag: v1.1.0\n", result.stdout)
        self.assertIn("--- notes ---\nrules changed: yes\n", result.stdout)

    def test_path_that_is_not_utf8_below_a_free_folder_stays_free(self) -> None:
        """The replacement character keeps the folder, so the pattern matches."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.commit_raw_path(b"docs/reference/bad\xff.md", "docs: add a raw page")
        result = self.run_cli("plan")
        self.assertEqual(result.code, cli.EXIT_OK)
        self.assertIn("tag: v1.0.1\n", result.stdout)
        self.assertIn("--- notes ---\nrules changed: no\n", result.stdout)

    def test_commit_that_a_later_release_contains_is_covered(self) -> None:
        """The old run of a skipped commit gets no tag behind a newer release.

        `v1.0.0` exists. X changes only documentation, and its run was
        replaced, so X has no release. Y changes a rule and is released as
        `v1.1.0` with notes that list X. A re-run for X must not plan `v1.0.1`.
        """
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        skipped = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.commit({"flake.nix": "{ }\n"}, "fix: change the flake")
        self.tag("v1.1.0")
        result = self.run_cli("plan", "--commit", skipped)
        self.assertEqual(result.code, cli.EXIT_OK)
        self.assertEqual(
            result.stdout, f"commit {skipped} is covered by release v1.1.0\n"
        )
        self.assertEqual(result.stderr, "")
        self.assertEqual(self.gh.calls, [])

    def test_covering_release_is_the_lowest_tag_that_contains_the_commit(self) -> None:
        """With two later releases, the report names the first of them."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        skipped = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.commit({"flake.nix": "{ }\n"}, "fix: change the flake")
        self.tag("v1.9.0")
        self.commit({"flake.nix": "{  }\n"}, "fix: change the flake again")
        self.tag("v1.10.0")
        result = self.run_cli("plan", "--commit", skipped)
        self.assertEqual(
            result.stdout, f"commit {skipped} is covered by release v1.9.0\n"
        )

    def test_a_malformed_later_tag_does_not_cover_the_commit(self) -> None:
        """Only a strict release tag covers: `v1.2` on a later commit is none."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        skipped = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.commit({"flake.nix": "{ }\n"}, "fix: change the flake")
        for name in ("v1.2", "v01.2.3", "v1.2.3-rc1"):
            self.tag(name)
        result = self.run_cli("plan", "--commit", skipped)
        self.assertIn("tag: v1.0.1\n", result.stdout)


class PublishCommandTest(RepoTestCase):
    """`release publish` creates the release that a commit lacks, or nothing."""

    def test_publish_creates_the_release_at_the_commit(self) -> None:
        """The call names the tag, the full commit, the title and the notes.

        A second call reads the tag back from GitHub.
        """
        head = self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        result = self.run_cli("publish", "--commit", head)
        self.assertEqual(result.code, cli.EXIT_OK)
        self.assertEqual(result.stdout, f"released v1.0.0 at commit {head}\n")
        self.assertEqual(
            self.gh.calls,
            [
                (
                    [
                        "release",
                        "create",
                        "v1.0.0",
                        "--target",
                        head,
                        "--title",
                        "v1.0.0",
                        "--notes-file",
                        "-",
                    ],
                    "rules changed: yes\n\n- `feat: add the flake`\n",
                ),
                (["api", "repos/{owner}/{repo}/git/ref/tags/v1.0.0"], None),
            ],
        )

    def test_publish_fails_when_the_tag_appeared_on_github_at_another_commit(
        self,
    ) -> None:
        """GitHub ignores `--target` for an existing tag: exit 1, no success text.

        The local clone has no `v1.0.0`, so the plan asks for it. Between the
        checkout and the call, someone made the tag on another commit.
        """
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        other = "0123456789abcdef0123456789abcdef01234567"
        self.gh.remote_tags["v1.0.0"] = other
        result = self.run_cli("publish")
        self.assertEqual(result.code, cli.EXIT_CANNOT_RELEASE)
        self.assertEqual(result.stdout, "")
        self.assertIn("v1.0.0", result.stderr)
        self.assertIn(other, result.stderr)

    def test_publish_accepts_an_annotated_tag_on_the_commit(self) -> None:
        """The check follows an annotated tag to its commit."""
        head = self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.gh.remote_tags["v1.0.0"] = head
        self.gh.annotated_tags.add("v1.0.0")
        result = self.run_cli("publish")
        self.assertEqual(result.code, cli.EXIT_OK)
        self.assertEqual(result.stdout, f"released v1.0.0 at commit {head}\n")

    def test_publish_leaves_the_local_tags_alone(self) -> None:
        """The tag is made by GitHub, so the local repository gets none."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.run_cli("publish")
        self.assertEqual(self.tag_names(), [])

    def test_publish_of_a_commit_with_a_release_does_nothing_and_succeeds(self) -> None:
        """Running twice is safe: the second run asks GitHub and creates nothing."""
        head = self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.gh.releases.add("v1.0.0")
        result = self.run_cli("publish")
        self.assertEqual(result.code, cli.EXIT_OK)
        self.assertEqual(
            result.stdout, f"commit {head} is already released as v1.0.0\n"
        )
        self.assertEqual(
            self.gh.calls, [(["release", "view", "v1.0.0", "--json", "tagName"], None)]
        )

    def test_publish_creates_the_release_that_an_existing_tag_lacks(self) -> None:
        """A tag without a release gets the release, from the release before it.

        `v1.0.0` has its release. The commit after it carries `v1.0.1`, and
        GitHub has no release for that tag. The notes cover the commit since
        `v1.0.0`, and the call checks the tag instead of moving it.
        """
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        head = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.tag("v1.0.1")
        self.gh.releases.add("v1.0.0")
        result = self.run_cli("publish")
        self.assertEqual(result.code, cli.EXIT_OK)
        self.assertEqual(
            result.stdout,
            f"commit {head} carries the tag v1.0.1 without a release: "
            "created the release for the existing tag\n",
        )
        self.assertEqual(
            self.gh.calls,
            [
                (["release", "view", "v1.0.1", "--json", "tagName"], None),
                (
                    [
                        "release",
                        "create",
                        "v1.0.1",
                        "--verify-tag",
                        "--title",
                        "v1.0.1",
                        "--notes-file",
                        "-",
                    ],
                    "rules changed: no\n\n- `docs: add a page`\n",
                ),
            ],
        )
        self.assertEqual(self.gh.releases, {"v1.0.0", "v1.0.1"})
        self.assertEqual(self.tag_names(), ["v1.0.0", "v1.0.1"])

    def test_missing_release_of_the_first_tag_lists_the_whole_history(self) -> None:
        """Without an earlier release tag the notes say `yes` and list all."""
        self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.commit({"docs/reference/b.txt": "b\n"}, "docs: add another page")
        self.tag("v1.0.0")
        self.run_cli("publish")
        notes = self.gh.calls[-1][1]
        self.assertEqual(
            notes,
            "rules changed: yes\n\n- `docs: add another page`\n- `docs: add a page`\n",
        )

    def test_missing_release_ignores_a_second_tag_on_the_same_commit(self) -> None:
        """The release before a tag is an earlier commit's tag, not its sibling."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.commit({"flake.nix": "{ }\n"}, "fix: change the flake")
        self.tag("v1.1.0")
        self.tag("v1.1.1")
        self.gh.releases.update({"v1.0.0", "v1.1.0"})
        self.run_cli("publish")
        call, notes = self.gh.calls[-1]
        self.assertEqual(call[2], "v1.1.1")
        self.assertEqual(notes, "rules changed: yes\n\n- `fix: change the flake`\n")

    def test_publish_stops_when_github_cannot_say_whether_the_release_exists(
        self,
    ) -> None:
        """A failure of `gh release view` that is no missing release creates nothing."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.gh.view_failure = "HTTP 403: Resource not accessible by integration"
        result = self.run_cli("publish")
        self.assertEqual(result.code, cli.EXIT_CANNOT_RELEASE)
        self.assertIn("HTTP 403", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            self.gh.calls, [(["release", "view", "v1.0.0", "--json", "tagName"], None)]
        )
        self.assertEqual(self.gh.releases, set())

    def test_plan_of_a_tagged_commit_does_not_call_gh(self) -> None:
        """`plan` has no side effect and needs no network, so it never asks."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.run_cli("plan")
        self.assertEqual(self.gh.calls, [])

    def test_publish_of_a_covered_commit_creates_nothing_and_succeeds(self) -> None:
        """The re-run of an old run must not create a tag behind a newer release.

        `v1.0.0` exists. X is a documentation commit whose run was replaced, so
        it has no release. Y changes a rule and is released as `v1.1.0`, with
        notes that cover X. Re-running X exits 0 and creates nothing.
        """
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        skipped = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        self.commit({"flake.nix": "{ }\n"}, "fix: change the flake")
        self.tag("v1.1.0")
        result = self.run_cli("publish", "--commit", skipped)
        self.assertEqual(result.code, cli.EXIT_OK)
        self.assertEqual(
            result.stdout, f"commit {skipped} is covered by release v1.1.0\n"
        )
        self.assertEqual(self.gh.calls, [])
        self.assertEqual(self.tag_names(), ["v1.0.0", "v1.1.0"])

    def test_publish_fails_when_the_tag_exists_on_a_commit_without_this_one(
        self,
    ) -> None:
        """The version is taken on another branch: exit 1, the tag named, no call."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.git(["switch", "--quiet", "--create", "side"])
        self.commit({"docs/reference/side.txt": "s\n"}, "docs: side page")
        self.tag("v1.0.1")
        self.git(["switch", "--quiet", "main"])
        main_commit = self.commit({"docs/reference/a.txt": "a\n"}, "docs: add a page")
        result = self.run_cli("publish", "--commit", main_commit)
        self.assertEqual(result.code, cli.EXIT_CANNOT_RELEASE)
        self.assertIn("v1.0.1", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.gh.calls, [])

    def test_publish_reports_that_the_tag_exists_on_github(self) -> None:
        """GitHub refuses the call with "tag exists": exit 1, the message, no retry."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.gh.create_failure = "HTTP 422: tag_name already exists"
        result = self.run_cli("publish")
        self.assertEqual(result.code, cli.EXIT_CANNOT_RELEASE)
        self.assertIn("tag_name already exists", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(len(self.gh.calls), 1)
        self.assertEqual(self.gh.releases, set())

    def test_failed_creation_for_an_existing_tag_exits_1(self) -> None:
        """`--verify-tag` fails when GitHub does not hold the tag: exit 1."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.tag("v1.0.0")
        self.gh.create_failure = "tag v1.0.0 doesn't exist in the repo"
        result = self.run_cli("publish")
        self.assertEqual(result.code, cli.EXIT_CANNOT_RELEASE)
        self.assertIn("doesn't exist in the repo", result.stderr)
        self.assertEqual(self.gh.releases, set())

    def test_publish_reports_a_failure_of_gh(self) -> None:
        """A failing `gh` gives exit status 1 and its message."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        self.gh.failure = "gh release create failed: HTTP 403"
        result = self.run_cli("publish")
        self.assertEqual(result.code, cli.EXIT_CANNOT_RELEASE)
        self.assertEqual(result.stderr, "release: gh release create failed: HTTP 403\n")
        self.assertEqual(result.stdout, "")

    def test_publish_of_a_name_that_is_no_commit_fails(self) -> None:
        """A revision that git does not know gives exit status 1."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        result = self.run_cli("publish", "--commit", "no-such-revision")
        self.assertEqual(result.code, cli.EXIT_CANNOT_RELEASE)
        self.assertIn("no-such-revision", result.stderr)
        self.assertEqual(self.gh.calls, [])


class UsageTest(RepoTestCase):
    """A wrong command line and a bug have their own exit statuses."""

    def test_missing_command_is_a_usage_error(self) -> None:
        """No command gives exit status 2 and the usage text."""
        result = self.run_cli()
        self.assertEqual(result.code, cli.EXIT_USAGE)
        self.assertIn("usage: release", result.stderr)

    def test_unknown_command_and_option_are_usage_errors(self) -> None:
        """An unknown command and an unknown option give exit status 2."""
        for args in (("tag",), ("plan", "--force"), ("publish", "extra")):
            with self.subTest(args=args):
                self.assertEqual(self.run_cli(*args).code, cli.EXIT_USAGE)

    def test_unexpected_exception_is_an_internal_error(self) -> None:
        """A bug gives exit status 3 and a traceback, not status 1."""
        self.commit({"flake.nix": "{}\n"}, "feat: add the flake")
        with mock.patch("release.cli.plan_release", side_effect=RuntimeError("bug")):
            result = self.run_cli("plan")
        self.assertEqual(result.code, cli.EXIT_INTERNAL)
        self.assertIn("RuntimeError: bug", result.stderr)
        self.assertIn("internal error", result.stderr)
