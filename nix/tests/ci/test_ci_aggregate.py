"""Tests for the aggregate job `ci` of `.github/workflows/ci.yml`.

The job is the one required status check of the hub: it must fail unless every
job that it needs succeeded. A skipped job is the dangerous case, because a
skipped required check can read as a pass. The only accepted skip is
`git-policy` on a push, because that job runs on pull requests only.

The tests read the `jq` program out of the workflow file, so they test the
text that GitHub runs, not a copy. They run it with `jq` on sample `needs`
objects, which have the shape that `toJSON(needs)` gives: one key per needed
job, with its `result`. The path of the workflow comes from the environment
variable `CI_WORKFLOW`, which the flake check sets.

The program is only half of the guarantee. The job also has to receive the
real `needs` and the real event, to run when a needed job fails, to list every
job that runs before it, and to be free of `continue-on-error`. The wiring
tests read these facts from the same workflow file, so a change that weakens
the job without touching the program turns a test red.
"""

import json
import os
import shlex
import subprocess
import unittest
from pathlib import Path
from typing import Any

import yaml

# The job under test, and the only event on which the skippable job may skip.
AGGREGATE_JOB = "ci"

# The only job that may be skipped, and the only event on which it may be.
SKIPPABLE_JOB = "git-policy"
SKIP_EVENT = "push"

# The expressions that hand the real results and the real event to the step.
NEEDS_EXPRESSION = "${{ toJSON(needs) }}"
EVENT_EXPRESSION = "${{ github.event_name }}"

# `jq -e` exits 0 when the last output is true and 1 when it is false or null.
# Any other status is an error of `jq`, for example a program that does not
# compile.
JQ_TRUE = 0
JQ_FALSE = 1


def load_workflow() -> dict[str, Any]:
    """Return the parsed workflow file that `CI_WORKFLOW` names."""
    workflow: dict[str, Any] = yaml.safe_load(
        Path(os.environ["CI_WORKFLOW"]).read_text("utf-8")
    )
    return workflow


def load_jobs() -> dict[str, dict[str, Any]]:
    """Return every job of the workflow that `CI_WORKFLOW` names, by its id."""
    jobs: dict[str, dict[str, Any]] = load_workflow()["jobs"]
    return jobs


def needs_of(job: dict[str, Any]) -> list[str]:
    """Return the ids that a job lists in `needs`: none when it has no key.

    GitHub accepts one id as a string or several as a list.
    """
    needs = job.get("needs", [])
    return [needs] if isinstance(needs, str) else list(needs)


def jobs_after(jobs: dict[str, dict[str, Any]], job_id: str) -> set[str]:
    """Return the jobs that run after a job, directly or through other jobs.

    A job runs after another when it needs it, or needs a job that does.
    """
    after: set[str] = set()
    pending = [job_id]
    while pending:
        current = pending.pop()
        for name, job in jobs.items():
            if current in needs_of(job) and name not in after:
                after.add(name)
                pending.append(name)
    return after


def jq_step(job: dict[str, Any]) -> dict[str, Any]:
    """Return the one step of the job that runs `jq`.

    Raises:
        AssertionError: The job has no such step, or more than one.
    """
    steps: list[dict[str, Any]] = [
        step for step in job["steps"] if "jq" in step.get("run", "")
    ]
    assert len(steps) == 1, steps
    return steps[0]


def jq_program(job: dict[str, Any]) -> str:
    """Return the `jq` program of the job, as the workflow writes it.

    The shell command of the step is split as the shell splits it. It must be
    `echo "$NEEDS" | jq -e --arg event "$EVENT" '<program>'`, and the program
    is its last word. The function fails when the command has another form, so
    that a change of the invocation is a visible change of the test.

    Raises:
        AssertionError: The step has not the expected form.
    """
    words = shlex.split(jq_step(job)["run"])
    start = words.index("jq")
    assert words[start + 1 : start + 5] == ["-e", "--arg", "event", "$EVENT"], words
    assert len(words) == start + 6, words
    return words[-1]


def needs_json(needed: list[str], results: dict[str, str]) -> str:
    """Return the `needs` object that GitHub gives the job.

    Args:
        needed: The jobs that the `ci` job lists in `needs`.
        results: The result of each job that does not succeed. A job that is
            not in the table has the result `success`.
    """
    return json.dumps(
        {
            name: {"result": results.get(name, "success"), "outputs": {}}
            for name in needed
        }
    )


