"""Tests for finding citations in a text, without resolving them."""

import signal
import unittest
from pathlib import PurePosixPath
from types import FrameType

from decisions.citations import CitationKind, scan_text

REPO = "example/hub-test"
RECORD = CitationKind.RECORD_NUMBER
FILE = CitationKind.RECORD_FILE
SPEC = CitationKind.SPEC_NUMBER
DOC = CitationKind.DOC_PATH

IN_RECORDS_FOLDER = "docs/decisions/0001-first.md"
"""A path of the record folder, for a text that cites from inside it."""


def scan(
    text: str, *, prose: bool = True, path: str = "notes.md"
) -> list[tuple[CitationKind, str, int]]:
    """Scan `text` as the file `path` of `REPO`; return `(kind, value, line)`."""
    return [
        (citation.kind, citation.value, citation.line)
        for citation in scan_text(text, REPO, path=PurePosixPath(path), prose=prose)
    ]


class RecordFormTest(unittest.TestCase):
    """Each form that names a record."""

    def test_adr_and_decision_record_keywords(self) -> None:
        """`ADR 0012`, `ADR-0013` and `decision record 0014` name records."""
        self.assertEqual(
            scan("See ADR 0012, adr-0013 and Decision Record 0014."),
            [(RECORD, "0012", 1), (RECORD, "0013", 1), (RECORD, "0014", 1)],
        )

    def test_adr_with_a_dash_names_a_record(self) -> None:
        """`ADR-0016` is the usual way to write an ADR in a sentence."""
        self.assertEqual(
            scan("ADR-0016 and ADRs-0017"), [(RECORD, "0016", 1), (RECORD, "0017", 1)]
        )

    def test_lists_name_every_number(self) -> None:
        """A list with commas, `and`, `or` and `to` names each number."""
        self.assertEqual(
            scan(
                "decision records 0001, 0002 and 0003; ADRs 0004, 0005, or 0006; "
                "ADR 0007 to 0009; ADR-0010 and 0011"
            ),
            [
                (RECORD, "0001", 1),
                (RECORD, "0002", 1),
                (RECORD, "0003", 1),
                (RECORD, "0004", 1),
                (RECORD, "0005", 1),
                (RECORD, "0006", 1),
                (RECORD, "0007", 1),
                (RECORD, "0008", 1),
                (RECORD, "0009", 1),
                (RECORD, "0010", 1),
                (RECORD, "0011", 1),
            ],
        )

    def test_list_stops_at_a_word_that_is_not_a_number(self) -> None:
        """Only numbers continue a list."""
        self.assertEqual(
            scan("ADRs 0001 and the others, 0002 is another"), [(RECORD, "0001", 1)]
        )

    def test_bare_record_keyword_is_not_a_citation(self) -> None:
        """The word `record` alone is prose: a year or a count is not a record."""
        text = "audit records 2024 to 2026, record 0013, records 0001 and 0002"
        self.assertEqual(scan(text), [])

    def test_folder_prefix_names_a_record(self) -> None:
        """`docs/decisions/0042-` names the record that starts with it."""
        self.assertEqual(
            scan("Look in docs/decisions/0042-* for it."), [(RECORD, "0042", 1)]
        )

    def test_folder_path_names_a_record_in_every_file(self) -> None:
        """A name after `docs/decisions/` is a record file wherever it is cited."""
        self.assertEqual(
            scan("see docs/decisions/0043-other.md"),
            [(RECORD, "0043", 1), (FILE, "0043-other.md", 1)],
        )

    def test_dot_slash_prefix_names_the_same_folder(self) -> None:
        """`./docs/decisions/NNNN-x.md` and `./docs/a.md` are root paths."""
        self.assertEqual(
            scan("see ./docs/decisions/0043-other.md and ./docs/a.md"),
            [(RECORD, "0043", 1), (FILE, "0043-other.md", 1), (DOC, "docs/a.md", 1)],
        )

    def test_nested_record_folder_is_not_the_record_folder(self) -> None:
        """`services/api/docs/decisions/` belongs to another tree and is not checked."""
        text = (
            "see services/api/docs/decisions/0003-api.md, ../docs/decisions/0004-x.md "
            "and a/docs/decisions/0005-"
        )
        self.assertEqual(scan(text), [])

    def test_address_of_this_repository_names_a_record(self) -> None:
        """`blob` and `tree` addresses of the repository count, in any letter case."""
        base = "https://github.com/Example/HUB-test"
        self.assertEqual(
            scan(f"{base}/blob/main/docs/decisions/0001-x.md"),
            [(RECORD, "0001", 1), (FILE, "0001-x.md", 1)],
        )
        self.assertEqual(
            scan(f"{base}/tree/v1.2/docs/decisions/0042-"), [(RECORD, "0042", 1)]
        )

    def test_address_of_another_repository_is_not_this_one(self) -> None:
        """The owner and the name must both be those of the checked repository."""
        base = "https://github.com"
        for address in (
            f"{base}/other/hub-test/blob/main/docs/decisions/0001-x.md",
            f"{base}/example/hub/blob/main/docs/decisions/0001-x.md",
            f"{base}/example/hub-test2/blob/main/docs/decisions/0001-x.md",
        ):
            with self.subTest(address=address):
                self.assertEqual(scan(address), [])

    def test_placeholders_never_match(self) -> None:
        """The literal placeholder `NNNN` has no digits."""
        text = (
            "ADR NNNN, ADRs NNNN, NNNN and NNNN, decision record NNNN, spec NNNN, "
            "docs/decisions/NNNN-slug.md, NNNN-slug.md, docs/specs/NNNN-x.md"
        )
        self.assertEqual(scan(text), [])

    def test_dates_and_long_numbers_are_not_numbers(self) -> None:
        """A date, a five-digit number and a version are not record numbers."""
        self.assertEqual(scan("ADR 2026-11-08, ADR 12345, ADR 123, spec 1.2.3"), [])

    def test_keyword_inside_a_word_does_not_match(self) -> None:
        """`RADR 0001` and `ADR_0001` are not citations."""
        self.assertEqual(scan("RADR 0001 and ADR_0001"), [])

    def test_dash_between_two_numbers_is_a_range(self) -> None:
        """A hyphen or an en dash joins two numbers as `to` does."""
        self.assertEqual(
            scan("ADRs 0001-0003, ADR 0007 – 0009 and specs 0004–0005"),
            [
                (RECORD, "0001", 1),
                (RECORD, "0002", 1),
                (RECORD, "0003", 1),
                (RECORD, "0007", 1),
                (RECORD, "0008", 1),
                (RECORD, "0009", 1),
                (SPEC, "0004", 1),
                (SPEC, "0005", 1),
            ],
        )

    def test_range_does_not_turn_a_date_or_a_file_name_into_a_number(self) -> None:
        """`ADR 0001-slug`, a date and a dash before a word keep their meaning."""
        self.assertEqual(
            scan("ADR-0016-some-slug and ADR 2026-11-08"), [(RECORD, "0016", 1)]
        )


