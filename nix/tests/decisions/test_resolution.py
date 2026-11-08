"""Tests that citations resolve against the records, the ledger and the files."""

import unittest

from support import LEDGER, TreeTestCase, ledger_entry, record_text


class RecordCitationTest(TreeTestCase):
    """A citation of a record resolves to a record in force."""

    def setUp(self) -> None:
        """Write records 0001 and 0002, and a ledger with 0005 and 0006."""
        super().setUp()
        self.write(
            {
                "docs/decisions/0001-first.md": record_text(),
                "docs/decisions/0002-second.md": record_text(),
                LEDGER: ledger_entry("0005", "0002") + ledger_entry("0006"),
            }
        )

    def test_existing_records_resolve_in_every_form(self) -> None:
        """Every form of a citation of a record in force passes."""
        self.write(
            {
                "README.md": "ADR 0001, ADR-0002, decision record 0002, "
                "ADRs 0001 and 0002.\nSee docs/decisions/0001-first.md.\n",
                "docs/how-to/a.md": "See [it](../decisions/0002-second.md).\n",
                "docs/decisions/0001-first.md": record_text("See (0002-second.md).\n"),
            }
        )
        self.assertEqual(self.findings(), [])

    def test_missing_record_is_reported_at_its_line(self) -> None:
        """A number that no file and no ledger entry has does not exist."""
        self.write({"notes.md": "Intro.\n\nSee ADR 0042 for it.\n"})
        self.assertEqual(
            self.findings(), ["notes.md:3: decision record 0042 does not exist"]
        )

    def test_one_missing_number_in_a_list_is_reported(self) -> None:
        """Only the numbers that do not resolve get a finding."""
        self.write({"notes.md": "decision records 0001, 0042 and 0002\n"})
        self.assertEqual(
            self.findings(), ["notes.md:1: decision record 0042 does not exist"]
        )

    def test_wrong_slug_is_reported(self) -> None:
        """A file name whose number exists, with another slug, is stale."""
        self.write(
            {"docs/decisions/0002-second.md": record_text("[x](0001-renamed.md)\n")}
        )
        self.assertEqual(
            self.findings(),
            [
                "docs/decisions/0002-second.md:9: "
                "no decision record file is named 0001-renamed.md"
            ],
        )

    def test_bare_file_name_outside_the_record_folder_is_not_a_record(self) -> None:
        """A spec file `0099-x.md` linked from a page is not a record citation."""
        self.write(
            {
                "docs/specs/0099-x.md": "# X\n",
                "docs/guide.md": "[the spec](0099-x.md) and [again](./0099-x.md)\n",
            }
        )
        self.assertEqual(self.findings(), [])

    def test_wrong_slug_is_reported_in_a_link_from_a_sibling_folder(self) -> None:
        """`../decisions/0001-renamed.md` from `docs/how-to/` is a record link."""
        self.write({"docs/how-to/a.md": "[x](../decisions/0001-renamed.md)\n"})
        self.assertEqual(
            self.findings(),
            ["docs/how-to/a.md:1: no decision record file is named 0001-renamed.md"],
        )

    def test_record_without_a_decision_keyword_is_not_a_citation(self) -> None:
        """The bare word `record` and a year are prose, not a record number."""
        self.write({"notes.md": "The audit records 2024 to 2026 and record 0042.\n"})
        self.assertEqual(self.findings(), [])

    def test_missing_number_in_a_path_is_reported_once(self) -> None:
        """A path with a missing number gives one finding, not one per form."""
        self.write({"notes.md": "see docs/decisions/0042-gone.md\n"})
        self.assertEqual(
            self.findings(), ["notes.md:1: decision record 0042 does not exist"]
        )

    def test_deleted_record_is_reported_with_its_successor(self) -> None:
        """Outside the ledger and the successor, a deleted number is stale."""
        self.write({"notes.md": "ADR 0005 said so.\n"})
        self.assertEqual(
            self.findings(),
            [
                "notes.md:1: decision record 0005 was deleted into the ledger: "
                "cite its successor, ADR 0002"
            ],
        )

    def test_withdrawn_record_is_reported(self) -> None:
        """A withdrawn record has no successor to cite instead."""
        self.write({"notes.md": "ADR 0006 said so.\n"})
        self.assertEqual(
            self.findings(),
            [
                "notes.md:1: decision record 0006 was withdrawn into the ledger: "
                "remove the citation"
            ],
        )

    def test_successor_may_cite_the_deleted_record(self) -> None:
        """The record that replaced 0005 may name it, as a number or a path."""
        self.write(
            {
                "docs/decisions/0002-second.md": record_text(
                    "It replaces ADR 0005 (docs/decisions/0005-deleted.md).\n"
                )
            }
        )
        self.assertEqual(self.findings(), [])

    def test_another_record_may_not_cite_the_deleted_record(self) -> None:
        """A record that is not the successor gets the finding."""
        self.write(
            {"docs/decisions/0001-first.md": record_text("It builds on ADR 0005.\n")}
        )
        (finding,) = self.findings()
        self.assertTrue(finding.startswith("docs/decisions/0001-first.md:9: "), finding)

    def test_successor_may_not_cite_a_withdrawn_record(self) -> None:
        """A withdrawn record has no successor, so no file may cite it."""
        self.write({"docs/decisions/0002-second.md": record_text("See ADR 0006.\n")})
        self.assertEqual(len(self.findings()), 1)