class AggregateJobTest(unittest.TestCase):
    """The `ci` job accepts a run only when every needed job succeeded."""

    jobs: dict[str, dict[str, Any]]
    job: dict[str, Any]
    program: str
    needed: list[str]

    @classmethod
    def setUpClass(cls) -> None:
        """Read the jobs, the `ci` job, its `jq` program and its `needs`."""
        cls.jobs = load_jobs()
        cls.job = cls.jobs[AGGREGATE_JOB]
        cls.program = jq_program(cls.job)
        cls.needed = needs_of(cls.job)

    def exit_status(self, event: str, results: dict[str, str]) -> int:
        """Run the program of the workflow on sample results.

        Args:
            event: The value of `github.event_name`.
            results: The result of each needed job that does not succeed.

        Returns:
            The exit status of `jq`, which is `JQ_TRUE` when the job passes.
        """
        completed = subprocess.run(
            ["jq", "-e", "--arg", "event", event, self.program],
            input=needs_json(self.needed, results),
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertIn(completed.returncode, (JQ_TRUE, JQ_FALSE), completed.stderr)
        return completed.returncode

    def test_the_job_needs_the_skippable_job_and_others(self) -> None:
        """The tests below mean something only if there is a job to skip."""
        self.assertIn(SKIPPABLE_JOB, self.needed)
        self.assertGreater(len(self.needed), 1)

    def test_the_job_runs_even_when_a_needed_job_fails(self) -> None:
        """`if: always()` keeps a failed need from skipping the job.

        A skipped `ci` job would not fail the required check.
        """
        self.assertEqual("always()", self.job.get("if"))

    def test_the_job_needs_every_job_that_runs_before_it(self) -> None:
        """The `needs` of `ci` are all the jobs, less `ci` and what follows it.

        The expected set comes from the workflow: every job except `ci` and
        the jobs that run after it, which cannot be needed without a cycle.
        A job that `needs` leaves out is a job whose failure `ci` does not
        see, and so is a job added to the workflow and not to `needs`.
        """
        expected = (
            set(self.jobs) - {AGGREGATE_JOB} - jobs_after(self.jobs, AGGREGATE_JOB)
        )
        self.assertTrue(expected, "the workflow has no job for `ci` to need")
        self.assertEqual(sorted(expected), sorted(self.needed))
        self.assertEqual(len(self.needed), len(set(self.needed)), self.needed)

    def test_the_step_gets_the_real_needs_and_event(self) -> None:
        """`NEEDS` and `EVENT` are the expressions, not values that the file fixes.

        A value written into `env` would give the program the same input on
        every run, whatever the jobs did.
        """
        env = jq_step(self.job).get("env", {})
        self.assertEqual(NEEDS_EXPRESSION, env.get("NEEDS"))
        self.assertEqual(EVENT_EXPRESSION, env.get("EVENT"))

    def test_nothing_in_the_job_continues_on_error(self) -> None:
        """Neither the job nor a step sets `continue-on-error`.

        The key would turn a failure of the step into a success of the job.
        """
        self.assertNotIn("continue-on-error", self.job)
        for step in self.job["steps"]:
            with self.subTest(step=step.get("name", step.get("run"))):
                self.assertNotIn("continue-on-error", step)

    def test_every_job_succeeding_passes(self) -> None:
        """All results `success` pass, on a push and on a pull request."""
        for event in ("push", "pull_request"):
            with self.subTest(event):
                self.assertEqual(JQ_TRUE, self.exit_status(event, {}))

    def test_a_failed_job_fails(self) -> None:
        """Each needed job that fails fails the aggregate."""
        for name in self.needed:
            for event in ("push", "pull_request"):
                with self.subTest(job=name, event=event):
                    self.assertEqual(
                        JQ_FALSE, self.exit_status(event, {name: "failure"})
                    )

    def test_a_cancelled_job_fails(self) -> None:
        """Each needed job that is cancelled fails the aggregate."""
        for name in self.needed:
            for event in ("push", "pull_request"):
                with self.subTest(job=name, event=event):
                    self.assertEqual(
                        JQ_FALSE, self.exit_status(event, {name: "cancelled"})
                    )

    def test_the_skippable_job_may_be_skipped_on_a_push(self) -> None:
        """`git-policy` skipped on a push is the one accepted skip."""
        self.assertEqual(
            JQ_TRUE, self.exit_status(SKIP_EVENT, {SKIPPABLE_JOB: "skipped"})
        )

    def test_the_skippable_job_must_run_on_a_pull_request(self) -> None:
        """`git-policy` skipped on a pull request fails the aggregate."""
        self.assertEqual(
            JQ_FALSE, self.exit_status("pull_request", {SKIPPABLE_JOB: "skipped"})
        )

    def test_the_skip_is_accepted_for_a_push_only(self) -> None:
        """Another event does not get the skip, `workflow_dispatch` for one."""
        for event in ("pull_request", "workflow_dispatch", "schedule", ""):
            with self.subTest(event):
                self.assertEqual(
                    JQ_FALSE, self.exit_status(event, {SKIPPABLE_JOB: "skipped"})
                )

    def test_any_other_skipped_job_fails(self) -> None:
        """Only `git-policy` may be skipped, on a push or on a pull request."""
        for name in self.needed:
            if name == SKIPPABLE_JOB:
                continue
            for event in ("push", "pull_request"):
                with self.subTest(job=name, event=event):
                    self.assertEqual(
                        JQ_FALSE, self.exit_status(event, {name: "skipped"})
                    )

    def test_a_result_that_is_not_success_fails(self) -> None:
        """A result that GitHub does not define fails, as an empty one does."""
        for name in self.needed:
            for result in ("", "neutral", "Success"):
                with self.subTest(job=name, result=result):
                    self.assertEqual(JQ_FALSE, self.exit_status("push", {name: result}))


if __name__ == "__main__":
    unittest.main()