def records(*numbers: str, line: int = 1) -> list[tuple[CitationKind, str, int]]:
    """Return the scan result for record numbers that are cited on `line`."""
    return [(RECORD, number, line) for number in numbers]


class RangeTest(unittest.TestCase):
    """A range names every number from its start to its end, both included."""

    def test_to_and_both_dashes_name_every_number_between(self) -> None:
        """`to` in any letter case, a hyphen and an en dash all join the ends."""
        for joiner in (" to ", " TO ", " To ", "-", " - ", "–", " – "):
            with self.subTest(joiner=joiner):
                self.assertEqual(
                    scan(f"ADRs 0007{joiner}0010"),
                    records("0007", "0008", "0009", "0010"),
                )

    def test_spec_range_names_every_spec(self) -> None:
        """The rule is the same for specs as for records."""
        self.assertEqual(
            scan("specs 0004 to 0006 and spec 0010–0011"),
            [
                (SPEC, "0004", 1),
                (SPEC, "0005", 1),
                (SPEC, "0006", 1),
                (SPEC, "0010", 1),
                (SPEC, "0011", 1),
            ],
        )

    def test_equal_ends_name_one_number(self) -> None:
        """A range of one number is that number, once."""
        for text in ("ADRs 0007 to 0007", "ADRs 0007-0007", "ADRs 0007 – 0007"):
            with self.subTest(text=text):
                self.assertEqual(scan(text), records("0007"))

    def test_reversed_range_is_reported_and_keeps_its_ends(self) -> None:
        """A range that runs down is a finding; its two ends are still cited."""
        for text in ("ADRs 0009 to 0007", "ADRs 0009-0007", "ADRs 0009 – 0007"):
            with self.subTest(text=text):
                self.assertCountEqual(
                    scan(text),
                    [
                        (RECORD, "0009", 1),
                        (CitationKind.REVERSED_RANGE, "0009 to 0007", 1),
                        (RECORD, "0007", 1),
                    ],
                )

    def test_mixed_list_expands_only_the_ranges(self) -> None:
        """A comma, `and` and `or` never join the ends of a range."""
        expected = records("0001", "0003", "0004", "0005", "0009")
        for text in (
            "ADRs 0001, 0003 to 0005 and 0009",
            "ADRs 0001, 0003-0005 and 0009",
            "ADRs 0001, 0003–0005 or 0009",
            "ADRs 0001 and 0003 to 0005, 0009",
        ):
            with self.subTest(text=text):
                self.assertEqual(scan(text), expected)

    def test_chain_of_ranges_names_each_number_once(self) -> None:
        """`0001 to 0003 to 0005` is two ranges that share 0003."""
        self.assertEqual(
            scan("ADRs 0001 to 0003 to 0005"),
            records("0001", "0002", "0003", "0004", "0005"),
        )

    def test_range_at_the_top_of_the_number_space(self) -> None:
        """`9999` is a valid end, and a five-digit number is not a number."""
        self.assertEqual(scan("ADRs 9998 to 9999"), records("9998", "9999"))
        self.assertEqual(scan("ADRs 0001 to 12345"), records("0001"))

    def test_widest_range_names_9999_numbers(self) -> None:
        """`0001 to 9999` expands to all numbers, in order and with no repeat."""
        found = scan("ADRs 0001 to 9999")
        self.assertEqual(
            [value for _, value, _ in found],
            [f"{number:04d}" for number in range(1, 10000)],
        )

    def test_ranges_of_one_file_name_a_bounded_count_of_numbers(self) -> None:
        """A range that does not fit in the budget keeps its ends and is flagged."""
        oversized = CitationKind.OVERSIZED_RANGE
        found = scan("ADRs 0001 to 9999\n\nADRs 0001 to 0003 and 0005\n")
        self.assertEqual(len(found), 9999 + 4)
        self.assertCountEqual(
            found[-4:],
            [
                (oversized, "0001 to 0003", 3),
                (RECORD, "0001", 3),
                (RECORD, "0003", 3),
                (RECORD, "0005", 3),
            ],
        )

    def test_many_small_ranges_use_up_the_budget_too(self) -> None:
        """The budget counts the numbers of all ranges, not of one range."""
        found = scan("ADRs 0001 to 0010\n\n" * 1001)
        flagged = [item for item in found if item[0] is CitationKind.OVERSIZED_RANGE]
        self.assertEqual(
            flagged, [(CitationKind.OVERSIZED_RANGE, "0001 to 0010", 2001)]
        )

    def test_date_is_not_an_end_of_a_range(self) -> None:
        """A date after `to` or a dash ends the list instead of closing a range."""
        self.assertEqual(scan("ADRs 0001 to 2026-11-08"), records("0001"))
        self.assertEqual(scan("ADR 2026-11-08 to 0003"), [])

    def test_other_joiners_make_no_range(self) -> None:
        """An em dash, a doubled `to` and a five-digit end close no range."""
        for text in (
            "ADRs 0001—0003",
            "ADRs 0001 to to 0003",
            "ADRs 0001 to 00003",
            "ADRs 0001 and to 0003",
        ):
            with self.subTest(text=text):
                self.assertEqual(scan(text), records("0001"))

    def test_crlf_and_byte_order_mark_do_not_hide_a_range(self) -> None:
        """A BOM at the start and CRLF line ends leave the range and its line."""
        text = "﻿ADRs 0007 –\r\n0009\r\n\r\nSee ADRs 0012 to 0013.\r\n"
        self.assertEqual(
            scan(text),
            records("0007", "0008", "0009") + records("0012", "0013", line=4),
        )

    def test_crlf_and_byte_order_mark_do_not_hide_a_range_in_code(self) -> None:
        """A line is one sentence in code, so the range is on one line."""
        text = "﻿# ADRs 0007 – 0009\r\n# See ADRs 0012-0013.\r\n"
        self.assertEqual(
            scan(text, prose=False),
            records("0007", "0008", "0009") + records("0012", "0013", line=2),
        )

    def test_range_is_reported_at_the_line_of_its_keyword(self) -> None:
        """A range that wraps over lines belongs to the line of `ADRs`."""
        self.assertEqual(
            scan("Intro.\n\nSee ADRs 0007\nto 0008.\n"), records("0007", "0008", line=3)
        )

    def test_foreign_repository_skips_every_number_of_a_range(self) -> None:
        """A range that another repository qualifies is not about this one."""
        text = "In `example/other`, ADRs 0001 to 0003 hold. ADRs 0005 to 0006 hold."
        self.assertEqual(scan(text), records("0005", "0006"))


