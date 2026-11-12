"""Tests of the tree scan and the command line of the leak check.

The identifiers are false on purpose, as in `test_leak_rules.py`.
"""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from decisions.walk import SNIFF_BYTES
from leaks.cli import EXIT_CLEAN, EXIT_FINDINGS, EXIT_USAGE, main

ACCOUNT_LINE = "account 123456789012\n"
"""A line with one leak of the rule `aws-account`."""


class ScanTestCase(unittest.TestCase):
    """A test case with an empty directory in `self.root`.

    Attributes:
        root: The directory that the test fills and scans.
    """

    root: Path

    def setUp(self) -> None:
        """Create the directory and remove it after the test."""
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)

    def write(self, path: str, content: str | bytes) -> None:
        """Write one file below the root, with its parent folders."""
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")

    def run_cli(self, *options: str) -> tuple[int, list[str], str]:
        """Run the tool on the root for the organization `acme`.

        Args:
            *options: The options after `--organization acme`.

        Returns:
            The exit status, the lines of standard output and standard error.
        """
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = main(["--organization", "acme", *options, str(self.root)])
        return status, stdout.getvalue().splitlines(), stderr.getvalue()


class ScanTest(ScanTestCase):
    """What the scan reads and how it reports."""

    def test_clean_tree_exits_zero(self) -> None:
        """A tree with public names only has no finding."""
        self.write("README.md", "Use acme/hub on ubuntu-latest.\n")
        status, lines, _ = self.run_cli("--public-repository", "hub")
        self.assertEqual((status, lines), (EXIT_CLEAN, []))

    def test_findings_name_path_line_and_rule_in_stable_order(self) -> None:
        """Each leak prints as `path:line: rule: text`, sorted by path and line."""
        self.write("b.md", "first\n" + ACCOUNT_LINE)
        self.write("a/c.yml", "runs-on: builder\n\nsee acme/billing\n")
        status, lines, stderr = self.run_cli()
        self.assertEqual(status, EXIT_FINDINGS)
        self.assertEqual(
            [line.split(". ")[0] for line in lines],
            [
                "a/c.yml:1: runner-label: `builder`",
                "a/c.yml:3: repository: `acme/billing`",
                "b.md:2: aws-account: `123456789012`",
            ],
        )
        self.assertIn("3 finding(s)", stderr)

    def test_lock_files_and_hidden_files_are_scanned(self) -> None:
        """A lock file and a dotfile are read: a leak there is as public."""
        self.write("flake.lock", ACCOUNT_LINE)
        self.write(".github/workflows/ci.yml", ACCOUNT_LINE)
        status, lines, _ = self.run_cli()
        self.assertEqual(status, EXIT_FINDINGS)
        self.assertEqual(len(lines), 2)

    def test_excluded_path_is_not_scanned(self) -> None:
        """An exclude skips a folder and a file, by whole path components."""
        self.write("tests/fixtures/a.md", ACCOUNT_LINE)
        self.write("rules.py", ACCOUNT_LINE)
        self.write("tests/fixtures2/a.md", ACCOUNT_LINE)
        status, lines, _ = self.run_cli(
            "--exclude", "tests/fixtures", "--exclude", "rules.py"
        )
        self.assertEqual(status, EXIT_FINDINGS)
        self.assertEqual(
            [line.split(":")[0] for line in lines], ["tests/fixtures2/a.md"]
        )

    def test_binary_file_is_skipped_and_bad_utf8_is_read(self) -> None:
        """A file with a NUL byte is binary; a bad byte does not hide a leak."""
        self.write("image.png", b"\x89PNG\0" + ACCOUNT_LINE.encode())
        self.write("latin1.txt", b"calf\xe9 " + ACCOUNT_LINE.encode())
        status, lines, _ = self.run_cli()
        self.assertEqual(status, EXIT_FINDINGS)
        self.assertEqual([line.split(":")[0] for line in lines], ["latin1.txt"])

    def test_utf16_file_with_a_byte_order_mark_is_read(self) -> None:
        """A UTF-16 file holds a NUL byte per character, and it is still text."""
        self.write("utf16le.md", b"\xff\xfe" + ACCOUNT_LINE.encode("utf-16-le"))
        self.write("utf16be.md", b"\xfe\xff" + ACCOUNT_LINE.encode("utf-16-be"))
        self.write("no-mark.bin", ACCOUNT_LINE.encode("utf-16-le"))
        status, lines, _ = self.run_cli()
        self.assertEqual(status, EXIT_FINDINGS)
        self.assertEqual(
            sorted(line.split(":")[0] for line in lines), ["utf16be.md", "utf16le.md"]
        )

    def test_nul_byte_after_the_first_block_does_not_hide_a_file(self) -> None:
        """Only a NUL byte in the first 8 KiB makes a file binary."""
        self.write("late.txt", b"x" * SNIFF_BYTES + b"\0\n" + ACCOUNT_LINE.encode())
        self.write("early.txt", b"x\0\n" + ACCOUNT_LINE.encode())
        status, lines, _ = self.run_cli()
        self.assertEqual(status, EXIT_FINDINGS)
        self.assertEqual([line.split(":")[0] for line in lines], ["late.txt"])

    def test_symbolic_link_is_not_followed(self) -> None:
        """A link is not read, so a file outside the tree is never scanned."""
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        outside = Path(elsewhere.name) / "outside.txt"
        outside.write_text(ACCOUNT_LINE, encoding="utf-8")
        (self.root / "link.txt").symlink_to(outside)
        status, lines, _ = self.run_cli()
        self.assertEqual((status, lines), (EXIT_CLEAN, []))

    def test_public_team_option_allows_a_team(self) -> None:
        """A team mention is a leak until the team is on the public list."""
        self.write("CODEOWNERS", "* @acme/maintainers\n")
        self.assertEqual(self.run_cli()[0], EXIT_FINDINGS)
        self.assertEqual(self.run_cli("--public-team", "Maintainers")[0], EXIT_CLEAN)


class UsageTest(ScanTestCase):
    """The usage errors of the command line."""

    def test_missing_organization_is_a_usage_error(self) -> None:
        """The organization has no default."""
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            status = main([str(self.root)])
        self.assertEqual(status, EXIT_USAGE)
        self.assertIn("--organization", stderr.getvalue())

    def test_malformed_values_are_usage_errors(self) -> None:
        """A bad name, an exclude outside the root and a missing root."""
        for options in (
            ["--public-repository", "a/b"],
            ["--public-team", "a b"],
            ["--public-team", "maintainers\n"],
            ["--public-repository", "hub\n"],
            ["--exclude", "../x"],
        ):
            with self.subTest(options=options):
                self.assertEqual(self.run_cli(*options)[0], EXIT_USAGE)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            status = main(["--organization", "acme", str(self.root / "missing")])
        self.assertEqual(status, EXIT_USAGE)
        self.assertIn("not a directory", stderr.getvalue())
        for organization in ("a/b", "acme\n"):
            with self.subTest(organization=organization):
                with contextlib.redirect_stderr(io.StringIO()):
                    status = main(["--organization", organization, str(self.root)])
                self.assertEqual(status, EXIT_USAGE)


if __name__ == "__main__":
    unittest.main()
