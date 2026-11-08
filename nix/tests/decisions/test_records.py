"""Tests for the record folder: layout, numbers and front matter."""

import unittest

from decisions.records import record_title
from support import FRONT_MATTER, TreeTestCase, record_text


class FolderLayoutTest(TreeTestCase):
    """The folder holds only records, a README and the ledger."""

    def test_valid_folder_has_no_findings(self) -> None:
        """Records, README.md and the ledger are allowed."""
        self.write(
            {
                "docs/decisions/0001-first.md": record_text(),
                "docs/decisions/0002-second-one.md": record_text(),
                "docs/decisions/README.md": "# Decisions\n",
                "docs/decisions/superseded.yaml": "[]\n",
            }
        )
        self.assertEqual(self.findings(), [])

    def test_missing_folder_has_no_findings(self) -> None:
        """A repository without records has nothing to check."""
        self.write({"README.md": "# Project\n"})
        self.assertEqual(self.findings(), [])

    def test_stray_file_is_reported(self) -> None:
        """A file that is not a record, README or ledger is a finding."""
        self.write({"docs/decisions/notes.txt": "x\n"})
        self.assertEqual(
            self.findings(),
            [
                "docs/decisions/notes.txt:1: the file notes.txt does not belong in "
                "docs/decisions/: it holds only NNNN-slug.md records, README.md "
                "and superseded.yaml"
            ],
        )

    def test_subfolder_is_reported(self) -> None:
        """A subfolder is a finding, even when it holds records."""
        self.write({"docs/decisions/archive/0001-old.md": record_text()})
        self.assertEqual(
            self.findings(),
            [
                "docs/decisions/archive:1: the folder archive does not belong in "
                "docs/decisions/: it holds only NNNN-slug.md records, README.md "
                "and superseded.yaml"
            ],
        )

    def test_ignored_file_in_a_work_tree_is_not_a_stray_file(self) -> None:
        """A `.DS_Store` that `.gitignore` hides does not fail a local check."""
        self.git_init()
        self.write(
            {
                ".gitignore": ".DS_Store\n",
                "docs/decisions/.DS_Store": "x",
                "docs/decisions/0001-first.md": record_text(),
            }
        )
        self.assertEqual(self.findings(), [])

    def test_unignored_stray_file_in_a_work_tree_is_reported(self) -> None:
        """A file that Git lists and the folder does not allow is still a finding."""
        self.git_init()
        self.write({"docs/decisions/.DS_Store": "x"})
        (finding,) = self.findings()
        self.assertTrue(
            finding.startswith("docs/decisions/.DS_Store:1: the file .DS_Store"),
            finding,
        )

    def test_badly_named_records_are_reported(self) -> None:
        """A number of the wrong length, an upper-case slug and no slug fail."""
        names = ["123-short.md", "0001-Upper.md", "0002.md", "0003-under_score.md"]
        self.write({f"docs/decisions/{name}": record_text() for name in names})
        self.assertEqual(len(self.findings()), 4)

    def test_duplicate_number_is_reported_on_the_later_file(self) -> None:
        """The second file with a number gets the finding, naming the first."""
        self.write(
            {
                "docs/decisions/0007-alpha.md": record_text(),
                "docs/decisions/0007-beta.md": record_text(),
            }
        )
        self.assertEqual(
            self.findings(),
            [
                "docs/decisions/0007-beta.md:1: number 0007 is also the number of "
                "0007-alpha.md"
            ],
        )