def range_ids(text: str) -> list[int | None]:
    """Scan `text` as prose of `REPO` and return the range id of each citation."""
    return [
        citation.range_id
        for citation in scan_text(
            text, REPO, path=PurePosixPath("notes.md"), prose=True
        )
    ]


class DashSlugTest(unittest.TestCase):
    """A dash that leads into a slug or a date makes no range."""

    def test_slug_that_starts_with_a_year_cites_the_first_number_only(self) -> None:
        """`ADR-NNNN-2026-roadmap` is a record with a slug, not 0005 to 2026."""
        self.assertEqual(scan("See ADR-0005-2026-roadmap."), records("0005"))

    def test_slug_that_starts_with_a_number_after_other_keywords(self) -> None:
        """Every keyword form and a list item treat the slug in the same way."""
        for text in (
            "decision record 0005-2026-roadmap",
            "ADRs-0005-2026-roadmap",
            "ADR 0005-2026-02-01",
            "ADRs 0005-0006-roadmap",
        ):
            with self.subTest(text=text):
                self.assertEqual(scan(text), records("0005"))
        self.assertEqual(scan("ADRs 0001, 0005-2026-roadmap"), records("0001", "0005"))
        numbers = ("0001", "0002", "0003", "0004", "0005")
        self.assertEqual(
            scan("specs 0001 to 0005-2026-roadmap"),
            [(SPEC, number, 1) for number in numbers],
        )

    def test_en_dash_slug_cites_the_first_number_only(self) -> None:
        """An en dash after the second number leads into a slug too."""
        for text in (
            "ADR 0005–2026–roadmap",
            "ADR 0005-2026–roadmap",
            "ADR 0005 – 2026–roadmap",
        ):
            with self.subTest(text=text):
                self.assertEqual(scan(text), records("0005"))

    def test_crlf_after_a_slug_keeps_the_line_numbers(self) -> None:
        """A CRLF line end after the slug neither joins lines nor makes a range."""
        text = "ADR-0005-2026-roadmap\r\nand ADR 0007-2026-plan\r\n"
        self.assertEqual(scan(text), records("0005") + records("0007", line=2))

    def test_crlf_and_byte_order_mark_before_a_slug(self) -> None:
        """A BOM before the keyword does not hide the slug form either."""
        self.assertEqual(
            scan("﻿ADR 0005-2026-roadmap\r\n", prose=False), records("0005")
        )

    def test_four_digits_before_a_plain_end_after_a_plural_are_a_range(self) -> None:
        """No dash after the end: the writer gave two numbers, whatever they mean.

        `ADRs 0001-2026 here.` is a range from 0001 to 2026 by the rules, because
        a plural keyword takes an unspaced hyphen as a range joiner. The
        singular keyword does not: see `DashRangeKeywordTest`.
        """
        for text in ("ADRs 0001-2026 here.", "decision records 0001-2026 here."):
            with self.subTest(text=text):
                found = scan(text)
                self.assertEqual(len(found), 2026)
                self.assertEqual((found[0][1], found[-1][1]), ("0001", "2026"))

    def test_to_range_may_end_at_the_number_that_opens_a_slug(self) -> None:
        """Only a dash joiner depends on what follows the end; `to` does not.

        The second number is the first number of the slug `NNNN-2026-x`, so the
        range ends there and the slug adds no number.
        """
        self.assertEqual(
            scan("ADR 0005 to 0007-2026-x"), records("0005", "0006", "0007")
        )

    def test_numbers_of_one_range_share_an_id(self) -> None:
        """The id tells a range from a number that the text cites alone."""
        ids = range_ids("ADRs 0001, 0003 to 0005, 0007 and 0009-0010")
        self.assertEqual(ids[0], None)
        self.assertEqual(len(set(ids[1:4])), 1)
        self.assertIsNotNone(ids[1])
        self.assertEqual(ids[4], None)
        self.assertEqual(len(set(ids[5:])), 1)
        self.assertNotEqual(ids[1], ids[5])

    def test_chain_of_ranges_is_one_range_and_equal_ends_are_none(self) -> None:
        """`0001 to 0003 to 0005` is one id; `0007 to 0007` has none."""
        chain = range_ids("ADRs 0001 to 0003 to 0005")
        self.assertEqual(len(chain), 5)
        self.assertEqual(len(set(chain)), 1)
        self.assertIsNotNone(chain[0])
        self.assertEqual(range_ids("ADRs 0007 to 0007"), [None])

    def test_ids_are_unique_in_a_file_and_unset_for_other_kinds(self) -> None:
        """Two ranges of a file never share an id, and a path has none."""
        ids = range_ids("ADRs 0001 to 0002.\n\nADRs 0001 to 0002 in docs/a.md")
        self.assertEqual(len(set(ids[:2])), 1)
        self.assertEqual(len(set(ids[2:4])), 1)
        self.assertNotEqual(ids[0], ids[2])
        self.assertEqual(ids[4], None)


