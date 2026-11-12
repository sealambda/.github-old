"""Tests of the rule that every job without `uses` has a time limit."""

from workflows_fixtures import (
    TIMEOUT_ADVICE,
    WORKFLOW_PATH,
    TreeTestCase,
    call_job,
    job,
    line_of_text,
    workflow,
)


class TimeoutRuleTest(TreeTestCase):
    """A job needs `timeout-minutes`, a whole number from 1 to 360."""

    def test_job_with_a_timeout_is_clean(self) -> None:
        """A job that sets a valid limit has no finding."""
        text = workflow("push", job("build", "timeout-minutes: 10"))
        self.assertEqual(self.findings_of(text), [])

    def test_job_without_a_timeout_is_named_with_path_and_line(self) -> None:
        """The finding holds the path, the line of the job and the job id."""
        text = workflow("push", job("build"))
        line = line_of_text(text, "  build:")
        self.assertEqual(
            self.findings_of(text),
            [
                f'{WORKFLOW_PATH}:{line}: job "build" has no timeout-minutes; '
                f"{TIMEOUT_ADVICE}"
            ],
        )

    def test_exit_status_is_one_and_stderr_counts_the_findings(self) -> None:
        """A finding fails the run with status 1."""
        self.write(WORKFLOW_PATH, workflow("push", job("a"), job("b")))
        status, lines, stderr = self.run_cli()
        self.assertEqual((status, len(lines)), (1, 2))
        self.assertIn("2 finding(s)", stderr)

    def test_every_job_is_checked(self) -> None:
        """Only the job that lacks a limit is a finding."""
        text = workflow("push", job("good", "timeout-minutes: 5"), job("bad"))
        findings = self.findings_of(text)
        self.assertEqual(len(findings), 1)
        self.assertIn('job "bad"', findings[0])

    def test_limits_at_the_bounds_are_clean(self) -> None:
        """The smallest and the largest whole number pass."""
        for minutes in ("1", "360"):
            with self.subTest(minutes=minutes):
                text = workflow("push", job("build", f"timeout-minutes: {minutes}"))
                self.assertEqual(self.findings_of(text), [])

    def test_expression_is_clean(self) -> None:
        """An expression has no value in the file, so it passes."""
        text = workflow(
            "push", job("build", "timeout-minutes: ${{ fromJSON(inputs.minutes) }}")
        )
        self.assertEqual(self.findings_of(text), [])

    def test_exactly_one_balanced_expression_is_clean(self) -> None:
        """Whitespace around one `${{ ... }}`, or none inside it, is allowed."""
        values = (
            '"${{ inputs.timeout-minutes }}"',
            '"  ${{ inputs.timeout-minutes }}  "',
            '"${{inputs.timeout-minutes}}"',
            "\"${{ fromJSON('{}') }}\"",
        )
        for written in values:
            with self.subTest(value=written):
                text = workflow("push", job("build", f"timeout-minutes: {written}"))
                self.assertEqual(self.findings_of(text), [])

    def test_text_that_is_not_one_balanced_expression_is_a_finding(self) -> None:
        """An unclosed, empty, doubled or padded expression has no usable value."""
        values = (
            "${{ x",
            "x }}",
            "${{ }}",
            "${{}}",
            "${{ a }} ${{ b }}",
            "${{ a }} }}",
            "${{ a }}}",
            "${{ ${{ a }} }}",
            "${{ a }} 5",
            "5 ${{ a }}",
            "}} a ${{",
        )
        for written in values:
            with self.subTest(value=written):
                text = workflow("push", job("build", f'timeout-minutes: "{written}"'))
                line = line_of_text(text, "timeout-minutes")
                self.assertEqual(
                    self.findings_of(text),
                    [
                        f'{WORKFLOW_PATH}:{line}: job "build" has timeout-minutes '
                        f"{written!r}; {TIMEOUT_ADVICE}"
                    ],
                )

    def test_check_is_stricter_than_github_for_text_and_fractions(self) -> None:
        """A numeric string and a fractional number are findings, as documented."""
        for written, shown in (('"5"', "'5'"), ("5.0", "5.0"), ("5.5", "5.5")):
            with self.subTest(value=written):
                text = workflow("push", job("build", f"timeout-minutes: {written}"))
                line = line_of_text(text, "timeout-minutes")
                self.assertEqual(
                    self.findings_of(text),
                    [
                        f'{WORKFLOW_PATH}:{line}: job "build" has timeout-minutes '
                        f"{shown}; {TIMEOUT_ADVICE}"
                    ],
                )

    def test_invalid_values_are_findings_on_the_timeout_line(self) -> None:
        """Zero, a negative, a too large, a fractional, a text and a null fail."""
        values = {
            "0": "0",
            "-5": "-5",
            "361": "361",
            "10.5": "10.5",
            "'30'": "'30'",
            "true": "True",
            "": "None",
        }
        for written, shown in values.items():
            with self.subTest(value=written):
                text = workflow("push", job("build", f"timeout-minutes: {written}"))
                line = line_of_text(text, "timeout-minutes")
                self.assertEqual(
                    self.findings_of(text),
                    [
                        f'{WORKFLOW_PATH}:{line}: job "build" has timeout-minutes '
                        f"{shown}; {TIMEOUT_ADVICE}"
                    ],
                )

    def test_job_that_calls_a_reusable_workflow_is_exempt(self) -> None:
        """GitHub rejects `timeout-minutes` on a `uses` job, so it needs none."""
        text = workflow("push", call_job("call"))
        self.assertEqual(self.findings_of(text), [])

    def test_call_job_is_exempt_even_with_a_timeout(self) -> None:
        """The rule neither requires nor judges a limit on a `uses` job."""
        text = workflow("push", call_job("call", "timeout-minutes: 0"))
        self.assertEqual(self.findings_of(text), [])

    def test_shapes_that_are_not_jobs_are_skipped(self) -> None:
        """A list of jobs and a job that is not a mapping are actionlint's."""
        for body in ("jobs: []\n", "jobs:\n  a:\n", "jobs:\n  a: text\n", "jobs:\n"):
            with self.subTest(body=body):
                text = "name: Test\non: push\n" + body
                self.assertEqual(self.findings_of(text), [])

    def test_document_that_is_not_a_mapping_is_skipped(self) -> None:
        """A list or an empty file has no jobs."""
        for text in ("- a\n- b\n", "", "text\n"):
            with self.subTest(text=text):
                self.assertEqual(self.findings_of(text), [])


