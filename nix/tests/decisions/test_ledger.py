"""Tests for the ledger of deleted records and the two schema files."""

import json
import unittest

from jsonschema import Draft202012Validator

from decisions.schemas import (
    LEDGER_SCHEMA,
    RECORD_SCHEMA,
    load_schema,
    schema_dir,
)
from support import LEDGER, TreeTestCase, ledger_entry, record_text


class LedgerRulesTest(TreeTestCase):
    """The rules that link the ledger to the record folder."""

    def test_valid_ledger_has_no_findings(self) -> None:
        """An entry with a successor and a withdrawn entry are valid."""
        self.write(
            {
                "docs/decisions/0003-current.md": record_text(),
                LEDGER: ledger_entry("0001", "0003") + ledger_entry("0002"),
            }
        )
        self.assertEqual(self.findings(), [])

    def test_unquoted_date_and_hash_entry_is_valid(self) -> None:
        """An entry with an unquoted date and an unquoted hash is valid."""
        self.write(
            {
                "docs/decisions/0002-current.md": record_text(),
                LEDGER: (
                    '- number: "0001"\n'
                    '  title: "A deleted record"\n'
                    "  commit: 0123456789abcdef0123456789abcdef01234567\n"
                    "  path: docs/decisions/0001-deleted.md\n"
                    '  successor: "0002"\n'
                    "  date: 2026-01-15\n"
                ),
            }
        )
        self.assertEqual(self.findings(), [])

    def test_path_of_another_number_is_reported_on_the_path_line(self) -> None:
        """A permalink must show the record of its entry, not another one."""
        text = ledger_entry("0001", "0002").replace("0001-deleted", "0009-deleted")
        self.write({"docs/decisions/0002-current.md": record_text(), LEDGER: text})
        self.assertEqual(
            self.findings(),
            [
                f"{LEDGER}:4: the file name of the path docs/decisions/0009-deleted.md "
                "must start with 0001- and end in .md"
            ],
        )

    def test_path_must_name_a_markdown_file(self) -> None:
        """A path to a folder or to another kind of file is a finding."""
        for name in ("0001-deleted", "0001-deleted.txt", "0001deleted.md"):
            with self.subTest(name=name):
                text = ledger_entry("0001", "0002").replace("0001-deleted.md", name)
                self.write(
                    {"docs/decisions/0002-current.md": record_text(), LEDGER: text}
                )
                (finding,) = self.findings()
                self.assertTrue(finding.startswith(f"{LEDGER}:4: "), finding)

    def test_path_folder_may_be_any_folder(self) -> None:
        """A record may have lived in `docs/adr/` or in a nested folder."""
        text = ledger_entry("0001", "0002").replace("docs/decisions", "a/b/adr")
        self.write({"docs/decisions/0002-current.md": record_text(), LEDGER: text})
        self.assertEqual(self.findings(), [])

    def test_number_with_a_record_file_is_reported(self) -> None:
        """A deleted record must not have a file."""
        self.write(
            {
                "docs/decisions/0001-still-here.md": record_text(),
                "docs/decisions/0002-current.md": record_text(),
                LEDGER: ledger_entry("0001", "0002"),
            }
        )
        self.assertEqual(
            self.findings(),
            [
                f"{LEDGER}:1: number 0001 is in the ledger and has a record file: "
                "a deleted record has no file"
            ],
        )

    def test_missing_successor_is_reported(self) -> None:
        """A successor must be a record that exists."""
        self.write({LEDGER: ledger_entry("0001", "0009")})
        self.assertEqual(
            self.findings(),
            [f"{LEDGER}:1: the successor 0009 of 0001 is not a record in force"],
        )

    def test_duplicate_number_is_reported_on_the_second_entry(self) -> None:
        """A number is listed once; the finding sits on the second entry."""
        self.write(
            {
                "docs/decisions/0002-current.md": record_text(),
                LEDGER: ledger_entry("0001", "0002")
                + ledger_entry("0001", "0002", " again"),
            }
        )
        self.assertEqual(self.findings(), [f"{LEDGER}:7: number 0001 is listed twice"])

    def test_citations_in_the_ledger_are_not_checked(self) -> None:
        """The ledger is skipped by the citation scan."""
        self.write(
            {
                "docs/decisions/0002-current.md": record_text(),
                LEDGER: "# ADR 0099 and spec 0098 and docs/gone.md\n"
                + ledger_entry("0001", "0002"),
            }
        )
        self.assertEqual(self.findings(), [])