class DashRangeKeywordTest(unittest.TestCase):
    """What a dash joins depends on the keyword and on the spaces around it.

    An en dash, and a hyphen with a space on both sides, make a range after any
    keyword. A hyphen with no space makes a range only after a plural keyword.
    """

    def test_en_dash_and_spaced_hyphen_make_a_range_after_a_singular(self) -> None:
        """`ADR 0007 – 0009` and `ADR 0007 - 0009` name 0007 to 0009."""
        for text in (
            "ADR 0007 – 0009",
            "ADR 0007 - 0009",
            "ADR 0007–0009",
            "decision record 0007 - 0009",
            "ADR-0007 – 0009",
        ):
            with self.subTest(text=text):
                self.assertEqual(scan(text), records("0007", "0008", "0009"))

    def test_en_dash_and_spaced_hyphen_make_a_range_after_a_plural(self) -> None:
        """The plural keyword reads the spaced forms in the same way."""
        for text in ("ADRs 0007 – 0009", "ADRs 0007 - 0009", "ADRs 0007–0009"):
            with self.subTest(text=text):
                self.assertEqual(scan(text), records("0007", "0008", "0009"))

    def test_unspaced_hyphen_makes_a_range_after_a_plural(self) -> None:
        """`ADRs 0001-0003` and `decision records 0001-0003` are ranges."""
        for text in (
            "ADRs 0001-0003",
            "decision records 0001-0003",
            "ADRS 0001-0003",
            "Decision Records 0001-0003",
            "ADRs-0001-0003",
        ):
            with self.subTest(text=text):
                self.assertEqual(scan(text), records("0001", "0002", "0003"))

    def test_unspaced_hyphen_cites_the_first_number_after_a_singular(self) -> None:
        """`ADR-NNNN-MMMM` is a record with a name, not a range."""
        for text in (
            "ADR-0001-0003",
            "adr-0001-0003",
            "ADR 0001-0003",
            "decision record 0001-0003",
            "Decision Record 0001-0003",
        ):
            with self.subTest(text=text):
                self.assertEqual(scan(text), records("0001"))

    def test_singular_keyword_before_a_year_cites_the_record_only(self) -> None:
        """`ADR 0005-2026 plan` names record 0005, not 0005 to 2026."""
        for text in (
            "ADR 0005-2026 plan",
            "ADR-0005-2026-roadmap",
            "ADR-0005-2026",
            "ADR 0005-2026.",
        ):
            with self.subTest(text=text):
                self.assertEqual(scan(text), records("0005"))

    def test_plural_keyword_before_a_year_is_a_range(self) -> None:
        """The plural keyword makes `ADRs 0001-2026 here.` a range to 2026."""
        found = scan("ADRs 0001-2026 here.")
        self.assertEqual(len(found), 2026)
        self.assertEqual(
            (found[0], found[-1]), ((RECORD, "0001", 1), (RECORD, "2026", 1))
        )

    def test_slug_and_date_exclusion_holds_after_both_keywords(self) -> None:
        """A second number that a dash and a letter or digit follow is no end."""
        for text in (
            "ADRs 0001-0003-foo",
            "ADRs 0001-2026-02-01",
            "ADR 0001-0003-foo",
            "ADR 0001 – 0003-foo",
            "ADR 0001 – 0003–foo",
        ):
            with self.subTest(text=text):
                self.assertEqual(scan(text), records("0001"))

    def test_hyphen_with_one_space_is_unspaced(self) -> None:
        """A hyphen needs a space on both sides to count as spaced."""
        for text in ("ADR 0001 -0003", "ADR 0001- 0003"):
            with self.subTest(text=text):
                self.assertEqual(scan(text), records("0001"))
        for text in ("ADRs 0001 -0003", "ADRs 0001- 0003"):
            with self.subTest(text=text):
                self.assertEqual(scan(text), records("0001", "0002", "0003"))

    def test_list_keeps_the_number_of_its_keyword(self) -> None:
        """A range inside a list follows the keyword that opens the list."""
        self.assertEqual(
            scan("ADRs 0001, 0003-0005"), records("0001", "0003", "0004", "0005")
        )
        self.assertEqual(scan("ADR 0001, 0003-0005"), records("0001", "0003"))
        self.assertEqual(scan("ADR 0001 and 0003-0005"), records("0001", "0003"))
        self.assertEqual(
            scan("ADR 0001, 0003 - 0005"), records("0001", "0003", "0004", "0005")
        )

    def test_a_later_keyword_starts_its_own_list(self) -> None:
        """The keyword of a list is the nearest one before it."""
        self.assertEqual(
            scan("ADR 0001-0003 and ADRs 0005-0006"),
            records("0001", "0005", "0006"),
        )

    def test_specs_follow_the_same_rule(self) -> None:
        """`specs` is plural and `spec` is singular, in any letter case."""
        self.assertEqual(
            scan("specs 0001-0002; SPECS 0004-0005"),
            [
                (SPEC, "0001", 1),
                (SPEC, "0002", 1),
                (SPEC, "0004", 1),
                (SPEC, "0005", 1),
            ],
        )
        self.assertEqual(scan("spec 0001-0003"), [(SPEC, "0001", 1)])
        self.assertEqual(
            scan("spec 0001 - 0002"), [(SPEC, "0001", 1), (SPEC, "0002", 1)]
        )

    def test_plural_range_keeps_one_range_id(self) -> None:
        """A range after a plural keyword is one range; a lead number has none."""
        self.assertEqual(len(set(range_ids("ADRs 0001-0003"))), 1)
        self.assertEqual(range_ids("ADR-0001-0003"), [None])


