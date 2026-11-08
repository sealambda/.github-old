"""Tests for `decisions retire`: what it writes, prints and refuses."""

import contextlib
import unittest
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

from decisions import git
from decisions.ledger_edit import LEDGER_HEADER
from decisions.retire import plan_retirement
from gitsupport import FIRST, ORIGIN_URL, SECOND, TODAY, GitTestCase
from support import FRONT_MATTER, ledger_entry, record_text

LEDGER = "docs/decisions/superseded.yaml"
"""The path of the ledger in the work tree of the tests."""


@contextlib.contextmanager
def failing_git_commands(*subcommands: str) -> Iterator[None]:
    """Make the tool's calls of `git <subcommand>` fail, and run the others.

    Args:
        *subcommands: The git subcommands that fail, such as `add`. The failure
            is a `GitError` with the message `boom`, as a refusal of git is.
    """
    real_run_git = git.run_git

    def run_git(root: Path, *args: str) -> str:
        """Fail for the chosen subcommands and delegate every other call."""
        if args[0] in subcommands:
            raise git.GitError(f"git {args[0]} failed: boom")
        return real_run_git(root, *args)

    with mock.patch.object(git, "run_git", run_git):
        yield


def expected_entry(
    commit: str, successor: str | None, number: str = "0001", slug: str = "first"
) -> str:
    """Return the ledger entry that `retire` writes for a record of the tests."""
    title = {"first": "First decision", "second": "Second decision"}[slug]
    lines = [
        f'- number: "{number}"',
        f"  title: {title}",
        f"  commit: {commit}",
        f"  path: docs/decisions/{number}-{slug}.md",
    ]
    if successor is not None:
        lines.append(f'  successor: "{successor}"')
    lines.append(f"  date: {TODAY.isoformat()}")
    return "\n".join(lines) + "\n"


class RetireByTest(GitTestCase):
    """`retire NNNN --by MMMM` on a record that reached `origin/main`."""

    def setUp(self) -> None:
        """Publish two records, then retire the first by the second."""
        super().setUp()
        self.commits = self.publish_records()
        self.result = self.run_retire("0001", "--by", "0002")

    def test_exits_0_and_prints_the_title_and_the_permalink(self) -> None:
        """The output names the record and the permalink of its last text."""
        self.assertEqual(self.result.code, 0, self.result.stderr)
        link = (
            "https://github.com/acme/hub/blob/"
            f"{self.commits[FIRST]}/docs/decisions/0001-first.md"
        )
        self.assertEqual(
            self.result.stdout.splitlines(),
            [
                "retired record 0001: First decision",
                f"permalink: {link}",
                "the check reports no finding",
            ],
        )

    def test_stages_the_deletion_of_the_record(self) -> None:
        """The record leaves the work tree and the index."""
        self.assertFalse((self.root / FIRST).exists())
        self.assertIn(f"D  {FIRST}", self.git("status", "--porcelain").splitlines())

    def test_creates_the_ledger_with_the_entry(self) -> None:
        """A new ledger holds the header and one entry with the last commit."""
        self.assertEqual(
            self.ledger_text(),
            LEDGER_HEADER + expected_entry(self.commits[FIRST], "0002"),
        )

    def test_leaves_the_other_record_alone(self) -> None:
        """Only the retired record is deleted."""
        self.assertTrue((self.root / SECOND).exists())


class StagingTest(GitTestCase):
    """The deletion and the ledger are staged together, so `git commit` keeps both."""

    def test_new_ledger_is_staged_with_the_deletion(self) -> None:
        """A commit without `-a` records the deletion and the new ledger."""
        self.publish_records()
        self.assertEqual(self.run_retire("0001", "--by", "0002").code, 0)
        self.assertEqual(
            self.git("diff", "--cached", "--name-status").splitlines(),
            [f"D\t{FIRST}", f"A\t{LEDGER}"],
        )
        self.assertEqual(self.git("diff", "--name-status"), "")

    def test_changed_ledger_is_staged_with_the_deletion(self) -> None:
        """An existing ledger shows as modified in the index."""
        self.publish_records()
        self.commit({LEDGER: "# Comment.\n" + ledger_entry("0003", "0002")})
        self.assertEqual(self.run_retire("0001", "--by", "0002").code, 0)
        self.assertEqual(
            self.git("diff", "--cached", "--name-status").splitlines(),
            [f"D\t{FIRST}", f"M\t{LEDGER}"],
        )
        self.assertEqual(self.git("diff", "--name-status"), "")


