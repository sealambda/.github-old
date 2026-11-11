"""The whole check: the manifest, and the workflows against the manifest."""

from pathlib import Path

from decisions.findings import Finding
from versions.manifest import install_url, read_manifest
from versions.workflows import check_workflows


def check_tree(root: Path) -> list[Finding]:
    """Check `versions.json` and the Nix installer steps of a tree.

    When the manifest has a finding, the Nix version is unknown, so the check
    of each `install_url` is skipped: the manifest findings come with the
    findings about installers whose version can't be read.

    Args:
        root: The checked tree.

    Returns:
        The findings, sorted by path, line and message.

    Raises:
        OSError: A file can't be listed or read.
    """
    manifest = read_manifest(root)
    expected = (
        install_url(manifest.nix_version) if manifest.nix_version is not None else None
    )
    return sorted([*manifest.findings, *check_workflows(root, expected)])
