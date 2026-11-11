"""Tests of the runner that starts `git` and `gh`."""

import sys
import unittest

from release.runner import CommandError, command_runner


class CommandRunnerTest(unittest.TestCase):
    """`command_runner` returns the output and turns a failure into an error."""

    def test_returns_the_standard_output(self) -> None:
        """The prefix and the arguments make one command."""
        run = command_runner([sys.executable])
        self.assertEqual(run(["-c", "print('out')"]), "out\n")

    def test_passes_the_standard_input(self) -> None:
        """Text given as `stdin` reaches the command."""
        run = command_runner([sys.executable, "-c"])
        script = "import sys; sys.stdout.write(sys.stdin.read())"
        self.assertEqual(run([script], stdin="notes\n"), "notes\n")

    def test_nonzero_status_raises_with_the_command_and_the_error_text(self) -> None:
        """The message names the command and holds its standard error."""
        run = command_runner([sys.executable, "-c"])
        script = "import sys; sys.stderr.write('refused'); sys.exit(3)"
        with self.assertRaises(CommandError) as raised:
            run([script])
        self.assertIn("failed: refused", str(raised.exception))
        self.assertEqual(raised.exception.stderr, "refused")

    def test_missing_program_raises_a_clear_error(self) -> None:
        """A program that is not on PATH gives a message that names it."""
        run = command_runner(["release-test-no-such-program"])
        with self.assertRaises(CommandError) as raised:
            run([])
        self.assertIn(
            "release-test-no-such-program is not installed", str(raised.exception)
        )
