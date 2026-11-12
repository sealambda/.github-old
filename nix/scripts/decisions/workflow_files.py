"""Select and read the GitHub Actions files of a tree.

The tools `versions` and `workflows` read the same files: the workflows, the
starter workflows and, for `versions`, the composite actions. This module is the
one place that decides which paths are such files, reads them and parses their
YAML, so the two tools can't disagree about what a workflow is.
"""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml

from decisions.findings import Finding
from decisions.walk import list_files
from decisions.yamlio import YamlDocument, describe_error, line_of, parse_yaml

_WORKFLOW_FOLDER_PARTS = (".github", "workflows")
# The folder of the starter workflows of an organization, at the root of its
# `.github` repository:
# https://docs.github.com/en/actions/how-tos/reuse-automations/create-workflow-templates
_TEMPLATE_FOLDER_PARTS = ("workflow-templates",)
_WORKFLOW_SUFFIXES = frozenset({".yml", ".yaml"})
_ACTION_NAMES = frozenset({"action.yml", "action.yaml"})

type Location = list[str | int]
"""The keys and indexes that lead from the root of a document to a value."""


@dataclass(frozen=True)
class ActionsFile:
    """A parsed workflow or action file.

    Attributes:
        path: The file, relative to the checked root, with `/` separators.
        document: The parsed YAML of the file, with the node tree that holds
            the lines.
    """

    path: str
    document: YamlDocument

    def finding(self, location: Location, message: str) -> Finding:
        """Return a finding at the line of the value at `location`.

        Args:
            location: The keys and indexes from the root of the document. The
                line is that of the deepest value that exists.
            message: What is wrong, in one sentence.
        """
        return Finding(self.path, line_of(self.document.root, location), message)


def is_workflow_path(relative: PurePosixPath) -> bool:
    """Tell whether a path is a workflow or a starter workflow.

    A workflow is a `.yml` or `.yaml` file directly in a folder `workflows`
    whose parent is a folder `.github`, wherever that folder sits. A file in a
    subfolder of `workflows` isn't a workflow: GitHub doesn't read it. A
    starter workflow is the same kind of file directly in the folder
    `workflow-templates` at the root of the tree, where GitHub reads the
    templates of an organization. The `.properties.json` files and the icons
    of that folder aren't YAML, so they have no candidate suffix.

    Args:
        relative: A path relative to the checked root.
    """
    parent = relative.parent.parts
    in_workflow_folder = (
        parent[-2:] == _WORKFLOW_FOLDER_PARTS or parent == _TEMPLATE_FOLDER_PARTS
    )
    return in_workflow_folder and relative.suffix in _WORKFLOW_SUFFIXES


def is_action_path(relative: PurePosixPath) -> bool:
    """Tell whether a path is the metadata file of an action.

    Args:
        relative: A path relative to the checked root.
    """
    return relative.name in _ACTION_NAMES


def read_actions_files(
    root: Path, *, include_actions: bool
) -> tuple[list[ActionsFile], list[Finding]]:
    """Read the workflows of a tree, and optionally its actions.

    The files are the workflows and starter workflows that `is_workflow_path`
    accepts, and with `include_actions` every `action.yml` and `action.yaml`
    below `root`. The listing is `decisions.walk.list_files`. A symbolic link
    is skipped. A file that isn't UTF-8 text or isn't valid YAML is a finding,
    because it could hide a rule that the caller checks.

    Args:
        root: The checked tree.
        include_actions: Whether to read the action files too.

    Returns:
        The files that parsed, in the order of the listing, and one finding
        for each file that didn't.

    Raises:
        OSError: A file can't be listed or read.
    """
    files: list[ActionsFile] = []
    findings: list[Finding] = []
    for relative in list_files(root):
        selected = is_workflow_path(relative) or (
            include_actions and is_action_path(relative)
        )
        file = root / relative
        if not selected or not file.is_file() or file.is_symlink():
            continue
        path = relative.as_posix()
        try:
            files.append(ActionsFile(path, _parse(file)))
        except UnicodeDecodeError:
            findings.append(Finding(path, 1, "the file isn't UTF-8 text"))
        except yaml.YAMLError as error:
            line, problem = describe_error(error)
            findings.append(
                Finding(path, line, f"the file isn't valid YAML: {problem}")
            )
    return files, findings


def _parse(file: Path) -> YamlDocument:
    """Read a file as UTF-8 and parse its YAML.

    Raises:
        UnicodeDecodeError: The file isn't UTF-8 text.
        yaml.YAMLError: The text isn't valid YAML, or holds several documents.
    """
    return parse_yaml(file.read_text(encoding="utf-8"))