class RenamedRecordTest(GitTestCase):
    """A record that an unmerged parent pull request moved is still published.

    `origin/main` holds the records in `docs/adr`. The local branch moves the
    folder to `docs/decisions` in a commit that is not on `origin/main`, as the
    parent branch of a stack does. The retiring branch sits on top of it.
    """

    OLD_FIRST = "docs/adr/0001-first.md"
    """Where `origin/main` has the first record."""

    OLD_SECOND = "docs/adr/0002-second.md"
    """Where `origin/main` has the second record."""

    def setUp(self) -> None:
        """Publish two records in `docs/adr`, then move them here only."""
        super().setUp()
        self.first_commit = self.commit(
            {self.OLD_FIRST: record_text("# First decision\n")}, "add the first record"
        )
        self.commit(
            {self.OLD_SECOND: record_text("# Second decision\n")},
            "add the second record",
        )
        self.commit({"README.md": "A repository.\n"}, "add a readme")
        self.push()
        self.set_origin_url(ORIGIN_URL)
        self.git("mv", "docs/adr", "docs/decisions")
        self.commit({}, "move the records to docs/decisions")

    def test_retires_a_record_that_only_the_parent_branch_moved(self) -> None:
        """The ledger keeps the path and the commit that `origin/main` has."""
        result = self.run_retire("0001", "--by", "0002")
        self.assertEqual(result.code, 0, result.stderr)
        link = f"https://github.com/acme/hub/blob/{self.first_commit}/{self.OLD_FIRST}"
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "retired record 0001: First decision",
                f"permalink: {link}",
                "the check reports no finding",
            ],
        )
        self.assertEqual(
            self.ledger_text(),
            LEDGER_HEADER
            + expected_entry(self.first_commit, "0002").replace(FIRST, self.OLD_FIRST),
        )
        self.assertIn(f"D  {FIRST}", self.git("status", "--porcelain").splitlines())

    def test_follows_more_than_one_rename(self) -> None:
        """A later change of the file name does not hide the published path."""
        self.git("mv", FIRST, "docs/decisions/0001-first-decision.md")
        self.commit({}, "give the first record a longer name")
        result = self.run_retire("0001", "--by", "0002")
        self.assertEqual(result.code, 0, result.stderr)
        self.assertIn(f"  path: {self.OLD_FIRST}\n", self.ledger_text() or "")

    def test_refuses_a_text_that_the_branch_changed(self) -> None:
        """The permalink would show the old text, so the retirement stops."""
        self.commit({FIRST: record_text("# First decision\n\nEdited.\n")})
        before = self.tree_state()
        result = self.run_retire("0001", "--by", "0002")
        self.assertEqual(result.code, 2)
        self.assertIn(
            f"docs/decisions/0001-first.md on HEAD differs from origin/main at "
            f"{self.OLD_FIRST}",
            result.stderr,
        )
        self.assertEqual(self.tree_state(), before)

    def test_refuses_a_record_that_was_never_published(self) -> None:
        """A record that the branch added and moved has no commit on `origin/main`."""
        old_third = "docs/adr/0003-third.md"
        self.commit({old_third: record_text("# Third\n")}, "add a record")
        self.git("mv", old_third, "docs/decisions/0003-third.md")
        self.commit({}, "move it")
        before = self.tree_state()
        result = self.run_retire("0003", "--by", "0002")
        self.assertEqual(result.code, 2)
        self.assertIn("has never been on origin/main", result.stderr)
        self.assertEqual(self.tree_state(), before)


