"""Tests of the rule that a pull request workflow has a concurrency group."""

from workflows_fixtures import (
    WORKFLOW_PATH,
    TreeTestCase,
    call_job,
    job,
    line_of_text,
    workflow,
)

CONCURRENCY_ADVICE = "set concurrency at the top level or on every job"
"""The end of every finding about a concurrency group."""

TIMED_JOB = job("build", "timeout-minutes: 5")
"""A job that meets the rule for time limits, so that only concurrency is tested."""


def finding(event: str, line: int) -> str:
    """Return the finding line for a workflow that runs on `event`."""
    return (
        f"{WORKFLOW_PATH}:{line}: the workflow runs on {event} and has no "
        f"concurrency group; {CONCURRENCY_ADVICE}"
    )


class ConcurrencyRuleTest(TreeTestCase):
    """A workflow that runs on a pull request needs a concurrency group."""

    def test_pull_request_without_concurrency_is_a_finding_on_the_on_line(self) -> None:
        """The finding names the event and sits on the line of `on`."""
        text = workflow("pull_request", TIMED_JOB)
        self.assertEqual(self.findings_of(text), [finding("pull_request", 2)])

    def test_pull_request_target_without_concurrency_is_a_finding(self) -> None:
        """The event `pull_request_target` is covered like `pull_request`."""
        text = workflow("pull_request_target", TIMED_JOB)
        self.assertEqual(self.findings_of(text), [finding("pull_request_target", 2)])

    def test_concurrency_at_the_top_is_clean(self) -> None:
        """A workflow level `concurrency` covers every job."""
        text = workflow(
            "pull_request", TIMED_JOB, header=("concurrency: group-${{ github.ref }}",)
        )
        self.assertEqual(self.findings_of(text), [])

    def test_concurrency_as_a_mapping_at_the_top_is_clean(self) -> None:
        """The mapping form with `group` and `cancel-in-progress` passes."""
        text = workflow(
            "pull_request",
            TIMED_JOB,
            header=("concurrency:", "  group: g", "  cancel-in-progress: true"),
        )
        self.assertEqual(self.findings_of(text), [])

    def test_concurrency_on_every_job_is_clean(self) -> None:
        """With no group at the top, each job needs its own."""
        text = workflow(
            "pull_request",
            job("a", "timeout-minutes: 5", "concurrency: a"),
            job("b", "timeout-minutes: 5", "concurrency: b"),
        )
        self.assertEqual(self.findings_of(text), [])

    def test_concurrency_on_some_jobs_is_a_finding(self) -> None:
        """One job without a group leaves its runs uncovered."""
        text = workflow(
            "pull_request",
            job("a", "timeout-minutes: 5", "concurrency: a"),
            job("b", "timeout-minutes: 5"),
        )
        self.assertEqual(self.findings_of(text), [finding("pull_request", 2)])

    def test_job_that_calls_a_workflow_may_carry_the_group(self) -> None:
        """GitHub allows `concurrency` on a `uses` job, so it counts."""
        text = workflow("pull_request", call_job("call", "concurrency: c"))
        self.assertEqual(self.findings_of(text), [])

    def test_call_job_without_a_group_is_a_finding(self) -> None:
        """A `uses` job is exempt from the time limit, not from the group."""
        text = workflow("pull_request", call_job("call"))
        self.assertEqual(self.findings_of(text), [finding("pull_request", 2)])

    def test_workflow_without_jobs_and_without_a_group_is_a_finding(self) -> None:
        """No job can carry a group, so the top level has to."""
        text = "name: Test\non: pull_request\njobs: {}\n"
        self.assertEqual(self.findings_of(text), [finding("pull_request", 2)])

    def test_null_concurrency_does_not_count(self) -> None:
        """An empty `concurrency:` key sets no group."""
        text = workflow("pull_request", TIMED_JOB, header=("concurrency:",))
        self.assertEqual(self.findings_of(text), [finding("pull_request", 2)])

    def test_other_events_are_exempt(self) -> None:
        """Only the two pull request events are covered."""
        for event in ("push", "[push, workflow_dispatch]", "schedule", "release"):
            with self.subTest(event=event):
                self.assertEqual(self.findings_of(workflow(event, TIMED_JOB)), [])

    def test_reusable_workflow_is_exempt(self) -> None:
        """A workflow that only `workflow_call` triggers has its caller's group."""
        text = workflow("workflow_call", TIMED_JOB)
        self.assertEqual(self.findings_of(text), [])

    def test_reusable_workflow_as_a_mapping_is_exempt(self) -> None:
        """The mapping form of `workflow_call` is exempt too."""
        text = workflow("\n  workflow_call:\n    inputs: {}", TIMED_JOB)
        self.assertEqual(self.findings_of(text), [])

    def test_workflow_that_is_also_reusable_is_covered_by_its_other_events(
        self,
    ) -> None:
        """`workflow_call` next to `pull_request` doesn't exempt the workflow."""
        text = workflow("[workflow_call, pull_request]", TIMED_JOB)
        self.assertEqual(self.findings_of(text), [finding("pull_request", 2)])


class OnKeyShapeTest(TreeTestCase):
    """The `on` key is a name, a list or a mapping, quoted or not."""

    def test_list_form_is_read(self) -> None:
        """The finding of a list sits on the line of `on`."""
        text = workflow("[push, pull_request]", TIMED_JOB)
        self.assertEqual(self.findings_of(text), [finding("pull_request", 2)])

    def test_block_list_finding_sits_on_the_item(self) -> None:
        """For a block list the finding sits on the item that names the event."""
        text = workflow("\n  - push\n  - pull_request", TIMED_JOB)
        line = line_of_text(text, "- pull_request")
        self.assertEqual(self.findings_of(text), [finding("pull_request", line)])

    def test_mapping_form_is_read_and_the_finding_sits_on_the_event(self) -> None:
        """For a mapping the finding sits on the key of the event."""
        text = workflow("\n  push:\n  pull_request:\n    branches: [main]", TIMED_JOB)
        line = line_of_text(text, "  pull_request:")
        self.assertEqual(self.findings_of(text), [finding("pull_request", line)])

    def test_quoted_on_key_is_read(self) -> None:
        """A quoted key is a string, not the boolean of YAML 1.1."""
        text = f'name: Test\n"on": pull_request\njobs:\n{TIMED_JOB}'
        self.assertEqual(self.findings_of(text), [finding("pull_request", 2)])

    def test_first_pull_request_event_is_the_one_reported(self) -> None:
        """A workflow with both events gets one finding."""
        text = workflow("[pull_request_target, pull_request]", TIMED_JOB)
        self.assertEqual(self.findings_of(text), [finding("pull_request_target", 2)])

    def test_missing_or_odd_on_value_gives_no_finding(self) -> None:
        """A value of another shape is for actionlint."""
        bodies = (
            "name: Test\njobs: {}\n",
            "name: Test\non: 5\njobs: {}\n",
            "name: Test\non:\njobs: {}\n",
        )
        for text in bodies:
            with self.subTest(text=text):
                self.assertEqual(self.findings_of(text), [])