class RangeCitationTest(TreeTestCase):
    """A range resolves each of its numbers as a single citation does."""

    def setUp(self) -> None:
        """Write records 0001, 0002 and 0004, and a ledger with 0003 and 0005.

        Record 0003 was replaced by 0004. Record 0005 was withdrawn.
        """
        super().setUp()
        self.write(
            {
                "docs/decisions/0001-first.md": record_text(),
                "docs/decisions/0002-second.md": record_text(),
                "docs/decisions/0004-fourth.md": record_text(),
                LEDGER: ledger_entry("0003", "0004") + ledger_entry("0005"),
            }
        )

    def test_range_over_a_deleted_record_is_a_finding_on_a_page(self) -> None:
        """The deleted number inside the range gets its own finding."""
        self.write({"notes.md": "Intro.\n\nSee ADRs 0001 to 0004.\n"})
        self.assertEqual(
            self.findings(),
            [
                "notes.md:3: decision record 0003 was deleted into the ledger: "
                "cite its successor, ADR 0004"
            ],
        )

    def test_dash_range_over_a_deleted_record_is_a_finding_too(self) -> None:
        """A hyphen and an en dash expand as `to` does."""
        self.write({"a.md": "ADRs 0001-0004\n", "b.md": "ADRs 0001–0004\n"})
        self.assertEqual(
            [finding.split(": ")[0] for finding in self.findings()],
            ["a.md:1", "b.md:1"],
        )

    def test_successor_may_cite_a_range_over_the_records_it_replaced(self) -> None:
        """A range gives no finding where a single citation of 0003 gives none."""
        self.write(
            {
                "docs/decisions/0004-fourth.md": record_text(
                    "It replaces ADR 0003, and builds on ADRs 0001 to 0003.\n"
                )
            }
        )
        self.assertEqual(self.findings(), [])

    def test_successor_may_not_cite_a_withdrawn_record_in_a_range(self) -> None:
        """Only the numbers that the successor replaced are allowed."""
        self.write(
            {"docs/decisions/0004-fourth.md": record_text("ADRs 0003 to 0005\n")}
        )
        self.assertEqual(
            self.findings(),
            [
                "docs/decisions/0004-fourth.md:9: decision record 0005 was "
                "withdrawn into the ledger: remove the citation"
            ],
        )

    def test_missing_numbers_of_a_range_are_one_finding(self) -> None:
        """The numbers that are no record and no ledger entry share one finding."""
        self.write({"notes.md": "ADRs 0004 to 0007\n"})
        self.assertEqual(
            self.findings(),
            [
                "notes.md:1: decision record 0005 was withdrawn into the ledger: "
                "remove the citation",
                "notes.md:1: decision records 0006 to 0007 do not exist",
            ],
        )

    def test_one_missing_number_of_a_range_keeps_the_single_message(self) -> None:
        """A range with one number that does not exist words it as a single citation."""
        self.write({"notes.md": "ADRs 0001 to 0002 and 0004 to 0006\n"})
        self.assertEqual(
            self.findings(),
            [
                "notes.md:1: decision record 0005 was withdrawn into the ledger: "
                "remove the citation",
                "notes.md:1: decision record 0006 does not exist",
            ],
        )

    def test_wide_missing_range_is_one_line(self) -> None:
        """`0100 to 0300` names 201 numbers and gives one finding."""
        self.write({"notes.md": "ADRs 0100 to 0300\n"})
        self.assertEqual(
            self.findings(), ["notes.md:1: decision records 0100 to 0300 do not exist"]
        )

    def test_runs_of_missing_numbers_are_collapsed(self) -> None:
        """Records 0008 and 0010 split the missing numbers into three runs."""
        self.write(
            {
                "docs/decisions/0008-eighth.md": record_text(),
                "docs/decisions/0010-tenth.md": record_text(),
                "notes.md": "ADRs 0006 to 0012\n",
            }
        )
        self.assertEqual(
            self.findings(),
            [
                "notes.md:1: decision records 0006 to 0007, 0009 and 0011 to 0012 "
                "do not exist"
            ],
        )

    def test_each_range_of_a_line_has_its_own_finding(self) -> None:
        """Two ranges and a number on one line are three citations."""
        self.write({"notes.md": "ADRs 0100, 0200 to 0300 and 0400 to 0500\n"})
        self.assertEqual(
            self.findings(),
            [
                "notes.md:1: decision record 0100 does not exist",
                "notes.md:1: decision records 0200 to 0300 do not exist",
                "notes.md:1: decision records 0400 to 0500 do not exist",
            ],
        )

    def test_chain_of_ranges_is_one_finding(self) -> None:
        """`0100 to 0102 to 0104` names the numbers 0100 to 0104 once."""
        self.write({"notes.md": "ADRs 0100 to 0102 to 0104\n"})
        self.assertEqual(
            self.findings(), ["notes.md:1: decision records 0100 to 0104 do not exist"]
        )

    def test_range_over_ledger_numbers_and_gaps_gives_separate_findings(self) -> None:
        """Deleted, withdrawn and missing numbers each get the advice that fits."""
        self.write({"notes.md": "ADRs 0001 to 0009\n"})
        self.assertEqual(
            self.findings(),
            [
                "notes.md:1: decision record 0003 was deleted into the ledger: "
                "cite its successor, ADR 0004",
                "notes.md:1: decision record 0005 was withdrawn into the ledger: "
                "remove the citation",
                "notes.md:1: decision records 0006 to 0009 do not exist",
            ],
        )

    def test_successor_gets_no_finding_for_the_numbers_it_replaced(self) -> None:
        """From 0004, the deleted 0003 is allowed; the other numbers are not."""
        self.write(
            {"docs/decisions/0004-fourth.md": record_text("ADRs 0001 to 0009\n")}
        )
        self.assertEqual(
            self.findings(),
            [
                "docs/decisions/0004-fourth.md:9: decision record 0005 was "
                "withdrawn into the ledger: remove the citation",
                "docs/decisions/0004-fourth.md:9: "
                "decision records 0006 to 0009 do not exist",
            ],
        )

    def test_spec_range_needs_every_spec_file(self) -> None:
        """A spec between the ends needs its own file."""
        self.write({"docs/specs/0001-a.md": "# A\n", "docs/specs/0003-c.md": "# C\n"})
        self.write({"notes.md": "specs 0001 to 0003\n"})
        self.assertEqual(
            self.findings(), ["notes.md:1: spec 0002 has no file docs/specs/0002-*.md"]
        )

    def test_missing_specs_of_a_range_are_one_finding(self) -> None:
        """Several specs without a file share one finding, with runs collapsed."""
        self.write({"docs/specs/0001-a.md": "# A\n", "docs/specs/0050-x.md": "# X\n"})
        self.write({"notes.md": "specs 0001 to 0100\n"})
        self.assertEqual(
            self.findings(),
            [
                "notes.md:1: specs 0002 to 0049 and 0051 to 0100 "
                "have no file docs/specs/NNNN-*.md"
            ],
        )

    def test_reversed_range_is_a_finding(self) -> None:
        """A range that runs down says how to write it."""
        self.write({"notes.md": "Intro.\n\nADRs 0004 to 0001\n"})
        self.assertEqual(
            self.findings(),
            [
                "notes.md:3: a range must run from the lower number to the higher, "
                "not 0004 to 0001"
            ],
        )

    def test_equal_ends_are_one_citation(self) -> None:
        """`0001 to 0001` is record 0001 and nothing else."""
        self.write({"notes.md": "ADRs 0001 to 0001 and 0007 to 0007\n"})
        self.assertEqual(
            self.findings(), ["notes.md:1: decision record 0007 does not exist"]
        )

    def test_second_widest_range_in_one_file_is_reported_not_expanded(self) -> None:
        """The budget of a file gives one finding for a range that does not fit."""
        self.write({"notes.md": "ADRs 0001 to 9999\n\nADRs 0001 to 9999\n"})
        findings = self.findings()
        # The first line: the deleted 0003, the withdrawn 0005, and one finding
        # for 0006 to 9999. The third line: the oversized range, and its end
        # 9999, which is cited alone.
        self.assertEqual(len(findings), 3 + 2)
        self.assertIn(
            "notes.md:3: the ranges of a file may name 10000 numbers in all: "
            "the range 0001 to 9999 is not expanded",
            findings,
        )
        self.assertIn("notes.md:3: decision record 9999 does not exist", findings)

    def test_widest_range_has_one_finding_for_the_numbers_that_do_not_exist(
        self,
    ) -> None:
        """`0001 to 9999` is three findings: 0003, 0005 and the rest in one."""
        self.write({"notes.md": "ADRs 0001 to 9999\n"})
        self.assertEqual(
            self.findings(),
            [
                "notes.md:1: decision record 0003 was deleted into the ledger: "
                "cite its successor, ADR 0004",
                "notes.md:1: decision record 0005 was withdrawn into the ledger: "
                "remove the citation",
                "notes.md:1: decision records 0006 to 9999 do not exist",
            ],
        )

    def test_plural_keyword_with_a_year_is_one_grouped_finding(self) -> None:
        """`ADRs 0001-2026 here.` is a range, so the missing numbers share a line."""
        self.write({"notes.md": "ADRs 0001-2026 here.\n"})
        self.assertEqual(
            self.findings(),
            [
                "notes.md:1: decision record 0003 was deleted into the ledger: "
                "cite its successor, ADR 0004",
                "notes.md:1: decision record 0005 was withdrawn into the ledger: "
                "remove the citation",
                "notes.md:1: decision records 0006 to 2026 do not exist",
            ],
        )

    def test_singular_keyword_with_a_year_cites_one_record(self) -> None:
        """`ADR 0001-2026 plan` names record 0001, which exists: no finding."""
        self.write({"notes.md": "ADR 0001-2026 plan and ADR-0002-0003.\n"})
        self.assertEqual(self.findings(), [])