class WorkflowFilesTest(TreeTestCase):
    """The rule reads the files that the `versions` check reads, and no action."""

    def test_yaml_extension_starter_workflow_and_nested_folder_are_read(self) -> None:
        """Every selected workflow file gives its own finding."""
        text = workflow("push", job("build"))
        for path in (
            ".github/workflows/other.yaml",
            "workflow-templates/starter.yml",
            "templates/x/.github/workflows/ci.yml",
        ):
            self.write(path, text)
        _, lines, _ = self.run_cli()
        self.assertEqual(
            [line.split(":")[0] for line in lines],
            [
                ".github/workflows/other.yaml",
                "templates/x/.github/workflows/ci.yml",
                "workflow-templates/starter.yml",
            ],
        )

    def test_other_files_are_not_workflows(self) -> None:
        """Actions, subfolders of `workflows` and other folders are skipped."""
        text = workflow("push", job("build"))
        for path in (
            "action.yml",
            ".github/workflows/sub/ci.yml",
            "docs/ci.yml",
            ".github/workflows/notes.md",
            "workflow-templates/sub/starter.yml",
        ):
            self.write(path, text)
        self.assertEqual(self.run_cli(), (0, [], ""))

    def test_invalid_yaml_is_a_finding(self) -> None:
        """A file that does not parse could hide a job, so it fails."""
        self.write(WORKFLOW_PATH, "jobs: [unclosed\n")
        status, lines, _ = self.run_cli()
        self.assertEqual(status, 1)
        self.assertIn("the file isn't valid YAML", lines[0])

    def test_file_that_is_not_utf8_is_a_finding(self) -> None:
        """Bytes that are not text fail with a finding on line 1."""
        self.write(WORKFLOW_PATH, b"\xff\xfe jobs\n")
        self.assertEqual(
            self.run_cli()[1], [f"{WORKFLOW_PATH}:1: the file isn't UTF-8 text"]
        )
