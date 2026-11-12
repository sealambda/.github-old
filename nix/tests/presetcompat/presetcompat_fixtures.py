"""Shared fixtures of the tests of the preset comparison.

The tests do not read the real `default.json` and `v2.json`: the flake check
`presetcompat` does that. They build a small pair of presets that keep every
invariant, break one invariant at a time, and look at the findings. The helpers
return a new object on every call, so a test can change its copy freely.
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from presetcompat.cli import main
from presetcompat.compare import compare

Preset = dict[str, Any]
"""A preset or a package rule, as parsed JSON that a test may change."""

NEW_PATH = "v2.json"
"""The path that the tests give for version 2 in a finding."""


def hub_rule(pattern: str, versioning: str) -> Preset:
    """Return a package rule for the tags of the hub repository.

    Args:
        pattern: The `matchCurrentValue`, in the form `/regex/`.
        versioning: The `versioning` value.
    """
    return {
        "matchPackageNames": ["sealambda/.github"],
        "matchCurrentValue": pattern,
        "versioning": versioning,
    }


def pin_rule() -> Preset:
    """Return the rule for the tags `v1.2.3`, the pin of the preset."""
    return hub_rule(
        "/^v\\d/", "regex:^v(?<major>\\d+)\\.(?<minor>\\d+)\\.(?<patch>\\d+)$"
    )


def actions_rule() -> Preset:
    """Return the rule for the tags `actions-v1.2.3`, the actions series."""
    return hub_rule(
        "/^actions-v/",
        "regex:^actions-v(?<major>\\d+)\\.(?<minor>\\d+)\\.(?<patch>\\d+)$",
    )


def breaking_rule() -> Preset:
    """Return the rule that labels what `matchIsBreaking` selects."""
    return {"matchIsBreaking": True, "addLabels": ["breaking"]}


def minor_zero_rule() -> Preset:
    """Return the rule that labels a minor update of a version `0.x`."""
    return {
        "matchUpdateTypes": ["minor"],
        "matchCurrentVersion": "/^v?0\\./",
        "addLabels": ["breaking"],
    }


def hub_input_rule() -> Preset:
    """Return the rule that merges the flake input `hub`, but not a major.

    The rule names the source of the hub and rebases when it is behind.
    """
    return {
        "matchManagers": ["nix"],
        "matchDepNames": ["hub"],
        "matchPackageNames": ["https://github.com/sealambda/.github"],
        "matchUpdateTypes": ["digest", "patch", "minor"],
        "rebaseWhen": "behind-base-branch",
        "automerge": True,
    }


def security_rule() -> Preset:
    """Return a rule of version 1 that merges by itself and covers every type."""
    return {
        "matchJsonata": ["isVulnerabilityAlert = true and newValue = currentValue"],
        "automerge": True,
    }


def security_rebase_rule() -> Preset:
    """Return the rule of version 2 that rebases what `security_rule` merges."""
    return {
        "matchJsonata": ["isVulnerabilityAlert = true and newValue = currentValue"],
        "rebaseWhen": "behind-base-branch",
    }


def old_preset() -> Preset:
    """Return a small version 1: two package rules and an approval."""
    return {
        "extends": ["config:best-practices", ":approveMajorUpdates"],
        "minimumReleaseAge": "7 days",
        "osvVulnerabilityAlerts": True,
        "schedule": ["* 0-9 * * 1"],
        "lockFileMaintenance": {"schedule": ["* 0-9 1 * *"]},
        "packageRules": [
            {"matchManagers": ["nix"], "minimumReleaseAge": None},
            {"matchManagers": ["mix"], "groupName": "Mix"},
        ],
    }


def new_preset() -> Preset:
    """Return the version 2 that keeps every invariant of `old_preset`."""
    return {
        "extends": ["config:best-practices"],
        "minimumReleaseAge": "7 days",
        "osvVulnerabilityAlerts": True,
        "schedule": ["* 0-9 * * 1"],
        "rebaseWhen": "conflicted",
        "lockFileMaintenance": {"schedule": ["* 0-9 * * 1"]},
        "packageRules": [
            {"matchManagers": ["nix"], "minimumReleaseAge": None},
            {"matchManagers": ["mix"], "groupName": "Mix"},
            breaking_rule(),
            minor_zero_rule(),
            hub_input_rule(),
            pin_rule(),
            actions_rule(),
        ],
    }


def messages_of(old: Preset, new: Preset) -> list[str]:
    """Return the messages of the findings of `compare`, in order."""
    return [finding.message for finding in compare(old, new, NEW_PATH)]


class CliTestCase(unittest.TestCase):
    """A test case with an empty directory in `self.root` and a way to run the tool.

    Attributes:
        root: The directory that holds the files of the test.
    """

    root: Path

    def setUp(self) -> None:
        """Create the directory and remove it after the test."""
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)

    def write_json(self, name: str, value: object) -> Path:
        """Write `value` as a JSON file below the root and return its path."""
        path = self.root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def run_cli(self, *arguments: str) -> tuple[int, list[str], str]:
        """Run the tool with the arguments.

        Returns:
            The exit status, the lines of standard output and standard error.
        """
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = main(list(arguments))
        return status, stdout.getvalue().splitlines(), stderr.getvalue()
