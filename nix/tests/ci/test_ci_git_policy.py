"""Tests for the job `git-policy` of `.github/workflows/ci.yml`.

The job runs the commit and branch checks of the hub on every pull request. No
other test reaches it: a flake check sees no Git history, and the aggregate job
`ci` stays green for a job that checks nothing. These tests read the wiring of
the job from the workflow file, so a change that makes the job check the wrong
range, or nothing, turns a test red. The path of the workflow comes from the
environment variable `CI_WORKFLOW`, as in `test_ci_aggregate`.
"""

import unittest
from typing import Any

from test_ci_aggregate import load_jobs

JOB = "git-policy"

# The command of each check, and the expression that gives each input of it.
RANGE_COMMAND = 'nix run .#gitpolicy -- range "$BASE_SHA..$HEAD_SHA"'
BRANCH_COMMAND = 'nix run .#gitpolicy -- branch -- "$HEAD_REF"'
INPUT_EXPRESSIONS = {
    "BASE_SHA": "${{ github.event.pull_request.base.sha }}",
    "HEAD_SHA": "${{ github.event.pull_request.head.sha }}",
    "HEAD_REF": "${{ github.head_ref }}",
}


def steps_by_command() -> dict[str, dict[str, Any]]:
    """Return the steps of the job that run a command, by the command."""
    steps: list[dict[str, Any]] = load_jobs()[JOB]["steps"]
    return {step["run"].strip(): step for step in steps if "run" in step}


class GitPolicyJobTest(unittest.TestCase):
    """The job checks the range of the pull request and the name of its branch."""

    def step_running(self, command: str) -> dict[str, Any]:
        """Return the step that runs the command, or fail and name the commands."""
        steps = steps_by_command()
        if command not in steps:
            self.fail(f"no step runs {command!r}; the steps run {sorted(steps)}")
        return steps[command]

    def test_the_job_runs_on_pull_requests_only(self) -> None:
        """On a push to `main` the commits have landed, so the job is skipped.

        The aggregate job `ci` accepts exactly this skip, so the condition and
        that rule must agree.
        """
        self.assertEqual("github.event_name == 'pull_request'", load_jobs()[JOB]["if"])

    def test_the_commit_check_gets_the_range_of_the_pull_request(self) -> None:
        """The range runs from the base commit to the head commit of the event."""
        step = self.step_running(RANGE_COMMAND)
        self.assertEqual(
            {name: INPUT_EXPRESSIONS[name] for name in ("BASE_SHA", "HEAD_SHA")},
            step["env"],
        )

    def test_the_branch_check_ends_the_options_before_the_name(self) -> None:
        """`--` makes a name like `--help` a name, so it fails as a bad name."""
        step = self.step_running(BRANCH_COMMAND)
        self.assertEqual({"HEAD_REF": INPUT_EXPRESSIONS["HEAD_REF"]}, step["env"])

    def test_the_branch_check_runs_after_a_failed_commit_check(self) -> None:
        """One run shows both problems, unless the run is cancelled."""
        step = self.step_running(BRANCH_COMMAND)
        self.assertEqual("${{ !cancelled() }}", step.get("if"))

    def test_the_job_runs_no_other_command(self) -> None:
        """The two checks are the whole job, so a dropped check is a red test."""
        self.assertEqual({RANGE_COMMAND, BRANCH_COMMAND}, set(steps_by_command()))

    def test_the_checkout_fetches_the_whole_history(self) -> None:
        """The range needs the base commit, which a shallow clone does not hold."""
        steps: list[dict[str, Any]] = load_jobs()[JOB]["steps"]
        checkouts = [
            s for s in steps if s.get("uses", "").startswith("actions/checkout@")
        ]
        self.assertEqual(1, len(checkouts), checkouts)
        self.assertEqual(0, checkouts[0]["with"]["fetch-depth"])
        self.assertIs(False, checkouts[0]["with"]["persist-credentials"])

    def test_no_value_of_the_event_reaches_a_shell_script_directly(self) -> None:
        """A `${{ }}` expression in a `run` body would let a branch name inject code."""
        for command in steps_by_command():
            with self.subTest(command):
                self.assertNotIn("${{", command)


if __name__ == "__main__":
    unittest.main()