class CommitChoiceTest(GitTestCase):
    """The entry holds the last commit of the record on `origin/main`."""

    def test_commit_is_the_last_one_that_changed_the_record(self) -> None:
        """A later change to the record moves the commit, not an unrelated one."""
        self.publish_records()
        changed = self.commit(
            {FIRST: record_text("# First decision\n\nA correction.\n")},
            "correct the first record",
        )
        self.commit({"README.md": "Another line.\n"}, "change the readme")
        self.push()
        result = self.run_retire("0001", "--by", "0002")
        self.assertEqual(result.code, 0, result.stderr)
        self.assertIn(f"  commit: {changed}\n", self.ledger_text() or "")

    def test_commit_ignores_a_local_commit_that_is_not_on_origin(self) -> None:
        """The permalink must open, so a commit that only exists here is skipped."""
        commits = self.publish_records()
        self.commit({"README.md": "Local only.\n"}, "change the readme")
        result = self.run_retire("0001", "--by", "0002")
        self.assertEqual(result.code, 0, result.stderr)
        self.assertIn(f"  commit: {commits[FIRST]}\n", self.ledger_text() or "")


class RetireWithdrawnTest(GitTestCase):
    """`retire NNNN --withdrawn` writes an entry without a successor."""

    def test_entry_has_no_successor(self) -> None:
        """A withdrawn record has no `successor` key."""
        commits = self.publish_records()
        result = self.run_retire("0002", "--withdrawn")
        self.assertEqual(result.code, 0, result.stderr)
        self.assertEqual(
            self.ledger_text(),
            LEDGER_HEADER
            + expected_entry(commits[SECOND], None, number="0002", slug="second"),
        )
        self.assertNotIn("successor", self.ledger_text() or "")

    def test_withdrawal_is_refused_when_an_entry_names_the_record(self) -> None:
        """A chained entry would keep a successor that is not in force."""
        self.publish_records()
        self.write({"docs/decisions/superseded.yaml": ledger_entry("0003", "0002")})
        before = self.tree_state()
        result = self.run_retire("0002", "--withdrawn")
        self.assertEqual(result.code, 2)
        self.assertIn("successor of 0003", result.stderr)
        self.assertEqual(self.tree_state(), before)


class ChainedSuccessorTest(GitTestCase):
    """Entries that name the retired record get the new successor."""

    LEDGER = (
        "# Kept comment.\n"
        "\n"
        '- number: "0003"\n'
        "  title: Old record\n"
        f"  commit: {'a1' * 20}\n"
        "  path: docs/decisions/0003-old.md\n"
        "  successor: '0001'  # chained\n"
        "  date: 2026-02-03\n"
        '- successor: "0001"\n'
        '  number: "0004"\n'
        "  title: Other\n"
        f"  commit: {'b2' * 20}\n"
        "  path: docs/decisions/0004-other.md\n"
        "  date: 2026-02-04\n"
        '- number: "0005"\n'
        "  title: Unrelated\n"
        f"  commit: {'c3' * 20}\n"
        "  path: docs/decisions/0005-unrelated.md\n"
        '  successor: "0002"\n'
        "  date: 2026-02-05\n"
    )

    def test_rewrites_only_the_successor_lines(self) -> None:
        """Quotes, comments and the key order stay; the entry is appended."""
        commits = self.publish_records()
        self.write({"docs/decisions/superseded.yaml": self.LEDGER})
        result = self.run_retire("0001", "--by", "0002")
        self.assertEqual(result.code, 0, result.stderr)
        expected = self.LEDGER.replace(
            "successor: '0001'", "successor: '0002'"
        ).replace('- successor: "0001"', '- successor: "0002"') + expected_entry(
            commits[FIRST], "0002"
        )
        self.assertEqual(self.ledger_text(), expected)
        self.assertIn("successor changed to 0002 in: 0003, 0004", result.stdout)

    def test_flow_style_successor_is_refused(self) -> None:
        """A line that the edit cannot change safely stops the retirement."""
        self.publish_records()
        flow = (
            '- {number: "0003", title: Old, '
            f"commit: {'a1' * 20}, path: docs/decisions/0003-old.md, "
            'successor: "0001", date: 2026-02-03}\n'
        )
        self.write({"docs/decisions/superseded.yaml": flow})
        before = self.tree_state()
        result = self.run_retire("0001", "--by", "0002")
        self.assertEqual(result.code, 2)
        self.assertIn("cannot rewrite the successor 0001", result.stderr)
        self.assertEqual(self.tree_state(), before)