class FrontMatterTest(TreeTestCase):
    """The front matter of each record validates against the schema."""

    def record(self, front_matter: str) -> None:
        """Write the record 0001 with the given front matter lines."""
        self.write(
            {"docs/decisions/0001-test.md": f"---\n{front_matter}---\n\n# Title\n"}
        )

    def test_list_of_makers_and_extra_keys_are_valid(self) -> None:
        """A list of makers, `consulted`, `informed` and `domain` are valid."""
        self.record(
            "status: proposed\ndate: 2026-11-08\n"
            "decision-makers: [Ana, Ben]\nconsulted: []\ninformed: Cy\n"
            "domain: docs\n"
        )
        self.assertEqual(self.findings(), [])

    def test_missing_front_matter_is_reported(self) -> None:
        """A record without the opening fence has no front matter."""
        self.write({"docs/decisions/0001-test.md": "# Title\n"})
        self.assertEqual(
            self.findings(),
            [
                "docs/decisions/0001-test.md:1: the file does not start with "
                "a YAML front matter block"
            ],
        )

    def test_superseded_status_is_reported_on_its_line(self) -> None:
        """`superseded` is not a status; the finding names the status line."""
        self.record("status: superseded\ndate: 2026-01-01\ndecision-makers: Ana\n")
        self.assertEqual(
            self.findings(),
            [
                "docs/decisions/0001-test.md:2: status: 'superseded' is not one "
                "of ['proposed', 'accepted', 'rejected']"
            ],
        )

    def test_missing_decision_makers_is_reported(self) -> None:
        """A required key that is absent is a finding on the first key line."""
        self.record("status: accepted\ndate: 2026-01-01\n")
        self.assertEqual(
            self.findings(),
            ["docs/decisions/0001-test.md:2: 'decision-makers' is a required property"],
        )

    def test_date_must_be_a_real_iso_date(self) -> None:
        """A date in another format, or that does not exist, fails."""
        self.record("status: accepted\ndate: 08/11/2026\ndecision-makers: Ana\n")
        self.assertEqual(len(self.findings()), 2)  # pattern and format
        self.record("status: accepted\ndate: 2026-13-45\ndecision-makers: Ana\n")
        self.assertEqual(len(self.findings()), 1)  # right shape, not a date

    def test_empty_list_of_makers_is_reported(self) -> None:
        """`decision-makers` needs at least one name."""
        self.record("status: accepted\ndate: 2026-01-01\ndecision-makers: []\n")
        self.assertEqual(len(self.findings()), 1)
        self.assertIn("decision-makers", self.findings()[0])

    def test_invalid_yaml_is_reported_with_its_line(self) -> None:
        """A YAML syntax error is a finding on the line of the error."""
        self.record("status: accepted\ndate: [2026\ndecision-makers: Ana\n")
        (finding,) = self.findings()
        self.assertTrue(finding.startswith("docs/decisions/0001-test.md:"), finding)
        self.assertIn("the front matter is not valid YAML", finding)

    def write_bytes(self, data: bytes) -> None:
        """Write the record 0001 with exactly these bytes."""
        path = self.root / "docs/decisions/0001-test.md"
        path.parent.mkdir(parents=True)
        path.write_bytes(data)

    def test_crlf_line_ends_are_valid(self) -> None:
        """A record saved with CRLF has front matter and a title."""
        self.write_bytes(
            b"---\r\nstatus: accepted\r\ndate: 2026-01-01\r\n"
            b"decision-makers: Ana\r\n---\r\n\r\n# Title\r\n"
        )
        self.assertEqual(self.findings(), [])

    def test_crlf_keeps_the_line_numbers_right(self) -> None:
        """A finding in a CRLF record is on the same line as with LF."""
        self.write_bytes(
            b"---\r\nstatus: superseded\r\ndate: 2026-01-01\r\n"
            b"decision-makers: Ana\r\n---\r\n\r\n# Title\r\n"
        )
        (finding,) = self.findings()
        self.assertTrue(finding.startswith("docs/decisions/0001-test.md:2: "), finding)

    def test_byte_order_mark_is_valid(self) -> None:
        """An editor that adds a UTF-8 byte order mark does not break the record."""
        self.write_bytes(
            b"\xef\xbb\xbf---\nstatus: accepted\ndate: 2026-01-01\n"
            b"decision-makers: Ana\n---\n\n# Title\n"
        )
        self.assertEqual(self.findings(), [])

    def test_binary_record_is_reported(self) -> None:
        """A record that is not UTF-8 text is a finding, not a crash."""
        path = self.root / "docs/decisions/0001-test.md"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"---\n\xff\xfe\n---\n")
        self.assertEqual(
            self.findings(),
            ["docs/decisions/0001-test.md:1: the file is not valid UTF-8 text"],
        )