class RelativeFileTest(unittest.TestCase):
    """A file name without the record folder names a record by where it is cited."""

    def test_bare_name_outside_the_record_folder_is_not_a_record(self) -> None:
        """`0042-x.md` in a file elsewhere is some other file, such as a spec."""
        self.assertEqual(scan("[a](0042-some-slug.md)", path="docs/specs/a.md"), [])
        self.assertEqual(scan("[a](0042-some-slug.md)", path="notes.md"), [])

    def test_bare_name_in_the_record_folder_is_a_record_file(self) -> None:
        """A record, or the README of the folder, cites its siblings by name."""
        for path in (IN_RECORDS_FOLDER, "docs/decisions/README.md"):
            with self.subTest(path=path):
                self.assertEqual(
                    scan("[a](0042-some-slug.md) and ./0043-x.md", path=path),
                    [(FILE, "0042-some-slug.md", 1), (FILE, "0043-x.md", 1)],
                )

    def test_link_that_resolves_into_the_record_folder_is_a_record_file(self) -> None:
        """`../decisions/0007-x.md` counts from a page in a sibling folder."""
        self.assertEqual(
            scan("[a](../decisions/0007-x.md)", path="docs/how-to/a.md"),
            [(FILE, "0007-x.md", 1)],
        )

    def test_link_that_resolves_elsewhere_is_not_a_record_file(self) -> None:
        """The same text from a page at another depth leads to another folder."""
        text = "[a](../decisions/0007-x.md)"
        self.assertEqual(scan(text, path="docs/a.md"), [])
        self.assertEqual(scan(text, path="a.md"), [])

    def test_link_that_leads_to_another_docs_folder_is_not_a_record_file(self) -> None:
        """`../docs/decisions/` from `docs/how-to/` is `docs/docs/decisions/`."""
        self.assertEqual(
            scan("[a](../docs/decisions/0005-x.md)", path="docs/how-to/a.md"), []
        )

    def test_how_to_page_links_a_record_with_a_relative_path(self) -> None:
        """`../decisions/0005-x.md` from `docs/how-to/adopt-the-hub.md` is a record."""
        self.assertEqual(
            scan("[a](../decisions/0005-x.md)", path="docs/how-to/adopt-the-hub.md"),
            [(FILE, "0005-x.md", 1)],
        )

    def test_name_in_another_folder_is_not_a_record(self) -> None:
        """`docs/specs/0006-x.md` is a spec file, not a record file."""
        found = scan("see docs/specs/0006-x.md", path=IN_RECORDS_FOLDER)
        self.assertEqual(found, [(DOC, "docs/specs/0006-x.md", 1)])


