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

    def test_output_that_is_not_utf8_is_decoded_with_a_replacement_character(
        self,
    ) -> None:
        """By default a byte that is not UTF-8 becomes U+FFFD, and the call works.

        The default is `errors="replace"`, so the release tool, which passes no
        argument, does not stop on a file name that is not UTF-8.
        """
        run = command_runner([sys.executable, "-c"])
        script = "import sys; sys.stdout.buffer.write(b'a\\xffb\\n')"
        self.assertEqual(run([script]), "a\N{REPLACEMENT CHARACTER}b\n")

    def test_keeps_carriage_returns_in_the_output_and_the_input(self) -> None:
        r"""A `\r` and a `\r\n` come back as written, not as `\n`.

        Text mode of `subprocess` turns both into a line feed. A commit
        message with a carriage return would then read differently from the
        message that Git stores.
        """
        run = command_runner([sys.executable, "-c"])
        script = "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"
        text = "a\rb\r\nc\n"
        self.assertEqual(run([script], stdin=text), text)

    def test_strict_decoding_raises_a_decode_error_for_output_that_is_not_utf8(
        self,
    ) -> None:
        """With `errors="strict"` bytes that are not UTF-8 fail for the caller."""
        run = command_runner([sys.executable, "-c"], errors="strict")
        script = "import sys; sys.stdout.buffer.write(b'\\xff\\xfe')"
        with self.assertRaises(UnicodeDecodeError):
            run([script])

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
