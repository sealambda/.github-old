"""Tests for the concurrency group of `.github/workflows/ci.yml`.

A run that GitHub cancels leaves a failed check `ci` on its commit, because the
job `ci` runs in a cancelled run (`if: always()`) and fails there. A push that
updates a pull request and its base branch together can start two runs for one
head commit. If the second run cancelled the first, the head commit would show
a failed `ci` beside a passed one. The group of a pull request therefore names
the head commit, and no run cancels another run. A run on `main` is never
cancelled either, because a cancelled run could leave a merge without its
release.

The aggregate job must still fail when a person cancels the only run. That
guarantee is the job of `test_ci_aggregate`, not of these tests.

The tests read the group and the cancellation setting from the workflow file.
They render the group for sample events with a small substitution of the
`${{ ... }}` expressions, so they show which runs share a group. The path of
the workflow comes from the environment variable `CI_WORKFLOW`, as in
`test_ci_aggregate`.
"""

import re
import unittest
from typing import Any

from test_ci_aggregate import load_jobs, load_workflow

# The text of one `${{ ... }}` expression in a group.
EXPRESSION = re.compile(r"\$\{\{\s*(?P<name>[^}\s]+)\s*\}\}")

HEAD_SHA = "pull_request_head_commit"


def pull_request_context(number: int, head_sha: str) -> dict[str, str]:
    """Return the context values of a `pull_request` event.

    GitHub names the ref of a pull request `refs/pull/<number>/merge`.
    """
    return {
        "github.workflow": "CI",
        "github.ref": f"refs/pull/{number}/merge",
        "github.event.pull_request.head.sha": head_sha,
    }


def push_context(branch: str) -> dict[str, str]:
    """Return the context values of a `push` event.

    A push event has no `pull_request` payload, and GitHub renders a missing
    property of the event as an empty string.
    """
    return {
        "github.workflow": "CI",
        "github.ref": f"refs/heads/{branch}",
        "github.event.pull_request.head.sha": "",
    }


def concurrency() -> dict[str, Any]:
    """Return the `concurrency` mapping of the workflow."""
    value = load_workflow()["concurrency"]
    assert isinstance(value, dict), value
    return value


def render_group(context: dict[str, str]) -> str:
    """Return the group of a run, with each expression replaced by its value.

    Raises:
        KeyError: The group uses an expression that the context does not hold.
            The test then needs the new value, so the failure is a visible one.
    """
    return EXPRESSION.sub(lambda m: context[m["name"]], concurrency()["group"])


class ConcurrencyGroupTest(unittest.TestCase):
    """No run cancels another run, and a pull request run groups by commit."""

    def test_no_run_cancels_another_run(self) -> None:
        """`cancel-in-progress` is the literal `false`, not an expression.

        A cancelled run would leave a failed `ci` on its commit, and a
        cancelled run on `main` could leave a merge without its release. An
        expression is no better than `true`, because the test cannot tell
        which value it takes.
        """
        self.assertIs(False, concurrency()["cancel-in-progress"])

    def test_no_job_sets_a_group_of_its_own(self) -> None:
        """A group on a job would not be the group that these tests read."""
        for name, job in load_jobs().items():
            with self.subTest(job=name):
                self.assertNotIn("concurrency", job)

    def test_two_runs_for_one_head_commit_share_a_group(self) -> None:
        """The two runs of one head commit wait for each other and both finish."""
        context = pull_request_context(10, HEAD_SHA)
        self.assertEqual(render_group(context), render_group(dict(context)))

    def test_a_new_head_commit_starts_a_group_of_its_own(self) -> None:
        """The run of the older commit is not in the way of the newer commit."""
        self.assertNotEqual(
            render_group(pull_request_context(10, HEAD_SHA)),
            render_group(pull_request_context(10, "newer_head_commit")),
        )

    def test_two_pull_requests_with_one_head_commit_do_not_share_a_group(
        self,
    ) -> None:
        """The ref of the pull request keeps unrelated pull requests apart."""
        self.assertNotEqual(
            render_group(pull_request_context(10, HEAD_SHA)),
            render_group(pull_request_context(11, HEAD_SHA)),
        )

    def test_a_push_to_main_has_a_group_for_the_branch(self) -> None:
        """Every push to `main` shares one group, which no pull request joins.

        The group of a push holds no commit, because the event has none. Two
        pushes to `main` therefore queue behind each other, so the releases
        follow the order of the pushes.
        """
        main = render_group(push_context("main"))
        self.assertNotEqual(main, render_group(pull_request_context(10, HEAD_SHA)))
        self.assertNotEqual(main, render_group(push_context("other")))


if __name__ == "__main__":
    unittest.main()