class RefusalTest(GitTestCase):
    """Each rule that refuses exits 2, prints why and changes nothing."""

    def setUp(self) -> None:
        """Publish two records."""
        super().setUp()
        self.publish_records()

    def assert_refused(self, message: str, *args: str) -> None:
        """Run `retire` with `args` and check the refusal and the unchanged tree.

        Args:
            message: Text that the error output must contain.
            *args: The arguments after `retire`.
        """
        before = self.tree_state()
        result = self.run_retire(*args)
        self.assertEqual(result.code, 2, result.stdout)
        self.assertIn(message, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.tree_state(), before)

    def test_record_that_is_not_on_origin_main(self) -> None:
        """A record committed here only has no permalink that others can open."""
        self.commit({"docs/decisions/0003-third.md": record_text("# Third\n")})
        self.assert_refused("has never been on origin/main", "0003", "--by", "0002")

    def test_record_that_is_not_committed(self) -> None:
        """An untracked record never reached `origin/main` either."""
        self.write({"docs/decisions/0003-third.md": record_text("# Third\n")})
        self.assert_refused("has never been on origin/main", "0003", "--by", "0002")

    def test_the_message_says_to_fetch(self) -> None:
        """The command does not fetch, and the message tells the person to."""
        self.commit({"docs/decisions/0003-third.md": record_text("# Third\n")})
        self.assert_refused("run `git fetch`", "0003", "--by", "0002")

    def test_unknown_record(self) -> None:
        """A number without a record file is refused."""
        self.assert_refused(
            "no record file docs/decisions/0009-*.md", "0009", "--withdrawn"
        )

    def test_record_already_in_the_ledger(self) -> None:
        """A second retirement of the same number is refused."""
        self.assertEqual(self.run_retire("0001", "--by", "0002").code, 0)
        self.assert_refused(
            "record 0001 is already in the ledger", "0001", "--withdrawn"
        )

    def test_successor_that_does_not_exist(self) -> None:
        """`--by` must name a record file."""
        self.assert_refused(
            "--by 0009 is not a record in force", "0001", "--by", "0009"
        )

    def test_successor_that_is_the_record_itself(self) -> None:
        """A record cannot replace itself."""
        self.assert_refused("its own successor", "0001", "--by", "0001")

    def test_successor_that_is_in_the_ledger(self) -> None:
        """`--by` names a record in force, not a retired one."""
        self.assertEqual(self.run_retire("0001", "--by", "0002").code, 0)
        self.commit({"docs/decisions/0003-third.md": record_text("# Third\n")})
        self.push()
        self.assert_refused(
            "--by 0001 is not a record in force", "0003", "--by", "0001"
        )

    def test_record_with_uncommitted_changes(self) -> None:
        """Local edits would be lost: the record must match its commit."""
        self.write({FIRST: record_text("# First decision\n\nEdited.\n")})
        self.assert_refused("has uncommitted changes", "0001", "--by", "0002")

    def test_record_that_differs_from_origin_main(self) -> None:
        """The permalink must show the text that this tree deletes."""
        self.commit({FIRST: record_text("# First decision\n\nEdited.\n")})
        self.assert_refused("differs from origin/main", "0001", "--by", "0002")

    def test_origin_that_is_not_on_github(self) -> None:
        """The permalink formula is GitHub's."""
        self.set_origin_url("https://gitlab.example.com/acme/hub.git")
        self.assert_refused("not a github.com repository URL", "0001", "--by", "0002")

    def test_origin_url_credentials_are_never_printed(self) -> None:
        """A token in the URL of `origin` must not reach the logs of a CI run."""
        for url in (
            "https://x-access-token:ghs_SECRET@gitlab.example.com/acme/hub.git",
            "https://x-access-token:ghs_SECRET@github.com/acme",
            "ghs_SECRET@gitlab.example.com:acme/hub.git",
        ):
            with self.subTest(url=url):
                self.set_origin_url(url)
                result = self.run_retire("0001", "--by", "0002")
                self.assertEqual(result.code, 2)
                self.assertIn("not a github.com repository URL", result.stderr)
                self.assertNotIn("SECRET", result.stderr + result.stdout)
                self.assertNotIn("x-access-token", result.stderr + result.stdout)

    def test_ledger_that_is_not_valid(self) -> None:
        """A ledger that the check rejects is not extended."""
        self.write({"docs/decisions/superseded.yaml": "- number: 1\n"})
        self.assert_refused("the ledger is not valid", "0001", "--by", "0002")

    def test_record_without_a_title(self) -> None:
        """The ledger needs a title, from the first level-1 heading."""
        self.commit({"docs/decisions/0003-third.md": FRONT_MATTER + "No heading.\n"})
        self.push()
        self.assert_refused("no level-1 heading", "0003", "--by", "0002")


