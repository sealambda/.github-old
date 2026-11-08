"""Tests for the text edits of the ledger and for the atomic write."""

import os
import stat
import unittest
from unittest import mock

import yaml

from decisions.ledger_edit import (
    LEDGER_HEADER,
    LedgerEditError,
    NewEntry,
    append_entry,
    format_entry,
    rewrite_successors,
    write_text_atomically,
)
from decisions.yamlio import parse_yaml
from support import TreeTestCase, ledger_entry

COMMIT = "ab" * 20


def entry(title: str = "A title", successor: str | None = "0002") -> NewEntry:
    """Return a new entry for record 0001, with the given title and successor."""
    return NewEntry(
        number="0001",
        title=title,
        commit=COMMIT,
        path="docs/decisions/0001-a.md",
        successor=successor,
        date="2026-03-04",
    )


class FormatEntryTest(unittest.TestCase):
    """The text of one entry."""

    def test_fields_follow_the_reference_order(self) -> None:
        """Number, title, commit, path, successor and date, each on a line."""
        self.assertEqual(
            format_entry(entry()),
            '- number: "0001"\n'
            "  title: A title\n"
            f"  commit: {COMMIT}\n"
            "  path: docs/decisions/0001-a.md\n"
            '  successor: "0002"\n'
            "  date: 2026-03-04\n",
        )

    def test_withdrawn_entry_has_no_successor_line(self) -> None:
        """No successor means no key."""
        self.assertNotIn("successor", format_entry(entry(successor=None)))

    def test_awkward_titles_round_trip_through_yaml(self) -> None:
        """A colon, a hash, quotes and non-ASCII letters survive as the title."""
        titles = [
            "Use `uv`: pin it",
            "Choose # as a marker",
            'Say "yes" to it',
            "It's a decision",
            "- starts with a dash",
            "Elección de la ñ",
            "A very long title " + "word " * 40,
        ]
        for title in titles:
            with self.subTest(title=title):
                data = parse_yaml(format_entry(entry(title))).data
                assert isinstance(data, list)
                self.assertEqual(data[0]["title"], title)
                self.assertEqual(data[0]["number"], "0001")
                self.assertEqual(data[0]["date"], "2026-03-04")


class AppendEntryTest(unittest.TestCase):
    """The entry goes after the last line and nothing else changes."""

    def test_new_ledger_starts_with_the_header(self) -> None:
        """A missing file becomes the header and the entry."""
        self.assertEqual(
            append_entry(None, entry()), LEDGER_HEADER + format_entry(entry())
        )

    def test_existing_text_is_kept_byte_for_byte(self) -> None:
        """The old text stays as the prefix."""
        old = "# Mine.\n\n" + ledger_entry("0003", "0002")
        self.assertEqual(append_entry(old, entry()), old + format_entry(entry()))

    def test_missing_final_newline_is_added(self) -> None:
        """The new entry starts on its own line."""
        old = ledger_entry("0003", "0002").rstrip("\n")
        new = append_entry(old, entry())
        self.assertTrue(new.startswith(old + "\n- number"), new)

    def test_empty_list_line_is_replaced(self) -> None:
        """A ledger written as `[]` can take an entry."""
        new = append_entry("# Mine.\n[]\n", entry())
        self.assertEqual(new, "# Mine.\n" + format_entry(entry()))
        data = parse_yaml(new).data
        assert isinstance(data, list)
        self.assertEqual(len(data), 1)


class RewriteSuccessorsTest(unittest.TestCase):
    """Only the number on a `successor` line changes."""

    def test_changes_quotes_comments_and_order_stay(self) -> None:
        """Double quotes, single quotes and a comment survive."""
        text = (
            '- successor: "0001"\n'
            '  number: "0003"\n'
            '- number: "0004"\n'
            "  successor: '0001'  # kept\n"
            '- number: "0006"\n'
            '  successor: "0009"\n'
        )
        new, changed = rewrite_successors(text, "0001", "0002")
        self.assertEqual(changed, ["0003", "0004"])
        self.assertEqual(new, text.replace("0001", "0002"))

    def test_no_match_returns_the_same_text(self) -> None:
        """A ledger without a chained entry is not touched."""
        text = ledger_entry("0003", "0009")
        self.assertEqual(rewrite_successors(text, "0001", "0002"), (text, []))

    def test_crlf_line_endings_stay(self) -> None:
        """The line ending of the changed line is the one it had."""
        text = ledger_entry("0003", "0001").replace("\n", "\r\n")
        new, _ = rewrite_successors(text, "0001", "0002")
        self.assertEqual(new, text.replace('"0001"', '"0002"'))

    def test_flow_style_is_refused(self) -> None:
        """A successor inside a flow mapping has no line of its own."""
        text = '- {number: "0003", successor: "0001"}\n'
        with self.assertRaisesRegex(LedgerEditError, "cannot rewrite"):
            rewrite_successors(text, "0001", "0002")

    def test_invalid_yaml_raises_the_yaml_error(self) -> None:
        """The caller turns a syntax error into a refusal."""
        with self.assertRaises(yaml.YAMLError):
            rewrite_successors("- [unclosed\n", "0001", "0002")


class WriteTextAtomicallyTest(TreeTestCase):
    """The write goes through a temporary file and a rename."""

    def test_new_file_gets_mode_0644(self) -> None:
        """A new file is readable by the team, whatever the umask."""
        path = self.root / "ledger.yaml"
        write_text_atomically(path, "text\n")
        self.assertEqual(path.read_text(encoding="utf-8"), "text\n")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)

    def test_existing_mode_is_kept(self) -> None:
        """An executable bit or a restrictive mode is not reset."""
        path = self.root / "ledger.yaml"
        path.write_text("old\n", encoding="utf-8")
        path.chmod(0o600)
        write_text_atomically(path, "new\n")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_failed_rename_leaves_the_old_file_and_no_temporary(self) -> None:
        """A reader never sees half a ledger, and nothing is left behind."""
        path = self.root / "ledger.yaml"
        path.write_text("old\n", encoding="utf-8")
        with (
            mock.patch.object(os, "replace", side_effect=OSError("disk")),
            self.assertRaises(OSError),
        ):
            write_text_atomically(path, "new\n")
        self.assertEqual(path.read_text(encoding="utf-8"), "old\n")
        self.assertEqual([item.name for item in self.root.iterdir()], ["ledger.yaml"])


if __name__ == "__main__":
    unittest.main()