class SpecAndPathCitationTest(TreeTestCase):
    """A citation of a spec or a page resolves to a file."""

    def test_spec_resolves_to_its_file(self) -> None:
        """`spec 0006` needs a file `docs/specs/0006-<slug>.md`."""
        self.write({"docs/specs/0006-design.md": "# Design\n", "a.py": "# spec 0006\n"})
        self.assertEqual(self.findings(), [])

    def test_missing_spec_is_reported_in_code(self) -> None:
        """A code comment that cites a spec without a file is a finding."""
        self.write({"src/a.py": "x = 1\n# see spec 0006 A3\n"})
        self.assertEqual(
            self.findings(),
            ["src/a.py:2: spec 0006 has no file docs/specs/0006-*.md"],
        )

    def test_existing_and_missing_documentation_paths(self) -> None:
        """A `docs/` path in any file must exist relative to the root."""
        self.write(
            {
                "docs/guide.md": "# Guide\n",
                "src/a.py": '# docs/guide.md\nPATH = "docs/gone.md"\n',
            }
        )
        self.assertEqual(
            self.findings(), ["src/a.py:2: the file docs/gone.md does not exist"]
        )

    def test_path_in_another_letter_case_does_not_exist(self) -> None:
        """A case-insensitive disk must not make `docs/Guide.md` pass."""
        self.write({"docs/guide.md": "# Guide\n", "notes.md": "See docs/Guide.md.\n"})
        expected = ["notes.md:1: the file docs/Guide.md does not exist"]
        self.assertEqual(self.findings(), expected)
        self.git_init()
        self.assertEqual(self.findings(), expected)

    def test_page_that_git_ignores_does_not_exist(self) -> None:
        """A page that `.gitignore` hides is not in the repository, nor in CI."""
        self.git_init()
        self.write(
            {
                ".gitignore": "draft.md\n",
                "docs/draft.md": "# Draft\n",
                "notes.md": "See docs/draft.md.\n",
            }
        )
        self.assertEqual(
            self.findings(), ["notes.md:1: the file docs/draft.md does not exist"]
        )

    def test_untracked_page_that_is_not_ignored_exists(self) -> None:
        """The listing includes new files, so a page not yet added resolves.

        A flake source holds only tracked files, so the same page fails there.
        """
        self.git_init()
        self.write({"docs/new.md": "# New\n", "notes.md": "See docs/new.md.\n"})
        self.assertEqual(self.findings(), [])

    def test_page_that_the_scan_skips_still_exists(self) -> None:
        """A changelog and an excluded page are not scanned, but links resolve."""
        self.write(
            {
                "docs/CHANGELOG.md": "# Changes\n",
                "docs/private/a.md": "# A\n",
                "notes.md": "See docs/CHANGELOG.md and docs/private/a.md.\n",
            }
        )
        self.assertEqual(self.findings(exclude=["docs/private"]), [])

    def test_relative_links_are_left_to_the_link_checker(self) -> None:
        """A path that does not start at `docs/` is not checked."""
        self.write({"docs/a.md": "[x](../reference/gone.md) [y](./gone.md)\n"})
        self.assertEqual(self.findings(), [])

    def test_foreign_citations_are_skipped_end_to_end(self) -> None:
        """A citation that another repository qualifies is not checked here."""
        self.write(
            {
                "notes.md": "In sealambda/infra ADR 0042 holds, as "
                "[its ADR 0043](https://github.com/sealambda/infra/blob/main/"
                "docs/adr/0043-x.md) and https://github.com/sealambda/infra/blob/"
                "main/docs/decisions/0044-y.md say.\n"
            }
        )
        self.assertEqual(self.findings(), [])

    def test_hub_text_that_names_another_repository_is_still_checked(self) -> None:
        """Naming a repository in a sentence does not excuse its other citations."""
        self.write(
            {
                "notes.md": "The sealambda/infra repository differs, "
                "but ADR 0042 is ours.\n"
            }
        )
        self.assertEqual(
            self.findings(), ["notes.md:1: decision record 0042 does not exist"]
        )

    def test_placeholders_in_templates_are_not_citations(self) -> None:
        """The placeholder NNNN in prose and templates raises no finding."""
        self.write(
            {
                "templates/t.md": "Name it docs/decisions/NNNN-slug.md, cite ADR NNNN "
                "or spec NNNN; see docs/specs/NNNN-slug.md.\n"
            }
        )
        self.assertEqual(self.findings(), [])

    def test_all_findings_come_in_one_sorted_run(self) -> None:
        """Findings of different checks are all reported, sorted by path."""
        self.write(
            {
                "docs/decisions/notes.txt": "x\n",
                "z.md": "ADR 0042\n",
                "a.md": "spec 0001\n",
            }
        )
        paths = [finding.split(":")[0] for finding in self.findings()]
        self.assertEqual(paths, ["a.md", "docs/decisions/notes.txt", "z.md"])