class NoOriginRefTest(GitTestCase):
    """`origin/main` is a local ref that the command does not fetch."""

    def test_missing_ref_says_to_fetch(self) -> None:
        """Without `origin/main` the command refuses and names `git fetch`."""
        self.commit({FIRST: record_text("# First decision\n")})
        before = self.tree_state()
        result = self.run_retire("0001", "--withdrawn")
        self.assertEqual(result.code, 2)
        self.assertIn("origin/main does not exist here: run `git fetch`", result.stderr)
        self.assertEqual(self.tree_state(), before)


class UsageTest(GitTestCase):
    """The command line of `retire`."""

    def test_by_and_withdrawn_exclude_each_other(self) -> None:
        """Giving both flags is a usage error."""
        result = self.run_retire("0001", "--by", "0002", "--withdrawn")
        self.assertEqual(result.code, 2)
        self.assertIn("not allowed with", result.stderr)

    def test_one_of_the_flags_is_required(self) -> None:
        """Giving neither flag is a usage error."""
        result = self.run_retire("0001")
        self.assertEqual(result.code, 2)
        self.assertIn(
            "one of the arguments --by --withdrawn is required", result.stderr
        )

    def test_numbers_have_four_digits(self) -> None:
        """A number of another shape is a usage error."""
        for args in (("1", "--withdrawn"), ("0001", "--by", "2")):
            with self.subTest(args=args):
                result = self.run_retire(*args)
                self.assertEqual(result.code, 2)
                self.assertIn("four-digit number", result.stderr)

    def test_root_that_is_not_a_repository(self) -> None:
        """A directory outside a git work tree is refused with git's message."""
        outside = self.origin.parent
        result = self.run_retire("0001", "--withdrawn", root=outside)
        self.assertEqual(result.code, 2)
        self.assertIn("git rev-parse --show-toplevel failed", result.stderr)

    def test_root_may_be_a_subdirectory(self) -> None:
        """The command finds the top of the work tree from a subfolder."""
        self.publish_records()
        result = self.run_retire("0001", "--by", "0002", root=self.root / "docs")
        self.assertEqual(result.code, 0, result.stderr)


class FindingsTest(GitTestCase):
    """The check runs after the retirement and its findings are printed."""

    def test_citation_of_the_retired_record_is_reported(self) -> None:
        """A file that still cites the record is a finding to fix."""
        self.publish_records()
        self.commit({"notes.md": "See ADR 0001.\n"})
        result = self.run_retire("0001", "--by", "0002")
        self.assertEqual(result.code, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines()[2:],
            [
                "the check reports 1 finding(s) to fix:",
                "notes.md:1: decision record 0001 was deleted into the ledger: "
                "cite its successor, ADR 0002",
            ],
        )

    def test_exclude_hides_a_fixture_from_the_report(self) -> None:
        """`--exclude` works as it does for `check`."""
        self.publish_records()
        self.commit({"fixtures/notes.md": "See ADR 0001.\n"})
        result = self.run_retire("0001", "--by", "0002", "--exclude", "fixtures")
        self.assertIn("the check reports no finding", result.stdout)


class FinalCheckFailureTest(GitTestCase):
    """A final check that cannot run must not hide a retirement that happened."""

    def test_unreadable_tree_after_the_change_still_exits_0(self) -> None:
        """The record is gone, so the output says so and names the cause."""
        commits = self.publish_records()
        with mock.patch(
            "decisions.retire.run_checks", side_effect=OSError("disk went away")
        ):
            result = self.run_retire("0001", "--by", "0002")
        link = (
            "https://github.com/acme/hub/blob/"
            f"{commits[FIRST]}/docs/decisions/0001-first.md"
        )
        self.assertEqual(result.code, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "retired record 0001: First decision",
                f"permalink: {link}",
                "the final check did not run: disk went away",
                "the record is retired; fix the cause, then run `decisions check`",
            ],
        )
        self.assertFalse((self.root / FIRST).exists())
        self.assertIn(f"D  {FIRST}", self.git("status", "--porcelain").splitlines())


