"""Tests for the file walker helpers: excludes, skipped names and text reading."""

import unittest

from decisions.walk import (
    MAX_FILE_BYTES,
    is_excluded,
    is_skipped_name,
    iter_candidate_files,
    list_files,
    parse_exclude,
    read_text_file,
)
from support import TreeTestCase, posix


class ExcludeTest(unittest.TestCase):
    """The `exclude` prefixes."""

    def test_parse_normalizes_the_prefix(self) -> None:
        """A leading `./` and a trailing slash are dropped."""
        self.assertEqual(parse_exclude("./a/b/"), posix("a/b"))

    def test_parse_rejects_paths_outside_the_root(self) -> None:
        """Empty, current-folder, absolute and `..` prefixes are errors."""
        for bad in ("", ".", "/abs", "../x", "a/../../x"):
            with self.subTest(prefix=bad), self.assertRaises(ValueError):
                parse_exclude(bad)

    def test_matching_uses_whole_components(self) -> None:
        """A prefix matches itself and what is below it, not a longer name."""
        excludes = [posix("a/b")]
        self.assertTrue(is_excluded(posix("a/b"), excludes))
        self.assertTrue(is_excluded(posix("a/b/c/d.py"), excludes))
        self.assertFalse(is_excluded(posix("a/bc.py"), excludes))
        self.assertFalse(is_excluded(posix("a"), excludes))
        self.assertFalse(is_excluded(posix("x/a/b"), excludes))


class SkippedNameTest(unittest.TestCase):
    """The names of lock files, changelogs and ignore files."""

    def test_skipped_names(self) -> None:
        """Lock files and changelogs are skipped."""
        for name in (
            "flake.lock",
            "mix.lock",
            "Cargo.lock",
            "package-lock.json",
            "pnpm-lock.yaml",
            "npm-shrinkwrap.json",
            "CHANGELOG.md",
            "CHANGELOG-v2.md",
        ):
            with self.subTest(name=name):
                self.assertTrue(is_skipped_name(name))

    def test_ignore_files_are_skipped(self) -> None:
        """A dotfile whose name ends in `ignore` lists patterns, not citations."""
        for name in (
            ".gitignore",
            ".dockerignore",
            ".prettierignore",
            ".npmignore",
            ".eslintignore",
            ".markdownlintignore",
            ".helmignore",
            ".vscodeignore",
            ".ignore",
        ):
            with self.subTest(name=name):
                self.assertTrue(is_skipped_name(name))

    def test_other_names_are_not_skipped(self) -> None:
        """A name that only resembles a lock file or a changelog is read."""
        for name in ("lockfile.md", "changelog.md", "CHANGELOG.txt", "locks.py"):
            with self.subTest(name=name):
                self.assertFalse(is_skipped_name(name))

    def test_names_that_only_resemble_an_ignore_file_are_not_skipped(self) -> None:
        """The rule needs the dot first, a lowercase ending and no suffix.

        `CODEOWNERS` and `.gitattributes` name real paths, so they are read.
        """
        for name in (
            "ignore.md",
            ".ignore.md",
            "x.gitignore",
            "gitignore",
            ".GITIGNORE",
            ".gitignore.bak",
            ".git-blame-ignore-revs",
            "CODEOWNERS",
            ".gitattributes",
        ):
            with self.subTest(name=name):
                self.assertFalse(is_skipped_name(name))


