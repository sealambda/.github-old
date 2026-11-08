"""Tests for the command line: exit statuses and output."""

import os
import unittest
from unittest import mock

from decisions import schemas
from support import REPOSITORY, TreeTestCase, record_text


class ExitStatusTest(TreeTestCase):
    """Exit 0 when clean, 1 with findings, 2 for a usage error, 3 for a bug."""

    def test_clean_tree_exits_0_with_no_output(self) -> None:
        """No finding means exit 0 and nothing printed."""
        self.write({"docs/decisions/0001-a.md": record_text("See ADR 0001.\n")})
        result = self.run_cli_on_root()
        self.assertEqual((result.code, result.stdout, result.stderr), (0, "", ""))

    def test_findings_exit_1_and_print_path_line_message(self) -> None:
        """Each finding is a line `path:line: message`; the count is on stderr."""
        self.write({"a.md": "x\nADR 0042\n", "b.md": "spec 0007\n"})
        result = self.run_cli_on_root()
        self.assertEqual(result.code, 1)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "a.md:2: decision record 0042 does not exist",
                "b.md:1: spec 0007 has no file docs/specs/0007-*.md",
            ],
        )
        self.assertEqual(result.stderr, "decisions: 2 finding(s)\n")

    def test_exclude_option_is_repeatable(self) -> None:
        """Each `--exclude` adds a skipped prefix."""
        self.write({"a/x.md": "ADR 0042\n", "b/x.md": "ADR 0042\n", "c.md": "ok\n"})
        result = self.run_cli_on_root("--exclude", "a", "--exclude", "b/")
        self.assertEqual(result.code, 0)

    def test_missing_root_exits_2(self) -> None:
        """A root that is not a directory is a usage error."""
        result = self.run_cli(
            "check", "--repository", REPOSITORY, str(self.root / "missing")
        )
        self.assertEqual(result.code, 2)
        self.assertIn("ROOT is not a directory", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_missing_repository_exits_2(self) -> None:
        """`--repository` is required."""
        result = self.run_cli("check", str(self.root))
        self.assertEqual(result.code, 2)
        self.assertIn("--repository", result.stderr)

    def test_malformed_repository_exits_2(self) -> None:
        """The repository must look like `owner/name`."""
        result = self.run_cli("check", "--repository", "just-a-name", str(self.root))
        self.assertEqual(result.code, 2)
        self.assertIn("OWNER/NAME", result.stderr)

    def test_no_arguments_exits_2(self) -> None:
        """Without arguments the command prints the usage and exits 2."""
        result = self.run_cli()
        self.assertEqual(result.code, 2)
        self.assertIn("usage: decisions", result.stderr)

    def test_unknown_command_exits_2(self) -> None:
        """The first argument must be a command: the old bare form is gone."""
        result = self.run_cli("--repository", REPOSITORY, str(self.root))
        self.assertEqual(result.code, 2)
        self.assertIn("usage: decisions", result.stderr)

    def test_unknown_option_exits_2(self) -> None:
        """An option that the command does not know is a usage error."""
        result = self.run_cli_on_root("--bogus")
        self.assertEqual(result.code, 2)

    def test_bad_exclude_exits_2(self) -> None:
        """An absolute path, `..` or an empty exclude is a usage error."""
        for bad in ("/abs", "../up", "a/../b", ".", ""):
            with self.subTest(exclude=bad):
                result = self.run_cli_on_root("--exclude", bad)
                self.assertEqual(result.code, 2)
                self.assertIn(
                    "an exclude must be a path inside the root", result.stderr
                )

    def test_unreadable_schema_directory_exits_2(self) -> None:
        """A missing schema file is reported as an error, not a traceback."""
        with mock.patch.dict(os.environ, {schemas.SCHEMA_DIR_ENV: str(self.root)}):
            result = self.run_cli_on_root()
        self.assertEqual(result.code, 2)
        self.assertIn("decisions:", result.stderr)

    def test_unexpected_exception_exits_3_with_a_traceback(self) -> None:
        """A bug is not a finding: status 1 is for findings only."""
        with mock.patch(
            "decisions.cli.run_checks", side_effect=RuntimeError("broken check")
        ):
            result = self.run_cli_on_root()
        self.assertEqual(result.code, 3)
        self.assertEqual(result.stdout, "")
        self.assertIn("Traceback (most recent call last)", result.stderr)
        self.assertIn("RuntimeError: broken check", result.stderr)
        self.assertIn("decisions: internal error", result.stderr)

    def test_schema_directory_comes_from_the_environment(self) -> None:
        """`DECISIONS_SCHEMA_DIR` overrides the default directory."""
        with mock.patch.dict(os.environ, {schemas.SCHEMA_DIR_ENV: "/some/where"}):
            self.assertEqual(str(schemas.schema_dir()), "/some/where")


if __name__ == "__main__":
    unittest.main()
