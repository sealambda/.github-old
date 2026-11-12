"""The parts of the command line that every tool of the hub shares.

The tools `decisions`, `leaks`, `versions` and `workflows` follow one contract
for their exit status and their error output. This module holds that contract
once, so that a change to it reaches every tool.

Exit status: `EXIT_CLEAN` when the tool finds nothing, `EXIT_FINDINGS` when it
finds a problem in the checked tree, `EXIT_USAGE` for a usage error or a file
that cannot be read, `EXIT_INTERNAL` for an exception that the tool does not
expect. Status 1 stays reserved for findings, so that a caller can tell a bug
in the tool from a problem in the tree.
"""

import argparse
import sys
import traceback
from collections.abc import Callable, Sequence
from typing import NoReturn, Protocol

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3


class UsageError(Exception):
    """The command line or the environment is wrong, not the checked tree."""


class RaisingParser(argparse.ArgumentParser):
    """An argument parser that raises `UsageError` instead of exiting."""

    def error(self, message: str) -> NoReturn:
        """Raise `UsageError` with the usage text and the problem."""
        raise UsageError(f"{self.format_usage().strip()}\n{self.prog}: {message}")


class Formattable(Protocol):
    """A finding that prints itself on one line."""

    def format(self) -> str:
        """Return the finding as one line of text."""
        ...


def report_findings(program: str, findings: Sequence[Formattable]) -> int:
    """Print the findings and return the exit status.

    Each finding goes to standard output, one per line. When there are
    findings, the count goes to standard error.

    Args:
        program: The name of the tool, as the count line prints it.
        findings: The findings of the run, in the order to print them.

    Returns:
        `EXIT_FINDINGS` when `findings` is not empty, else `EXIT_CLEAN`.
    """
    for finding in findings:
        print(finding.format())
    if findings:
        print(f"{program}: {len(findings)} finding(s)", file=sys.stderr)
        return EXIT_FINDINGS
    return EXIT_CLEAN


def run_guarded(
    program: str,
    run: Callable[[], int],
    *,
    refused: tuple[type[Exception], ...] = (),
) -> int:
    """Run a tool and turn every failure into an exit status.

    A `UsageError` prints its message as it is and gives `EXIT_USAGE`. An
    `OSError`, or an exception class in `refused`, prints `program: message` and
    gives `EXIT_USAGE` too. Any other exception is a bug in the tool: its
    traceback goes to standard error and the status is `EXIT_INTERNAL`.

    Args:
        program: The name of the tool, as the error lines print it.
        run: The work of the tool. It returns the exit status.
        refused: A tuple of exception classes that the tool raises on purpose
            to refuse a request, such as a rule that forbids a step.

    Returns:
        The status that `run` returns, or the status of the failure.
    """
    refusals: tuple[type[Exception], ...] = (*refused, OSError)
    try:
        return run()
    except UsageError as error:
        print(error, file=sys.stderr)
        return EXIT_USAGE
    except refusals as error:
        print(f"{program}: {error}", file=sys.stderr)
        return EXIT_USAGE
    except Exception:  # the last resort: report any bug with its trace
        traceback.print_exc()
        print(f"{program}: internal error, the traceback is above", file=sys.stderr)
        return EXIT_INTERNAL
