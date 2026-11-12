"""Tests of the command line of the workflow check."""

import contextlib
import io
import unittest
from unittest import mock

from workflows import cli
from workflows_fixtures import WORKFLOW_PATH, TreeTestCase, job, workflow


class CommandLineTest(TreeTestCase):
    """Exit statuses and output streams."""

    def test_clean_tree_exits_zero_and_prints_nothing(self) -> None:
        """A tree with no workflow is clean."""
        self.assertEqual(self.run_cli(), (0, [], ""))

    def test_clean_workflow_exits_zero(self) -> None:
        """A workflow that meets both rules is clean."""
        self.write(
            WORKFLOW_PATH,
            workflow("push", job("build", "timeout-minutes: 5")),
        )
        self.assertEqual(self.run_cli(), (0, [], ""))

    def test_findings_of_both_rules_come_in_one_run_sorted_by_path_and_line(
        self,
    ) -> None:
        """One run reports every finding, for both rules."""
        self.write(WORKFLOW_PATH, workflow("pull_request", job("build")))
        self.write(".github/workflows/a.yml", workflow("push", job("x")))
        status, lines, stderr = self.run_cli()
        self.assertEqual(status, 1)
        self.assertEqual(
            [line.split(": ", 1)[0] for line in lines],
            [".github/workflows/a.yml:4", f"{WORKFLOW_PATH}:2", f"{WORKFLOW_PATH}:4"],
        )
        self.assertIn("3 finding(s)", stderr)

    def test_missing_root_is_a_usage_error(self) -> None:
        """A root that isn't a directory exits 2."""
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            status = cli.main([str(self.root / "missing")])
        self.assertEqual(status, 2)
        self.assertIn("ROOT is not a directory", stderr.getvalue())

    def test_missing_argument_is_a_usage_error(self) -> None:
        """No ROOT exits 2 and names the missing argument."""
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            status = cli.main([])
        self.assertEqual(status, 2)
        self.assertIn("arguments are required: ROOT", stderr.getvalue())

    def test_unreadable_file_is_an_exit_status_two(self) -> None:
        """An `OSError` from the walk is a status 2, not a traceback."""
        stderr = io.StringIO()
        with (
            mock.patch.object(cli, "check_tree", side_effect=PermissionError("denied")),
            contextlib.redirect_stderr(stderr),
        ):
            status = cli.main([str(self.root)])
        self.assertEqual(status, 2)
        self.assertIn("workflows: denied", stderr.getvalue())

    def test_a_bug_is_an_exit_status_three_with_the_trace(self) -> None:
        """An unexpected exception is a status 3, apart from findings."""
        stderr = io.StringIO()
        with (
            mock.patch.object(cli, "check_tree", side_effect=RuntimeError("boom")),
            contextlib.redirect_stderr(stderr),
        ):
            status = cli.main([str(self.root)])
        self.assertEqual(status, 3)
        self.assertIn("RuntimeError: boom", stderr.getvalue())
        self.assertIn("internal error", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