class SpecAndPathTest(unittest.TestCase):
    """The forms that name a spec or a page."""

    def test_spec_numbers(self) -> None:
        """`spec 0006` and a list of specs name spec numbers."""
        self.assertEqual(
            scan("spec 0006 and specs 0001 and 0002"),
            [(SPEC, "0006", 1), (SPEC, "0001", 1), (SPEC, "0002", 1)],
        )

    def test_documentation_paths(self) -> None:
        """A `docs/` path ends at `.md`, even before punctuation or an anchor."""
        self.assertEqual(
            scan("Read docs/a.md. Then (docs/b/c.md#top), `docs/d-e.md`."),
            [(DOC, "docs/a.md", 1), (DOC, "docs/b/c.md", 1), (DOC, "docs/d-e.md", 1)],
        )

    def test_paths_that_are_not_checked(self) -> None:
        """Relative links, URLs, globs, placeholders and other files are left."""
        text = (
            "[x](../docs/a.md) https://example.org/docs/b.md docs/**/*.md "
            "docs/<area>/c.md docs/decisions/NNNN-slug.md docs/d.mdx docs/e.txt"
        )
        self.assertEqual(scan(text), [])

    def test_record_file_under_decisions_is_not_a_page_path(self) -> None:
        """A record file path is checked as a record, not as a page."""
        self.assertEqual(
            scan("docs/decisions/0001-x.md"),
            [(RECORD, "0001", 1), (FILE, "0001-x.md", 1)],
        )

    def test_other_decisions_page_is_a_page_path(self) -> None:
        """`docs/decisions/README.md` is a page that must exist."""
        self.assertEqual(
            scan("docs/decisions/README.md"), [(DOC, "docs/decisions/README.md", 1)]
        )


