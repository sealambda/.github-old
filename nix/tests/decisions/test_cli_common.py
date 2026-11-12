"""Tests of the exit status contract that every command line of the hub shares."""

import contextlib
import io
import unittest
from collections.abc import Callable
from dataclasses import dataclass

from decisions.cli_common import (
    EXIT_CLEAN,
    EXIT_FINDINGS,
    EXIT_INTERNAL,
    EXIT_USAGE,
    RaisingParser,
    UsageError,
    report_findings,
    run_guarded,
)


@dataclass(frozen=True)
class _Line:
    """A finding that prints as its text."""

    text: str

    def format(self) -> str:
        """Return the text."""
        return self.text


class _Refusal(Exception):
    """An exception that a tool raises on purpose to refuse a request."""


def _raising(error: Exception) -> Callable[[], int]:
    """Return a tool run that raises `error`."""

    def run() -> int:
        raise error

    return run


class ReportFindingsTest(unittest.TestCase):
    """The findings go to standard output and the count to standard error."""

    def report(self, findings: list[_Line]) -> tuple[int, str, str]:
        """Return the status, standard output and standard error of a report."""
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = report_findings("tool", findings)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_no_finding_is_clean_and_silent(self) -> None:
        """An empty list prints nothing and exits 0."""
        self.assertEqual(self.report([]), (EXIT_CLEAN, "", ""))

    def test_findings_print_in_order_with_a_count(self) -> None:
        """Each finding is one line of standard output, then the count."""
        status, stdout, stderr = self.report([_Line("a:1: x"), _Line("b:2: y")])
        self.assertEqual(status, EXIT_FINDINGS)
        self.assertEqual(stdout, "a:1: x\nb:2: y\n")
        self.assertEqual(stderr, "tool: 2 finding(s)\n")


class RunGuardedTest(unittest.TestCase):
    """Every failure of a tool becomes an exit status and a message."""

    def guard(
        self, run: Callable[[], int], *, refused: tuple[type[Exception], ...] = ()
    ) -> tuple[int, str]:
        """Return the status and standard error of a guarded run."""
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            status = run_guarded("tool", run, refused=refused)
        return status, stderr.getvalue()

    def test_the_status_of_the_run_passes_through(self) -> None:
        """A run that returns a status gives that status."""
        self.assertEqual(self.guard(lambda: EXIT_FINDINGS), (EXIT_FINDINGS, ""))

    def test_a_usage_error_prints_as_it_is(self) -> None:
        """A `UsageError` gives status 2 and its message, with no prefix."""
        status, stderr = self.guard(_raising(UsageError("bad flag")))
        self.assertEqual((status, stderr), (EXIT_USAGE, "bad flag\n"))

    def test_an_unreadable_file_is_a_usage_status(self) -> None:
        """An `OSError` gives status 2 and a prefixed message."""
        status, stderr = self.guard(_raising(PermissionError("denied")))
        self.assertEqual((status, stderr), (EXIT_USAGE, "tool: denied\n"))

    def test_a_refusal_is_a_usage_status(self) -> None:
        """An exception class in `refused` gives status 2, not a trace."""
        status, stderr = self.guard(
            _raising(_Refusal("not allowed")), refused=(_Refusal,)
        )
        self.assertEqual((status, stderr), (EXIT_USAGE, "tool: not allowed\n"))

    def test_the_same_exception_is_a_bug_when_it_is_not_refused(self) -> None:
        """`refused` lists the exceptions that are on purpose, and no others."""
        status, stderr = self.guard(_raising(_Refusal("not allowed")))
        self.assertEqual(status, EXIT_INTERNAL)
        self.assertIn("_Refusal: not allowed", stderr)

    def test_a_bug_is_an_internal_status_with_the_trace(self) -> None:
        """An unexpected exception gives status 3 and a traceback."""
        status, stderr = self.guard(_raising(RuntimeError("boom")))
        self.assertEqual(status, EXIT_INTERNAL)
        self.assertIn("RuntimeError: boom", stderr)
        self.assertIn("tool: internal error, the traceback is above", stderr)


class RaisingParserTest(unittest.TestCase):
    """The parser reports a bad command line as a `UsageError`."""

    def test_a_missing_argument_raises_with_the_usage_text(self) -> None:
        """The message holds a usage line, then the problem on its own line.

        Some environments make `argparse` color the usage line, so the test
        compares the problem line only.
        """
        parser = RaisingParser(prog="tool")
        parser.add_argument("root")
        with self.assertRaises(UsageError) as caught:
            parser.parse_args([])
        usage, problem = str(caught.exception).split("\n")
        self.assertIn("tool", usage)
        self.assertEqual(problem, "tool: the following arguments are required: root")


if __name__ == "__main__":
    unittest.main()