class LedgerSchemaTest(TreeTestCase):
    """The ledger validates against its schema, with lines."""

    def test_bad_fields_are_reported_on_their_lines(self) -> None:
        """A short commit and a wrong date are findings on their own lines."""
        self.write(
            {
                LEDGER: (
                    '- number: "0001"\n'
                    "  title: Old\n"
                    "  commit: abc123\n"
                    "  path: docs/decisions/0001-old.md\n"
                    "  date: 2026-02-30\n"
                )
            }
        )
        findings = self.findings()
        self.assertEqual(len(findings), 2)
        self.assertTrue(findings[0].startswith(f"{LEDGER}:3: [0].commit: "))
        self.assertTrue(findings[1].startswith(f"{LEDGER}:5: [0].date: "))

    def test_unquoted_number_is_reported(self) -> None:
        """YAML reads an unquoted `0001` as an integer, which is not valid."""
        self.write({LEDGER: ledger_entry("0001").replace('"0001"', "0001", 1)})
        (finding,) = self.findings()
        self.assertTrue(finding.startswith(f"{LEDGER}:1: [0].number: "), finding)

    def test_missing_field_and_unknown_field_are_reported(self) -> None:
        """A required key and an unknown key both fail."""
        text = ledger_entry("0001").replace("  title: Deleted record 0001\n", "")
        self.write({LEDGER: text + "  reason: why\n"})
        messages = sorted(self.findings())
        self.assertEqual(len(messages), 2)
        self.assertIn("'title' is a required property", messages[0])
        self.assertIn("Additional properties", messages[1])

    def test_ledger_must_be_a_list(self) -> None:
        """A mapping at the top level fails the schema."""
        self.write({LEDGER: "number: '0001'\n"})
        (finding,) = self.findings()
        self.assertIn("is not of type 'array'", finding)

    def test_invalid_yaml_is_reported(self) -> None:
        """A YAML syntax error in the ledger is a finding."""
        self.write({LEDGER: "- number: [\n"})
        (finding,) = self.findings()
        self.assertIn("the ledger is not valid YAML", finding)


class SchemaFilesTest(unittest.TestCase):
    """The schema files are valid schemas."""

    def test_schemas_are_valid_draft_2020_12(self) -> None:
        """Both files are JSON and pass the meta-schema."""
        for name in (RECORD_SCHEMA, LEDGER_SCHEMA):
            with self.subTest(schema=name):
                Draft202012Validator.check_schema(load_schema(name))

    def test_withdrawn_entries_need_no_successor(self) -> None:
        """`successor` is the one field that the ledger schema does not require."""
        schema = json.loads((schema_dir() / LEDGER_SCHEMA).read_text("utf-8"))
        required = schema["$defs"]["entry"]["required"]
        self.assertEqual(
            sorted(required), ["commit", "date", "number", "path", "title"]
        )

    def path_is_valid(self, path: str) -> bool:
        """Tell whether the ledger schema accepts `path` in an otherwise valid entry."""
        entry = {
            "number": "0001",
            "title": "Deleted record",
            "commit": "a" * 40,
            "path": path,
            "date": "2026-11-08",
        }
        validator = Draft202012Validator(load_schema(LEDGER_SCHEMA))
        return validator.is_valid([entry])

    def test_path_may_be_a_relative_posix_path_to_a_record_file(self) -> None:
        """The folder is free; the file name is `NNNN-slug.md`."""
        for path in (
            "docs/decisions/0001-old.md",
            "docs/adr/0001-old-name_v2.md",
            "0001-old.md",
            "a/b/c/0001-x.md",
            "docs/.hidden/0001-x.md",
            "docs/..data/0001-x.md",
        ):
            with self.subTest(path=path):
                self.assertTrue(self.path_is_valid(path))

    def test_path_rejects_what_is_not_a_relative_posix_record_path(self) -> None:
        """A rooted path, a `..` segment and a wrong file name break the schema."""
        for path in (
            "",
            "/docs/decisions/0001-old.md",
            "../docs/decisions/0001-old.md",
            "docs/../0001-old.md",
            "docs/decisions/..",
            "docs/decisions/",
            "docs/decisions",
            "docs/decisions/0001-old.txt",
            "docs/decisions/0001old.md",
            "docs/decisions/001-old.md",
            "docs/decisions/00001-old.md",
            "docs/decisions/0001-.md",
            "docs/decisions/0001-old.md/",
            "docs/decisions/0001-old.md\n",
            "docs/decisions/0001-old.md/0002-x.txt",
            "docs//0001-old.md/x",
        ):
            with self.subTest(path=path):
                self.assertFalse(self.path_is_valid(path))


if __name__ == "__main__":
    unittest.main()
