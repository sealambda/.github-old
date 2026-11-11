"""Tests of the classification of changed paths.

The expectations come from who reads each file, not from the list of patterns
in `release.paths`. A consumer reads the hub through its flake, its reusable
workflow, the Renovate preset and the default community files that GitHub
applies to every repository of the organization (`docs/reference/hub-releases.md`
gives the reasons). Each path below is a file of the hub, and each value names
the reader, or says that nobody reads the file.
"""

import unittest

from release.paths import is_rule_free, rules_changed

# Files that no consumer reads.
UNREAD_BY_CONSUMERS: dict[str, str] = {
    "docs/reference/hub-releases.md": "a consumer's docs check reads its own docs",
    "docs/how-to/release-the-hub.md": "a consumer's docs check reads its own docs",
    "docs/decisions/0001-hub-as-single-source-of-standards.md": "hub record",
    "README.md": "GitHub shows it for this repository only, it is not inherited",
    "nix/tests/release/test_release_tags.py": "only the hub's own test checks",
    "nix/tests/check-docs.sh": "only the hub's own test checks",
    "vale/Sealambda/CurrentState.test.yml": "the flake leaves test cases out",
    "LICENSE": "GitHub has no default license file",
    "LICENSES/MPL-2.0.txt": "only the hub's licenses check",
    "REUSE.toml": "only the hub's licenses check",
    ".github/CODEOWNERS": "GitHub reads it per repository, it is not inherited",
    ".github/workflows/ci.yml": "the hub's own CI, it has no workflow_call trigger",
    ".gitignore": "only the hub's own work tree",
}

# The folder that GitHub reads default community files from, next to the root
# and `.github/`. The hub holds no such file there. The tests build the names
# from this value, so that no test text cites a page that doesn't exist.
COMMUNITY_FOLDER = "docs"

# The folders below `docs/` that the hub's layout holds.
HUB_DOCS_FOLDERS: tuple[str, ...] = ("how-to", "reference", "decisions", "specs")

# Files that GitHub applies to every repository of the organization.
INHERITED_COMMUNITY_FILES: list[str] = [
    "CONTRIBUTING.md",
    "SECURITY.md",
    "SUPPORT.md",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/change_request.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    # GitHub also reads default community files from `docs/`, and it supports
    # more names than the hub holds today.
    f"{COMMUNITY_FOLDER}/SECURITY.md",
    f"{COMMUNITY_FOLDER}/CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    ".github/FUNDING.yml",
]

# Files that the flake, a workflow or Renovate of a consumer reads.
READ_BY_CONSUMERS: dict[str, str] = {
    "flake.nix": "the flake of every consumer",
    "flake.lock": "the pins of the flake",
    "treefmt.nix": "imported by lib.mkTreefmt",
    "config/vale.ini": "copied by sync-config",
    "config/lychee.toml": "copied by sync-config",
    "vale/Sealambda/CurrentState.yml": "the Vale style of mkDocsCheck",
    "nix/scripts/check-docs.sh": "run by mkDocsCheck",
    "nix/scripts/decisions/check.py": "run by mkDecisionsCheck",
    "schemas/decision-record.schema.json": "read by the decisions tool",
    ".github/workflows/secrets.yml": "the reusable workflow",
    "default.json": "the Renovate preset",
    "versions.json": "the pinned version of Nix",
    "templates/adr.md.tmpl": "copied by people, and read by the versions check",
}