class ForeignCitationTest(unittest.TestCase):
    """A citation that another repository qualifies is skipped, and no other."""

    def test_name_before_a_citation_skips_that_citation_only(self) -> None:
        """`example/other ADR 0002` is foreign; its neighbors are the hub's."""
        text = "ADR 0001 holds. In `example/other`, ADR 0002 holds. ADR 0003 holds."
        self.assertEqual(scan(text), [(RECORD, "0001", 1), (RECORD, "0003", 1)])

    def test_name_in_a_sentence_does_not_skip_the_other_citations(self) -> None:
        """A sentence that names a repository and cites a record of its own."""
        text = "ADR 0004 says `example/other` ADR 0038 differs, as ADR 0005 does."
        self.assertEqual(scan(text), [(RECORD, "0004", 1), (RECORD, "0005", 1)])

    def test_hub_text_about_a_record_of_another_repository_still_counts(self) -> None:
        """Text that only names the repository and then talks on is the hub's."""
        text = "The example/other repository keeps a record. See ADR 0004 here."
        self.assertEqual(scan(text), [(RECORD, "0004", 1)])

    def test_qualified_citation_wrapped_over_lines_is_skipped(self) -> None:
        """The repository name and the citation may sit on different lines."""
        text = "See `example/other`\nADR 0038 and ADR 0004."
        self.assertEqual(scan(text), [(RECORD, "0004", 2)])

    def test_every_citation_in_a_foreign_address_is_skipped(self) -> None:
        """A path inside `github.com/<other>/<repo>/...` belongs to that repository."""
        text = "See https://github.com/other/thing/blob/main/docs/decisions/0001-x.md."
        self.assertEqual(scan(text), [])

    def test_citation_after_a_foreign_address_counts(self) -> None:
        """The address ends at the space: the next citation is the hub's."""
        text = "See https://github.com/other/thing/blob/main/docs/x.md and ADR 0001."
        self.assertEqual(scan(text), [(RECORD, "0001", 1)])

    def test_citation_in_a_foreign_markdown_link_is_skipped(self) -> None:
        """The text and the address of one link are the same citation."""
        text = (
            "[ADR 0038](https://github.com/example/other/blob/main/docs/adr/x.md) "
            "and [example/other ADR 0039](https://example.org/x) and ADR 0004."
        )
        self.assertEqual(scan(text), [(RECORD, "0004", 1)])

    def test_github_pages_that_are_not_repositories_are_not_foreign(self) -> None:
        """`github.com/orgs/x` and `github.com/features/y` name no repository."""
        for url in (
            "https://github.com/orgs/other/settings/actions",
            "https://github.com/features/actions",
            "https://github.com/settings/profile",
        ):
            with self.subTest(url=url):
                self.assertEqual(
                    scan(f"See {url} and ADR 0001."), [(RECORD, "0001", 1)]
                )

    def test_short_name_is_foreign_in_any_letter_case(self) -> None:
        """`Example/Other` qualifies the citation after it, as `example/other`."""
        self.assertEqual(
            scan("`Example/Other` ADR 0002 and ADR 0003."), [(RECORD, "0003", 1)]
        )

    def test_short_name_takes_its_owner_from_the_checked_repository(self) -> None:
        """In `acme/hub`, `acme/other` is foreign and `example/other` is not."""
        path = PurePosixPath("notes.md")
        found = scan_text(
            "`acme/other` ADR 0001 and `example/other` ADR 0002.",
            "acme/hub",
            path=path,
            prose=True,
        )
        self.assertEqual([citation.value for citation in found], ["0002"])

    def test_own_repository_is_not_foreign(self) -> None:
        """The named repository, by URL or short name, is not foreign."""
        text = (
            "See https://github.com/example/hub-test/blob/main/docs/decisions/"
            "0001-x.md and example/hub-test. ADR 0002."
        )
        self.assertEqual(
            scan(text),
            [(RECORD, "0001", 1), (FILE, "0001-x.md", 1), (RECORD, "0002", 1)],
        )

    def test_hub_style_repository_name(self) -> None:
        """The name `.github` ends at a slash, and a final dot is punctuation."""
        hub = "example/.github"
        path = PurePosixPath("notes.md")
        own = scan_text(
            "Use example/.github/x.yml. ADR 0001.", hub, path=path, prose=True
        )
        other = scan_text("Use example/other. ADR 0001.", hub, path=path, prose=True)
        self.assertEqual([c.value for c in own], ["0001"])
        # The final dot ends the name, so the next sentence counts.
        self.assertEqual([c.value for c in other], ["0001"])
        # A foreign name before a citation, in a line of code, qualifies it.
        line = scan_text("example/other ADR 0001", hub, path=path, prose=False)
        self.assertEqual(line, [])

    def test_other_github_hosts_are_not_repositories(self) -> None:
        """`docs.github.com/en/x` is not `github.com/<owner>/<repo>`."""
        text = "See https://docs.github.com/en/communities and ADR 0001."
        self.assertEqual(scan(text), [(RECORD, "0001", 1)])


