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


def command_runner(prefix: Sequence[str], *, errors: str = "replace") -> Runner:
    r"""Build a runner for a program.

    The child process inherits the environment of the caller. This is how `gh`
    reads `GH_TOKEN` and `GH_REPO`.

    Args:
        prefix: The program and the arguments that every call starts with, for
            example `["git", "-C", "/path"]`.
        errors: How the runner decodes a standard output that is not valid
            UTF-8, as the `errors` argument of `bytes.decode`. The default
            `"replace"` turns each invalid byte into U+FFFD, so a file name
            that git prints as raw bytes does not stop the release tool: such
            a path matches no pattern of `release.paths`, and its answer is
            `rules changed: yes`. `"strict"` raises `UnicodeDecodeError`, for a
            caller that reports the bad bytes itself. The setting does not
            apply to the standard error, which is always decoded with
            replacement characters.

    Returns:
        A runner. It raises `CommandError` when the program is missing or exits
        with a nonzero status. The message holds the command and the standard
        error, and `CommandError.stderr` holds the standard error alone. The
        runner returns the standard output as the program wrote it: a carriage
        return stays a carriage return. Text mode of `subprocess` would turn
        each `\r\n` and each lone `\r` into `\n`, which changes the message of a
        commit that holds a carriage return. The runner decodes the bytes
        itself, so this holds for every caller.
    """

    def run(args: Sequence[str], *, stdin: str | None = None) -> str:
        """Run `prefix` and `args` and return the decoded standard output."""
        command = [*prefix, *args]
        try:
            completed = subprocess.run(
                command,
                input=None if stdin is None else stdin.encode("utf-8"),
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as error:
            raise CommandError(
                f"{prefix[0]} is not installed or not on PATH"
            ) from error
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()
            raise CommandError(f"{' '.join(command)} failed: {stderr}", stderr)
        return completed.stdout.decode("utf-8", errors=errors)

    return run
