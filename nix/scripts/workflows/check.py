"""The whole check: both rules on every workflow of a tree."""

from pathlib import Path

from decisions.findings import Finding
from decisions.workflow_files import read_actions_files
from workflows.rules import check_concurrency, check_timeouts


def check_tree(root: Path) -> list[Finding]:
    """Check the time limits and the concurrency groups of a tree.

    The files are the workflows and starter workflows that
    `decisions.workflow_files.read_actions_files` selects. A composite action
    has no jobs and no events, so it isn't read. A file that isn't valid YAML
    is a finding, because it could hide a job.

    Args:
        root: The checked tree.

    Returns:
        The findings, sorted by path, line and message.

    Raises:
        OSError: A file can't be listed or read.
    """
    files, findings = read_actions_files(root, include_actions=False)
    for file in files:
        findings.extend(check_timeouts(file))
        findings.extend(check_concurrency(file))
    return sorted(findings)
