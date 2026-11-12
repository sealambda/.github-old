"""Tests of the selection and the reading of workflow and action files."""

import tempfile
import unittest
from pathlib import Path, PurePosixPath

from decisions.workflow_files import (
    ActionsFile,
    is_action_path,
    is_workflow_path,
    read_actions_files,
)


class PathSelectionTest(unittest.TestCase):
    """Which paths are workflows and which are actions."""

    def test_workflows_in_a_dot_github_folder_are_selected(self) -> None:
        """A `.yml` or `.yaml` file directly in `.github/workflows` is a workflow."""
        for path in (
            ".github/workflows/ci.yml",
            ".github/workflows/ci.yaml",
            "templates/x/.github/workflows/ci.yml",
        ):
            with self.subTest(path=path):
                self.assertTrue(is_workflow_path(PurePosixPath(path)))

    def test_starter_workflows_at_the_root_are_selected(self) -> None:
        """A YAML file directly in `workflow-templates` is a starter workflow."""
        self.assertTrue(is_workflow_path(PurePosixPath("workflow-templates/a.yml")))

    def test_other_paths_are_not_workflows(self) -> None:
        """Subfolders, other suffixes, other folders and a nested template folder."""
        for path in (
            ".github/workflows/sub/ci.yml",
            ".github/workflows/ci.json",
            ".github/workflows/ci.properties.json",
            "workflows/ci.yml",
            "docs/workflows/ci.yml",
            "workflow-templates/sub/a.yml",
            "nested/workflow-templates/a.yml",
            "ci.yml",
        ):
            with self.subTest(path=path):
                self.assertFalse(is_workflow_path(PurePosixPath(path)))

    def test_action_files_are_selected_by_name_anywhere(self) -> None:
        """`action.yml` and `action.yaml` are actions in any folder."""
        for path in ("action.yml", "a/b/action.yaml"):
            with self.subTest(path=path):
                self.assertTrue(is_action_path(PurePosixPath(path)))
        self.assertFalse(is_action_path(PurePosixPath("actions.yml")))


class ReadActionsFilesTest(unittest.TestCase):
    """The reading of the selected files."""

    def setUp(self) -> None:
        """Create the directory of the test tree and remove it after the test."""
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

    def read(self, *, include_actions: bool) -> tuple[list[str], list[str]]:
        """Return the paths that were read and the lines of the findings."""
        files, findings = read_actions_files(self.root, include_actions=include_actions)
        return [file.path for file in files], [f.format() for f in findings]

    def test_actions_are_read_only_on_request(self) -> None:
        """`include_actions` decides whether `action.yml` is read."""
        self.write(".github/workflows/ci.yml", "name: a\n")
        self.write("tool/action.yml", "name: b\n")
        self.assertEqual(
            self.read(include_actions=False)[0], [".github/workflows/ci.yml"]
        )
        self.assertEqual(
            sorted(self.read(include_actions=True)[0]),
            [".github/workflows/ci.yml", "tool/action.yml"],
        )

    def test_a_file_that_is_not_utf8_is_a_finding_and_is_not_returned(self) -> None:
        """Bytes that aren't text give a finding on line 1."""
        self.write(".github/workflows/ci.yml", b"\xff\xfe")
        self.assertEqual(
            self.read(include_actions=False),
            ([], [".github/workflows/ci.yml:1: the file isn't UTF-8 text"]),
        )

    def test_invalid_yaml_is_a_finding_with_the_line_of_the_error(self) -> None:
        """A parse error gives a finding that holds the problem."""
        self.write(".github/workflows/ci.yml", "name: a\njobs: [x\n")
        paths, lines = self.read(include_actions=False)
        self.assertEqual(paths, [])
        self.assertEqual(len(lines), 1)
        self.assertIn(".github/workflows/ci.yml:", lines[0])
        self.assertIn("the file isn't valid YAML", lines[0])

    def test_a_symbolic_link_is_skipped(self) -> None:
        """A link to a workflow is not read twice."""
        self.write("real.yml", "name: a\n")
        folder = self.root / ".github" / "workflows"
        folder.mkdir(parents=True)
        (folder / "link.yml").symlink_to(self.root / "real.yml")
        self.assertEqual(self.read(include_actions=False), ([], []))

    def test_a_finding_is_made_at_the_line_of_a_location(self) -> None:
        """`ActionsFile.finding` uses the line of the deepest existing key."""
        self.write(".github/workflows/ci.yml", "name: a\njobs:\n  build:\n    x: 1\n")
        files, _ = read_actions_files(self.root, include_actions=False)
        file: ActionsFile = files[0]
        self.assertEqual(file.finding(["jobs", "build"], "m").line, 3)
        self.assertEqual(file.finding(["jobs", "missing"], "m").line, 2)