class ScanScopeTest(TreeTestCase):
    """Which files the citation scan reads."""

    def test_excluded_prefix_is_skipped_by_whole_components(self) -> None:
        """`fixtures` skips `fixtures/a.md`, not `fixtures-extra/a.md`."""
        self.write({"fixtures/a.md": "ADR 0042\n", "fixtures-extra/a.md": "ADR 0043\n"})
        self.assertEqual(
            self.findings(exclude=["fixtures"]),
            ["fixtures-extra/a.md:1: decision record 0043 does not exist"],
        )

    def test_exclude_may_name_a_single_file(self) -> None:
        """An exclude can be one file."""
        self.write({"a.md": "ADR 0042\n", "b.md": "ADR 0043\n"})
        self.assertEqual(
            self.findings(exclude=["./a.md"]),
            ["b.md:1: decision record 0043 does not exist"],
        )

    def test_skipped_files_are_not_scanned(self) -> None:
        """Lock files, changelogs, `.git`, binaries and big files are skipped."""
        self.without_git()
        text = "ADR 0042\n"
        self.write(
            {
                "flake.lock": text,
                "package-lock.json": text,
                "pnpm-lock.yaml": text,
                "mix.lock": text,
                "CHANGELOG.md": text,
                "CHANGELOG-2025.md": text,
                ".git/config": text,
                "big.txt": text + "x" * (1024 * 1024),
            }
        )
        (self.root / "bin.dat").write_bytes(b"ADR 0042\n\0")
        (self.root / "latin.txt").write_bytes(b"ADR 0042 \xe9\n")
        self.assertEqual(self.findings(), [])

    def test_file_at_the_size_limit_is_scanned(self) -> None:
        """A file of exactly 1 MiB is still read."""
        text = "ADR 0042\n"
        self.write({"limit.txt": text + "x" * (1024 * 1024 - len(text))})
        self.assertEqual(len(self.findings()), 1)

    def test_code_and_configuration_files_are_scanned(self) -> None:
        """Any text file is scanned, whatever its suffix."""
        self.write(
            {
                "a.py": "# ADR 0042\n",
                "b.nix": "# ADR 0043\n",
                "Makefile": "# ADR 0044\n",
                ".github/c.yml": "# ADR 0045\n",
            }
        )
        self.assertEqual(len(self.findings()), 4)

    def test_symbolic_links_are_not_followed(self) -> None:
        """A link to a file with a bad citation is not read twice."""
        self.write({"real.md": "fine\n"})
        (self.root / "link.md").symlink_to(self.root / "real.md")
        self.assertEqual(self.findings(), [])

    def test_ignored_files_of_a_work_tree_are_not_scanned(self) -> None:
        """In a Git work tree, `.gitignore` keeps `.venv` and the like out."""
        self.git_init()
        self.write(
            {
                ".gitignore": ".venv/\nnode_modules/\n",
                ".venv/lib/a.md": "ADR 0042\n",
                "node_modules/pkg/README.md": "ADR 0043\n",
                "kept.md": "ADR 0044\n",
            }
        )
        self.assertEqual(
            self.findings(), ["kept.md:1: decision record 0044 does not exist"]
        )

    def test_ignore_file_patterns_are_not_citations(self) -> None:
        """A `.gitignore` line such as `docs/secret.md` is a pattern, not a page."""
        self.git_init()
        self.write(
            {
                ".gitignore": "docs/secret.md\n# see ADR 0042\n",
                "sub/.dockerignore": "docs/secret.md\n",
                "ignore.md": "docs/secret.md\n",
                "CODEOWNERS": "docs/gone.md @owner\n",
            }
        )
        self.assertEqual(
            self.findings(),
            [
                "CODEOWNERS:1: the file docs/gone.md does not exist",
                "ignore.md:1: the file docs/secret.md does not exist",
            ],
        )

    def test_ignore_file_is_skipped_without_git_too(self) -> None:
        """The walk of a Nix build source, which has no `.git`, skips it as well."""
        self.write({".gitignore": "docs/secret.md\n", "sub/.npmignore": "ADR 0042\n"})
        self.assertEqual(self.findings(), [])

    def test_untracked_and_tracked_files_of_a_work_tree_are_scanned(self) -> None:
        """A file that is not ignored counts, whether `git add` saw it or not."""
        self.git_init()
        self.write({"tracked.md": "ADR 0042\n", "untracked.md": "ADR 0043\n"})
        self.git("add", "tracked.md")
        self.assertEqual(len(self.findings()), 2)


if __name__ == "__main__":
    unittest.main()