class TitleRuleTest(TreeTestCase):
    """A record needs a level-1 heading after its front matter."""

    NO_TITLE = (
        "docs/decisions/0001-test.md:1: the record has no level-1 heading: put its "
        "title in a line that starts with `# ` after the front matter"
    )

    def record_with_body(self, body: str) -> None:
        """Write the record 0001 with valid front matter and this body."""
        self.write({"docs/decisions/0001-test.md": FRONT_MATTER + body})

    def test_record_without_a_heading_is_reported(self) -> None:
        """Front matter and a paragraph are not enough."""
        self.record_with_body("Only text.\n")
        self.assertEqual(self.findings(), [self.NO_TITLE])

    def test_level_two_heading_is_not_a_title(self) -> None:
        """Only a level-1 heading is the title."""
        self.record_with_body("## Context\n\n#hashtag\n")
        self.assertEqual(self.findings(), [self.NO_TITLE])

    def test_heading_in_a_code_block_is_not_a_title(self) -> None:
        """A `# comment` in an example does not count."""
        self.record_with_body("```sh\n# install\n```\n")
        self.assertEqual(self.findings(), [self.NO_TITLE])

    def test_heading_after_a_code_block_is_the_title(self) -> None:
        """The title may follow an example."""
        self.record_with_body("```\ncode\n```\n\n# Title\n")
        self.assertEqual(self.findings(), [])


class RecordTitleTest(unittest.TestCase):
    """`record_title` follows the CommonMark rules for headings and fences."""

    def test_title_is_the_first_level_one_heading(self) -> None:
        """The text of the heading is the title, without closing `#` marks."""
        self.assertEqual(record_title("Intro\n# Title ##\n# Other\n"), "Title")

    def test_title_follows_the_front_matter(self) -> None:
        """A BOM and CRLF line ends do not hide the title."""
        text = "\N{BYTE ORDER MARK}---\r\nstatus: accepted\r\n---\r\n\r\n# Title\r\n"
        self.assertEqual(record_title(text), "Title")

    def test_no_heading_gives_none(self) -> None:
        """Text without a level-1 heading has no title."""
        for text in ("", "plain\n", "#tag\n", "## two\n", "    # indented code\n"):
            with self.subTest(text=text):
                self.assertIsNone(record_title(text))

    def test_indented_code_is_not_a_heading(self) -> None:
        """Four spaces make code; three spaces still make a heading."""
        self.assertEqual(record_title("    # code\n   # Title\n"), "Title")

    def test_a_longer_fence_is_not_closed_by_a_shorter_one(self) -> None:
        """A block of four backticks may hold a block of three."""
        text = "````\n```\n# inner\n```\n````\n# Title\n"
        self.assertEqual(record_title(text), "Title")

    def test_a_longer_closing_fence_closes(self) -> None:
        """A closing fence may have more characters than the opening one."""
        self.assertEqual(record_title("```\n# a\n`````\n# Title\n"), "Title")

    def test_tilde_and_backtick_fences_do_not_close_each_other(self) -> None:
        """`~~~` closes with `~~~`, not with backticks, and the reverse."""
        tilde = "~~~\n# a\n```\n# b\n~~~\n# Title\n"
        backtick = "```\n# a\n~~~\n# b\n```\n# Title\n"
        self.assertEqual(record_title(tilde), "Title")
        self.assertEqual(record_title(backtick), "Title")

    def test_closing_fence_has_no_text_after_it(self) -> None:
        """A fence line with an info string opens a block but never closes one."""
        self.assertEqual(record_title("```\n# a\n``` x\n# b\n```\n# Title\n"), "Title")

    def test_info_string_may_follow_an_opening_fence(self) -> None:
        """`` ```python `` opens a block."""
        self.assertEqual(record_title("```python\n# a\n```\n# Title\n"), "Title")

    def test_inline_code_on_a_line_is_not_a_fence(self) -> None:
        """A backtick fence has no backtick in its info string."""
        self.assertEqual(record_title("```code``` here\n# Title\n"), "Title")

    def test_unclosed_fence_runs_to_the_end(self) -> None:
        """A block without a closing fence holds the rest of the text."""
        self.assertIsNone(record_title("```\n# a\n# b\n"))

    def test_later_headings_are_not_the_title(self) -> None:
        """The first level-1 heading after the front matter is the title."""
        text = FRONT_MATTER + "# The title\n\n## Context\n\n# Another\n"
        self.assertEqual(record_title(text), "The title")

    def test_closing_hashes_and_spaces_are_not_part_of_the_title(self) -> None:
        """`# Title ##` is the title `Title`; a `#` inside a word stays."""
        self.assertEqual(record_title(FRONT_MATTER + "# Title ##  \n"), "Title")
        self.assertEqual(record_title(FRONT_MATTER + "# Use C#\n"), "Use C#")

    def test_text_without_front_matter_is_read_whole(self) -> None:
        """The function does not require the front matter."""
        self.assertEqual(record_title("# Bare\n"), "Bare")


if __name__ == "__main__":
    unittest.main()