class SegmentationTest(unittest.TestCase):
    """Prose is cut into sentences and code into lines."""

    def test_line_numbers_follow_the_text(self) -> None:
        """A citation reports the line where it starts."""
        text = "one\n\ntwo ADR 0001\nthree\ndecision record\n0002\n"
        self.assertEqual(scan(text), [(RECORD, "0001", 3), (RECORD, "0002", 5)])

    def test_line_numbers_with_many_lines(self) -> None:
        """The line of a citation far down a text counts every newline above."""
        text = "line\n" * 500 + "ADR 0001\n" + "line\n" * 500 + "ADR 0002"
        self.assertEqual(scan(text), [(RECORD, "0001", 501), (RECORD, "0002", 1002)])

    def test_prose_spans_wrapped_lines(self) -> None:
        """In prose, a keyword and its number may be on two lines."""
        self.assertEqual(scan("see ADR\n0001 for it"), [(RECORD, "0001", 1)])

    def test_code_is_cut_into_lines(self) -> None:
        """In code, a keyword and a number on two lines are not a citation."""
        text = "# see ADR\n# 0001 for it\nx = 1  # spec 0006\n"
        self.assertEqual(scan(text, prose=False), [(SPEC, "0006", 3)])

    def test_foreign_line_in_code_does_not_hide_other_lines(self) -> None:
        """A repository name in one line of code does not skip the next line."""
        text = "# example/other ADR 0001\n# ADR 0002\n"
        self.assertEqual(scan(text, prose=False), [(RECORD, "0002", 2)])

    def test_table_rows_and_list_items_are_separate_segments(self) -> None:
        """A foreign row of a table or item of a list does not hide the others."""
        table = "| a | example/other ADR 0001 |\n| b | ADR 0002 |\n"
        items = "- example/other ADR 0001\n- ADR 0002\n"
        self.assertEqual(scan(table), [(RECORD, "0002", 2)])
        self.assertEqual(scan(items), [(RECORD, "0002", 2)])


class ScanTimeTest(unittest.TestCase):
    """The scan time grows in step with the size of a text."""

    TIME_LIMIT_SECONDS = 10.0

    @unittest.skipUnless(hasattr(signal, "setitimer"), "needs POSIX interval timers")
    def test_one_megabyte_line_of_brackets_is_scanned_in_linear_time(self) -> None:
        """A long run of `[` after a repository name must not blow up the scan.

        This test uses a time limit because the failure it guards against is a
        slow scan, not a wrong result: a link pattern that rescans the rest of
        the line from each `[` needs hours on this text, and a plain assertion
        would hang the whole run. A timer signal turns the hang into a failure.
        """
        text = "example/other ADR 0001 " + "[" * 1_000_000
        self.assertEqual(self.scan_within_limit(text), [])
        text = "example/other ADR 0001 " + "[a](" * 250_000
        self.assertEqual(self.scan_within_limit(text), [])

    @unittest.skipUnless(hasattr(signal, "setitimer"), "needs POSIX interval timers")
    def test_repeated_full_width_ranges_are_scanned_in_bounded_time(self) -> None:
        """Repeating `0001 to 9999` must not multiply the findings without bound.

        This test uses a time limit for the reason that the test above gives:
        without the budget of a file, 60 000 such lines name 600 million
        numbers, and the scan runs for minutes and fills the memory.
        """
        found = self.scan_within_limit("ADRs 0001 to 9999\n" * 60_000)
        self.assertEqual(len(found), 9999 + 3 * 59_999)

    def scan_within_limit(self, text: str) -> list[tuple[CitationKind, str, int]]:
        """Scan `text` and fail the test when the scan takes too long."""

        def on_timeout(_signal: int, _frame: FrameType | None) -> None:
            self.fail(f"the scan took more than {self.TIME_LIMIT_SECONDS} seconds")

        previous = signal.signal(signal.SIGALRM, on_timeout)
        signal.setitimer(signal.ITIMER_REAL, self.TIME_LIMIT_SECONDS)
        try:
            return scan(text)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)


if __name__ == "__main__":
    unittest.main()
