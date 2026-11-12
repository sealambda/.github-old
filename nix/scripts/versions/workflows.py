"""Check the steps that install Nix in the workflows and actions of a tree."""

from collections.abc import Iterator
from pathlib import Path

from decisions.findings import Finding
from decisions.workflow_files import ActionsFile, Location, read_actions_files
from versions.action_output import (
    EXPRESSION_URL,
    SETUP_NIX_ACTION,
    check_producer,
    is_expression_form,
)
from versions.installers import is_other_installer_action, script_installer_fragment

INSTALL_ACTION = "cachix/install-nix-action"
"""The installer action whose `install_url` input pins the Nix version."""

_EXPRESSION_HINT = f"; only {SETUP_NIX_ACTION} may use that expression"
"""The ending of a finding on the expression form in another file."""


def check_workflows(root: Path, expected_url: str | None) -> list[Finding]:
    """Check every installer step of the workflows and actions of a tree.

    `decisions.workflow_files.read_actions_files` selects and reads the files
    with `include_actions`: the workflows `.github/workflows/*.yml` and
    `*.yaml` at any depth of the tree, for example
    `templates/x/.github/workflows/ci.yml`, the starter workflows
    `workflow-templates/*.yml` and `*.yaml` at the root, and every
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
    files, findings = read_actions_files(root, include_actions=True)
    for file in files:
        findings.extend(_check_file(file, expected_url))
    return findings


def _check_file(file: ActionsFile, expected_url: str | None) -> list[Finding]:
    """Check the steps of one workflow or action file.

    A YAML anchor can make two `steps` lists one node, so two steps then have
    the same line and message. The result holds each finding once, in the order
    of the steps.
    """
    findings = []
    for location, step in _iter_steps(file.document.data):
        finding = _check_step(file, location, step, expected_url)
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
    source: ActionsFile,
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


def _check_script(
    source: ActionsFile, location: Location, script: str
) -> Finding | None:
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
    source: ActionsFile,
    location: Location,
    step: dict[object, object],
    expected_url: str | None,
) -> Finding | None:
    """Return the finding for a `uses` step, or `None` when the step is fine.

    A step that doesn't install Nix is fine. A local action (`./path`) and a
    Docker image are skipped: the files of a local action are checked as
    actions of their own, so a job that installs Nix through a local action
    stays under the rule through the installer step of that action.
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
    source: ActionsFile,
    location: Location,
    step: dict[object, object],
    expected_url: str | None,
) -> Finding | None:
    """Return a finding when the `install_url` of an installer step differs.

    The exact address always passes. The hub's setup action,
    `.github/actions/setup-nix/action.yml`, may use one expression instead,
    when its earlier step reads `versions.json` (`versions.action_output`).
    """
    if expected_url is None:
        return None
    options = step.get("with")
    actual = options.get("install_url") if isinstance(options, dict) else None
    if actual == expected_url:
        return None
    if is_expression_form(source, actual):
        return check_producer(source, location)
    if actual is None:
        return source.finding(
            [*location, "uses"],
            f"{INSTALL_ACTION} has no install_url; set it to {expected_url}",
        )
    return source.finding(
        [*location, "with", "install_url"],
        f"install_url is {actual}; set it to {expected_url}"
        + (_EXPRESSION_HINT if actual == EXPRESSION_URL else ""),
    )
