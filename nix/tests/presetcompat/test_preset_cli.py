"""Tests of the command line of the preset comparison."""

import unittest
from unittest import mock

from presetcompat import cli
from presetcompat_fixtures import CliTestCase, new_preset, old_preset


class CommandLineTest(CliTestCase):
    """Exit statuses and output streams."""

    def test_a_pair_that_keeps_every_invariant_exits_zero(self) -> None:
        """No finding means status 0 and no output."""
        old = self.write_json("v1.json", old_preset())
        new = self.write_json("v2.json", new_preset())
        self.assertEqual(self.run_cli("check", str(old), str(new)), (0, [], ""))

    def test_findings_come_in_one_run_with_the_path_of_the_new_file(self) -> None:
        """Status 1, one line for each finding, and the count on stderr."""
        broken = new_preset()
        broken["minimumReleaseAge"] = "3 days"
        del broken["osvVulnerabilityAlerts"]
        old = self.write_json("v1.json", old_preset())
        new = self.write_json("v2.json", broken)
        status, lines, stderr = self.run_cli("check", str(old), str(new))
        self.assertEqual(status, 1)
        self.assertEqual(
            lines,
            [
                f'{new.as_posix()}:1: minimumReleaseAge must be "7 days", '
                "got '3 days'",
                f"{new.as_posix()}:1: osvVulnerabilityAlerts must be true",
            ],
        )
        self.assertIn("2 finding(s)", stderr)

    def test_a_missing_file_is_an_exit_status_two(self) -> None:
        """A file that cannot be read exits 2."""
        old = self.write_json("v1.json", old_preset())
        status, lines, stderr = self.run_cli("check", str(old), str(self.root / "no"))
        self.assertEqual((status, lines), (2, []))
        self.assertIn("presetcompat:", stderr)

    def test_a_file_that_is_not_json_is_an_exit_status_two(self) -> None:
        """Text that isn't JSON exits 2 and names the file."""
        old = self.write_json("v1.json", old_preset())
        new = self.root / "v2.json"
        new.write_text("{ not json", encoding="utf-8")
        status, _, stderr = self.run_cli("check", str(old), str(new))
        self.assertEqual(status, 2)
        self.assertIn(f"{new} is not JSON", stderr)

    def test_bytes_that_are_not_utf_8_are_an_exit_status_two(self) -> None:
        """A file that holds no text is not a preset."""
        old = self.write_json("v1.json", old_preset())
        new = self.root / "v2.json"
        new.write_bytes(b"\xff\xfe\x00")
        self.assertEqual(self.run_cli("check", str(old), str(new))[0], 2)

    def test_json_that_is_not_an_object_is_an_exit_status_two(self) -> None:
        """A preset is an object, so a list exits 2."""
        old = self.write_json("v1.json", old_preset())
        new = self.write_json("v2.json", [])
        status, _, stderr = self.run_cli("check", str(old), str(new))
        self.assertEqual(status, 2)
        self.assertIn("is not a JSON object", stderr)

    def test_a_missing_argument_is_a_usage_error(self) -> None:
        """One path in place of two exits 2 and names the missing one."""
        old = self.write_json("v1.json", old_preset())
        status, _, stderr = self.run_cli("check", str(old))
        self.assertEqual(status, 2)
        self.assertIn("arguments are required: NEW", stderr)

    def test_no_command_is_a_usage_error(self) -> None:
        """The command `check` is required."""
        status, _, stderr = self.run_cli()
        self.assertEqual(status, 2)
        self.assertIn("presetcompat:", stderr)

    def test_a_bug_is_an_exit_status_three_with_the_trace(self) -> None:
        """An unexpected exception is a status 3, apart from findings."""
        old = self.write_json("v1.json", old_preset())
        new = self.write_json("v2.json", new_preset())
        with mock.patch.object(cli, "compare", side_effect=RuntimeError("boom")):
            status, _, stderr = self.run_cli("check", str(old), str(new))
        self.assertEqual(status, 3)
        self.assertIn("RuntimeError: boom", stderr)
        self.assertIn("internal error", stderr)


if __name__ == "__main__":
    unittest.main()
