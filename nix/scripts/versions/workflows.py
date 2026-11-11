"""Check the steps that install Nix in the workflows and actions of a tree."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml
from yaml.nodes import Node

from decisions.findings import Finding
from decisions.walk import list_files
from decisions.yamlio import describe_error, line_of, parse_yaml
from versions.installers import is_other_installer_action, script_installer_fragment

INSTALL_ACTION = "cachix/install-nix-action"
"""The installer action whose `install_url` input pins the Nix version."""

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
class _Source:
    """The file of a step, for its findings.

    Attributes:
        path: The file, relative to the checked root, with `/` separators.
        root: The node tree of the file, which holds the lines.
    """

    path: str
    root: Node | None

    def finding(self, location: Location, message: str) -> Finding:
        """Return a finding at the line of the value at `location`."""
        return Finding(self.path, line_of(self.root, location), message)


def check_workflows(root: Path, expected_url: str | None) -> list[Finding]:
    """Check every installer step of the workflows and actions of a tree.

    The files are `.github/workflows/*.yml` and `*.yaml` at any depth of the
    tree, for example `templates/x/.github/workflows/ci.yml`, the starter
    workflows `workflow-templates/*.yml` and `*.yaml` at the root, and every
    `action.yml` and `action.yaml` below `root`. A file that isn't valid YAML
    is a finding, because it could hide a step.

    Args:
        root: The checked tree.
        expected_url: The `install_url` that every `cachix/install-nix-action`
            step must set, or `None` when the manifest is invalid and the
            version is unknown: the check of the address is then skipped.

    Returns:
        One finding for each step that doesn't meet the rules, and for each
        file that isn't valid YAML.

    Raises:
        OSError: A file can't be listed or read.
    """
    findings: list[Finding] = []
    for relative in list_files(root):
        file = root / relative
        if _is_candidate(relative) and file.is_file() and not file.is_symlink():
            findings.extend(_check_file(file, relative.as_posix(), expected_url))
    return findings


def _is_candidate(relative: PurePosixPath) -> bool:
    """Tell whether a path is a workflow, a starter workflow or an action file.

    A workflow is a `.yml` or `.yaml` file directly in a folder `workflows`
    whose parent is a folder `.github`, wherever that folder sits. A file in a
    subfolder of `workflows` isn't a workflow: GitHub doesn't read it. A
    starter workflow is the same kind of file directly in the folder
    `workflow-templates` at the root of the tree, where GitHub reads the
    templates of an organization. The `.properties.json` files and the icons
    of that folder aren't YAML, so they have no candidate suffix.
    """
    if relative.name in _ACTION_NAMES:
        return True
    parent = relative.parent.parts
    in_workflow_folder = (
        parent[-2:] == _WORKFLOW_FOLDER_PARTS or parent == _TEMPLATE_FOLDER_PARTS
    )
    return in_workflow_folder and relative.suffix in _WORKFLOW_SUFFIXES


def _check_file(file: Path, path: str, expected_url: str | None) -> list[Finding]:
    """Check the steps of one workflow or action file.

    A YAML anchor can make two `steps` lists one node, so two steps then have
    the same line and message. The result holds each finding once, in the order
    of the steps.
    """
    try:
        text = file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [Finding(path, 1, "the file isn't UTF-8 text")]
    try:
        document = parse_yaml(text)
    except yaml.YAMLError as error:
        line, problem = describe_error(error)
        return [Finding(path, line, f"the file isn't valid YAML: {problem}")]
    source = _Source(path, document.root)
    findings = []
    for location, step in _iter_steps(document.data):
        finding = _check_step(source, location, step, expected_url)
        if finding is not None:
            findings.append(finding)
    return list(dict.fromkeys(findings))


def _iter_steps(data: object) -> Iterator[tuple[Location, dict[object, object]]]:
    """Yield each step of a workflow or composite action with its location.

    A workflow holds steps in `jobs.<id>.steps`, and a composite action in
    `runs.steps`. A value of another shape is skipped: actionlint reports it.

    Args:
        data: The parsed document.

    Yields:
        The location of the step, as the keys and indexes from the root, and
        the step mapping.
    """
    if not isinstance(data, dict):
        return
    jobs = data.get("jobs")
    if isinstance(jobs, dict):
        for job_id, job in jobs.items():
            if isinstance(job, dict):
                yield from _iter_list(["jobs", str(job_id), "steps"], job.get("steps"))
    runs = data.get("runs")
    if isinstance(runs, dict):
        yield from _iter_list(["runs", "steps"], runs.get("steps"))


def _iter_list(
    location: Location, steps: object
) -> Iterator[tuple[Location, dict[object, object]]]:
    """Yield the mappings of a `steps` list with their locations."""
    if not isinstance(steps, list):
        return
    for index, step in enumerate(steps):
        if isinstance(step, dict):
            yield [*location, index], step


def _check_step(
    source: _Source,
    location: Location,
    step: dict[object, object],
    expected_url: str | None,
) -> Finding | None:
    """Return the finding for a step, or `None` when the step is fine.

    A `run` step is read as a script, and any other step as an action.
    """
    run = step.get("run")
    if isinstance(run, str):
        return _check_script(source, location, run)
    return _check_action(source, location, step, expected_url)


def _check_script(source: _Source, location: Location, script: str) -> Finding | None:
    """Return a finding when a `run` script holds an address or name of an installer."""
    fragment = script_installer_fragment(script)
    if fragment is None:
        return None
    return source.finding(
        [*location, "run"],
        f"the script uses the Nix installer {fragment}, whose version this check "
        f"can't read; use {INSTALL_ACTION} with install_url",
    )


def _check_action(
    source: _Source,
    location: Location,
    step: dict[object, object],
    expected_url: str | None,
) -> Finding | None:
    """Return the finding for a `uses` step, or `None` when the step is fine.

    A step that doesn't install Nix is fine. A local action (`./path`) and a
    Docker image are skipped: the files of a local action are checked as
    actions of their own.
    """
    uses = step.get("uses")
    if not isinstance(uses, str) or uses.startswith(("./", "docker://")):
        return None
    name = uses.split("@", 1)[0].lower()
    if name == INSTALL_ACTION:
        return _check_install_url(source, location, step, expected_url)
    if is_other_installer_action(name):
        return source.finding(
            [*location, "uses"],
            f"{name} installs a Nix version that this check can't read; "
            f"use {INSTALL_ACTION} with install_url",
        )
    return None


def _check_install_url(
    source: _Source,
    location: Location,
    step: dict[object, object],
    expected_url: str | None,
) -> Finding | None:
    """Return a finding when the `install_url` of an installer step differs."""
    if expected_url is None:
        return None
    options = step.get("with")
    actual = options.get("install_url") if isinstance(options, dict) else None
    if actual == expected_url:
        return None
    if actual is None:
        return source.finding(
            [*location, "uses"],
            f"{INSTALL_ACTION} has no install_url; set it to {expected_url}",
        )
    return source.finding(
        [*location, "with", "install_url"],
        f"install_url is {actual}; set it to {expected_url}",
    )
