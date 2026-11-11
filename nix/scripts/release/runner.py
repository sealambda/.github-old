"""Run `git` and `gh` as child processes behind one injectable interface.

The rest of the package takes a `Runner` and never starts a process itself, so
a test hands in a runner for a temporary repository and a fake `gh`.
"""

import subprocess
from collections.abc import Sequence
from typing import Protocol


class CommandError(Exception):
    """A command failed, or its program is not installed.

    Attributes:
        stderr: The standard error of the failed command without the trailing
            whitespace, or an empty string when the command did not run or
            printed nothing. A caller can tell one failure of a command from
            another with it.
    """

    def __init__(self, message: str, stderr: str = "") -> None:
        """Create the error with a message and the standard error text."""
        super().__init__(message)
        self.stderr = stderr


class Runner(Protocol):
    """Runs one command and returns its standard output."""

    def __call__(self, args: Sequence[str], *, stdin: str | None = None) -> str:
        """Run the command with `args` and return its standard output.

        Args:
            args: The arguments after the program name.
            stdin: Text for the standard input of the command, or `None` for
                none.

        Raises:
            CommandError: The command failed.
        """
        ...


def command_runner(prefix: Sequence[str]) -> Runner:
    """Build a runner for a program.

    The child process inherits the environment of the caller. This is how `gh`
    reads `GH_TOKEN` and `GH_REPO`.

    Args:
        prefix: The program and the arguments that every call starts with, for
            example `["git", "-C", "/path"]`.

    Returns:
        A runner. It raises `CommandError` when the program is missing or exits
        with a nonzero status. The message holds the command and the standard
        error, and `CommandError.stderr` holds the standard error alone.
    """

    def run(args: Sequence[str], *, stdin: str | None = None) -> str:
        """Run `prefix` and `args` and return the decoded standard output."""
        command = [*prefix, *args]
        try:
            completed = subprocess.run(
                command,
                input=stdin,
                capture_output=True,
                encoding="utf-8",
                check=False,
            )
        except FileNotFoundError as error:
            raise CommandError(
                f"{prefix[0]} is not installed or not on PATH"
            ) from error
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            raise CommandError(f"{' '.join(command)} failed: {stderr}", stderr)
        return completed.stdout

    return run