class WalkTest(TreeTestCase):
    """The walk and the text test."""

    def candidates(self, *excludes: str) -> list[str]:
        """Return the candidate files of the root as POSIX path text."""
        return [
            path.as_posix()
            for path in iter_candidate_files(
                self.root,
                list_files(self.root),
                [posix(prefix) for prefix in excludes],
            )
        ]

    def test_walk_is_sorted_and_prunes_git_and_excludes(self) -> None:
        """Without Git, files come in a stable order, minus `.git` and excludes."""
        self.without_git()
        self.write(
            {
                "b.md": "",
                "a/z.md": "",
                "a/y.md": "",
                ".git/HEAD": "",
                "skip/deep/x.md": "",
                "flake.lock": "",
            }
        )
        self.assertEqual(self.candidates("skip"), ["b.md", "a/y.md", "a/z.md"])

    def test_tree_without_a_git_entry_is_walked_even_when_git_exists(self) -> None:
        """The Nix sandbox has no `.git`: the files are all the files."""
        self.write({"b.md": "", ".venv/x.md": "", "a/y.md": ""})
        self.assertEqual(self.candidates(), ["b.md", ".venv/x.md", "a/y.md"])

    def test_work_tree_lists_the_files_that_git_lists(self) -> None:
        """Tracked and untracked files stay; ignored, excluded and skipped go."""
        self.git_init()
        self.write(
            {
                ".gitignore": ".venv/\n",
                "tracked.md": "",
                "untracked.md": "",
                "sub/deep/x.md": "",
                "sub/a.md": "",
                ".venv/lib/y.md": "",
                "skip/z.md": "",
                "flake.lock": "",
            }
        )
        self.git("add", "tracked.md")
        self.assertEqual(
            self.candidates("skip"),
            ["tracked.md", "untracked.md", "sub/a.md", "sub/deep/x.md"],
        )

    def test_ignore_file_in_any_folder_is_not_a_candidate(self) -> None:
        """A `.gitignore` below the root is skipped; a look-alike is read."""
        self.write(
            {
                ".gitignore": "docs/secret.md\n",
                "sub/.gitignore": "docs/secret.md\n",
                "sub/.dockerignore": "docs/secret.md\n",
                "sub/ignore.md": "docs/secret.md\n",
                "sub/.ignore.md": "docs/secret.md\n",
                "sub/CODEOWNERS": "docs/secret.md @owner\n",
            }
        )
        self.assertEqual(
            self.candidates(), ["sub/.ignore.md", "sub/CODEOWNERS", "sub/ignore.md"]
        )

    def test_work_tree_skips_a_tracked_file_that_was_deleted(self) -> None:
        """`git ls-files` still lists it, but there is no file to read."""
        self.git_init()
        self.write({"gone.md": "", "here.md": ""})
        self.git("add", "gone.md", "here.md")
        (self.root / "gone.md").unlink()
        self.assertEqual(self.candidates(), ["here.md"])

    def test_work_tree_skips_a_symbolic_link(self) -> None:
        """A link that Git tracks is not followed, as in the plain walk."""
        self.git_init()
        self.write({"real.md": ""})
        (self.root / "link.md").symlink_to(self.root / "real.md")
        self.assertEqual(self.candidates(), ["real.md"])

    def test_failing_git_is_an_error_not_a_silent_walk(self) -> None:
        """A `.git` that Git cannot use must not hide files from the check."""
        (self.root / ".git").write_text("gitdir: /nonexistent\n", encoding="utf-8")
        with self.assertRaisesRegex(OSError, "git ls-files failed"):
            self.candidates()

    def test_listing_keeps_what_the_candidate_filter_drops(self) -> None:
        """The raw listing names lock files, changelogs and excluded paths."""
        self.write({"b.md": "", "a/CHANGELOG.md": "", "a/x.lock": "", "skip/y.md": ""})
        self.assertEqual(
            [path.as_posix() for path in list_files(self.root)],
            ["b.md", "a/CHANGELOG.md", "a/x.lock", "skip/y.md"],
        )

    def test_listing_of_a_work_tree_leaves_out_ignored_and_deleted_files(self) -> None:
        """Git decides what exists: untracked files stay, ignored ones go."""
        self.git_init()
        self.write(
            {
                ".gitignore": "ignored.md\n",
                "kept.md": "",
                "ignored.md": "",
                "gone.md": "",
            }
        )
        self.git("add", "gone.md")
        (self.root / "gone.md").unlink()
        self.assertEqual(
            [path.as_posix() for path in list_files(self.root)],
            [".gitignore", "kept.md"],
        )

    def test_read_text_file_returns_text(self) -> None:
        """A UTF-8 file is returned as text."""
        self.write({"a.txt": "café\n"})
        self.assertEqual(read_text_file(self.root / "a.txt"), "café\n")

    def test_read_text_file_rejects_binary_oversize_and_invalid_utf8(self) -> None:
        """A NUL byte, more than 1 MiB and invalid UTF-8 all give `None`."""
        (self.root / "nul.bin").write_bytes(b"text\0text")
        (self.root / "latin.txt").write_bytes(b"text \xe9")
        (self.root / "big.txt").write_bytes(b"x" * (MAX_FILE_BYTES + 1))
        for name in ("nul.bin", "latin.txt", "big.txt"):
            with self.subTest(name=name):
                self.assertIsNone(read_text_file(self.root / name))

    def test_nul_byte_after_the_first_block_does_not_make_a_binary(self) -> None:
        """Only the first 8 KiB is searched for a NUL byte."""
        (self.root / "late.txt").write_bytes(b"x" * 9000 + b"\0")
        self.assertIsNotNone(read_text_file(self.root / "late.txt"))


if __name__ == "__main__":
    unittest.main()