class RuleFreePathTest(unittest.TestCase):
    """A path is rule-free only when no consumer reads it."""

    def test_files_that_no_consumer_reads_are_rule_free(self) -> None:
        """Each file with no reader leaves the rules alone."""
        for path, reason in UNREAD_BY_CONSUMERS.items():
            with self.subTest(path=path, reason=reason):
                self.assertTrue(is_rule_free(path))

    def test_community_files_that_github_inherits_are_rules(self) -> None:
        """Every repository of the organization inherits these, so they are rules."""
        for path in INHERITED_COMMUNITY_FILES:
            with self.subTest(path=path):
                self.assertFalse(is_rule_free(path))

    def test_files_that_a_consumer_reads_are_rules(self) -> None:
        """A file that a flake, a workflow or Renovate reads is a rule."""
        for path, reader in READ_BY_CONSUMERS.items():
            with self.subTest(path=path, reader=reader):
                self.assertFalse(is_rule_free(path))

    def test_markdown_is_not_rule_free_by_its_extension(self) -> None:
        """Only the root README and the documentation folders are free.

        A Markdown file elsewhere can be a community file or a template that a
        person copies, so the extension proves nothing.
        """
        for path in ("notes.md", "templates/README.md"):
            with self.subTest(path=path):
                self.assertFalse(is_rule_free(path))

    def test_only_the_root_readme_is_free(self) -> None:
        """A README in a folder is not the file that GitHub shows for the hub."""
        self.assertFalse(is_rule_free("config/README.md"))

    def test_files_directly_in_docs_are_rules(self) -> None:
        """GitHub reads default community files from `docs/` itself."""
        paths = [f"{COMMUNITY_FOLDER}/{name}" for name in ("page.txt", "SUPPORT.md")]
        for path in [*paths, COMMUNITY_FOLDER]:
            with self.subTest(path=path):
                self.assertFalse(is_rule_free(path))

    def test_the_folders_of_the_hub_layout_are_free(self) -> None:
        """The hub's pages, records and specs sit in four named folders.

        `CONTRIBUTING.md` names `docs/specs/`, and the pages and records are in
        the other three. A consumer reads none of them.
        """
        for folder in HUB_DOCS_FOLDERS:
            for path in (f"docs/{folder}/page.md", f"docs/{folder}/sub/page.md"):
                with self.subTest(path=path):
                    self.assertTrue(is_rule_free(path))

    def test_other_folders_below_docs_are_rules(self) -> None:
        """A folder that the hub doesn't name stays a rule.

        GitHub reads the pull request template from `docs/` and from
        `docs/PULL_REQUEST_TEMPLATE/`. It documents issue templates and
        discussion category forms in `.github/` only, but the hub treats every
        unnamed folder alike, so an unknown folder never hides a community file.
        """
        folders = (
            "PULL_REQUEST_TEMPLATE",
            "ISSUE_TEMPLATE",
            "DISCUSSION_TEMPLATE",
            "tutorials",
            "explanation",
            "other",
        )
        for folder in folders:
            path = f"{COMMUNITY_FOLDER}/{folder}/file.md"
            with self.subTest(path=path):
                self.assertFalse(is_rule_free(path))

    def test_a_pull_request_template_in_docs_is_a_rule(self) -> None:
        """GitHub applies a pull request template of `docs/` to every repository."""
        self.assertFalse(is_rule_free(f"{COMMUNITY_FOLDER}/pull_request_template.md"))

    def test_near_misses_of_free_names_are_rules(self) -> None:
        """A name that only resembles a free name is a rule."""
        for path in (
            "nix/tests",
            "docsx/guide/page.md",
            f"{COMMUNITY_FOLDER}/how-tos/page.md",
            f"{COMMUNITY_FOLDER}/specs-old/page.md",
            "services/api/docs/specs/page.md",
            "src/LICENSE",
            "LICENSE.md",
            ".gitignored",
            "x.md.bak",
            "vale/Sealambda/CurrentState.testing.yml",
            ".github/workflows/ci.yml.bak",
        ):
            with self.subTest(path=path):
                self.assertFalse(is_rule_free(path))

    def test_a_path_that_nobody_classified_is_a_rule(self) -> None:
        """The default for an unknown path is the safe answer."""
        self.assertFalse(is_rule_free("unknown/new/path.bin"))


class RulesChangedTest(unittest.TestCase):
    """The answer is `yes` unless every path is rule-free."""

    def test_only_unread_paths_leave_the_rules_alone(self) -> None:
        """A change of a page, a test and the license gives `False`."""
        self.assertFalse(
            rules_changed(
                [
                    "docs/reference/hub-releases.md",
                    "nix/tests/release/test_release_plan.py",
                    "LICENSE",
                ]
            )
        )

    def test_one_rule_path_among_many_changes_the_rules(self) -> None:
        """A mixed change gives `True`."""
        self.assertTrue(
            rules_changed(["docs/reference/hub-releases.md", "flake.nix", "README.md"])
        )

    def test_a_changed_community_file_changes_the_rules(self) -> None:
        """A change to `SECURITY.md` alone reaches every repository."""
        self.assertTrue(rules_changed(["SECURITY.md"]))

    def test_unknown_path_changes_the_rules(self) -> None:
        """A path that nobody classified gives `True`: the default is safe."""
        self.assertTrue(rules_changed(["README.md", "brand-new-dir/file"]))

    def test_no_path_means_nothing_changed(self) -> None:
        """An empty set of paths gives `False`."""
        self.assertFalse(rules_changed([]))