class RollbackTest(GitTestCase):
    """A failure of `git rm` or `git add` leaves the index and the tree as they were."""

    def test_new_ledger_is_removed_again(self) -> None:
        """A ledger that the command created does not stay."""
        self.publish_records()
        before = self.tree_state()
        with mock.patch.object(git, "remove_file", side_effect=git.GitError("boom")):
            result = self.run_retire("0001", "--by", "0002")
        self.assertEqual(result.code, 2)
        self.assertIn("boom", result.stderr)
        self.assertIn("the ledger is restored", result.stderr)
        self.assertEqual(self.tree_state(), before)
        self.assertTrue((self.root / FIRST).exists())

    def test_existing_ledger_text_is_restored(self) -> None:
        """An existing ledger comes back byte for byte."""
        self.publish_records()
        original = "# Comment.\n" + ledger_entry("0003", "0002")
        self.write({"docs/decisions/superseded.yaml": original})
        with mock.patch.object(git, "remove_file", side_effect=git.GitError("boom")):
            result = self.run_retire("0001", "--by", "0002")
        self.assertEqual(result.code, 2)
        self.assertEqual(self.ledger_text(), original)

    def test_failure_to_stage_the_ledger_restores_index_and_tree(self) -> None:
        """The deletion that `git rm` staged is undone, and the new ledger goes."""
        self.publish_records()
        before = self.tree_state()
        with failing_git_commands("add"):
            result = self.run_retire("0001", "--by", "0002")
        self.assertEqual(result.code, 2)
        self.assertIn("boom", result.stderr)
        self.assertIn("the ledger is restored", result.stderr)
        self.assertEqual(self.tree_state(), before)
        self.assertEqual(self.git("diff", "--cached", "--name-status"), "")
        self.assertEqual(self.git("diff", "--name-status"), "")
        self.assertTrue((self.root / FIRST).exists())
        self.assertIsNone(self.ledger_text())

    def test_failure_to_stage_restores_a_committed_ledger(self) -> None:
        """A tracked ledger comes back clean, byte for byte."""
        self.publish_records()
        original = "# Comment.\n" + ledger_entry("0003", "0002")
        self.commit({LEDGER: original})
        with failing_git_commands("add"):
            result = self.run_retire("0001", "--by", "0002")
        self.assertEqual(result.code, 2)
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertEqual(self.ledger_text(), original)

    def test_failure_to_restore_the_record_says_how_to_finish(self) -> None:
        """When the undo fails too, the message names the commands to run."""
        self.publish_records()
        with failing_git_commands("add", "restore"):
            result = self.run_retire("0001", "--by", "0002")
        self.assertEqual(result.code, 2)
        self.assertIn(
            f"git restore --source=HEAD --staged --worktree -- {FIRST}", result.stderr
        )
        self.assertIsNone(self.ledger_text())


class RepositoryNameTest(GitTestCase):
    """The repository of the permalink comes from the URL of `origin`."""

    def test_forms_of_the_origin_url(self) -> None:
        """Each URL form of GitHub gives the same repository."""
        self.publish_records()
        forms = [
            ORIGIN_URL,
            "git@github.com:acme/hub",
            "https://github.com/acme/hub.git",
            "https://github.com/acme/hub",
            "ssh://git@github.com/acme/hub.git",
        ]
        for url in forms:
            with self.subTest(url=url):
                self.set_origin_url(url)
                plan = plan_retirement(self.root, "0001", "0002", TODAY)
                self.assertEqual(plan.repository, "acme/hub")

    def test_plan_does_not_change_the_tree(self) -> None:
        """Planning is free of side effects: the files stay."""
        self.publish_records()
        before = self.tree_state()
        plan_retirement(self.root, "0001", "0002", TODAY)
        self.assertEqual(self.tree_state(), before)


if __name__ == "__main__":
    unittest.main()
