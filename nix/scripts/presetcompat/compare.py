"""The invariants that version 2 of the Renovate preset keeps from version 1.

Each invariant is a function that takes the two presets, as parsed JSON, and
returns the findings that it makes. `compare` runs them all and sorts the
result. The invariants read the structure of the files: they never run
Renovate, so they hold without a network. A rule of the hub is only as good as
the check that proves it, so each invariant has a test that breaks it.

This module holds the invariants about the values that version 2 keeps and the
rules that it keeps or adds for the tags of the hub. `presetcompat.guards`
holds the invariants about what a setting or a rule of version 2 may switch
off, and about the labels. Neither module evaluates the rules of a preset in
the order in which Renovate applies them.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from decisions.findings import Finding
from presetcompat import guards
from presetcompat.values import as_list, as_mapping, describe_rule, matches_regex

Preset = Mapping[str, object]
"""A preset file, as parsed JSON."""

REQUIRED_RELEASE_AGE = "7 days"
"""The wait that every preset keeps before Renovate proposes a release."""

ALLOWED_REMOVALS = frozenset({":approveMajorUpdates"})
"""The `extends` items of version 1 that version 2 drops on purpose.

Version 2 replaces the Dashboard approval of a major update with a pull request
that carries the label `major`.
"""

HUB_PACKAGE = "sealambda/.github"
"""The package name under which Renovate sees the tags of the hub."""

VERSIONING_PREFIX = "regex:"
"""The start of a `versioning` value that names the regex versioning."""


@dataclass(frozen=True)
class Series:
    """One series of tags of the hub repository.

    Attributes:
        name: The name of the series in a message.
        sample_tag: A tag of the series. The rules must read this tag and no
            tag of the other series.
    """

    name: str
    sample_tag: str


PIN_SERIES = Series("hub pin", "v1.2.3")
"""The tags of a release of the hub: the pin of the preset in a repository."""

ACTIONS_SERIES = Series("actions series", "actions-v1.2.3")
"""The tags of the actions series of the hub."""


def compare(old: Preset, new: Preset, path: str) -> list[Finding]:
    """Return every invariant that `new` breaks.

    Args:
        old: Version 1 of the preset.
        new: Version 2 of the preset.
        path: The path of `new`, for the findings. Every finding is about the
            whole file, so its line is 1.

    Returns:
        The findings, sorted. The list is empty when `new` keeps every
        invariant.
    """
    findings = [
        *_check_release_age(new, path),
        *_check_vulnerability_alerts(new, path),
        *_check_rules_kept(old, new, path),
        *_check_extends_kept(old, new, path),
        *_check_lock_file_schedule(new, path),
        *_check_series(new, path),
        *guards.check_guards(old, new, path),
    ]
    return sorted(findings)


def _check_release_age(new: Preset, path: str) -> list[Finding]:
    """Check that `minimumReleaseAge` is still `REQUIRED_RELEASE_AGE`."""
    age = new.get("minimumReleaseAge")
    if age == REQUIRED_RELEASE_AGE:
        return []
    message = f'minimumReleaseAge must be "{REQUIRED_RELEASE_AGE}", got {age!r}'
    return [Finding(path, 1, message)]


def _check_vulnerability_alerts(new: Preset, path: str) -> list[Finding]:
    """Check that `osvVulnerabilityAlerts` is true."""
    if new.get("osvVulnerabilityAlerts") is True:
        return []
    return [Finding(path, 1, "osvVulnerabilityAlerts must be true")]


def _check_rules_kept(old: Preset, new: Preset, path: str) -> list[Finding]:
    """Check that every package rule of `old` is in `new`, unchanged."""
    kept = as_list(new.get("packageRules"))
    return [
        Finding(
            path,
            1,
            f"packageRules lacks rule {number} of version 1, unchanged: "
            f"{describe_rule(rule)}",
        )
        for number, rule in enumerate(as_list(old.get("packageRules")), start=1)
        if rule not in kept
    ]


def _check_extends_kept(old: Preset, new: Preset, path: str) -> list[Finding]:
    """Check that `new` extends all that `old` extends, but `ALLOWED_REMOVALS`."""
    kept = as_list(new.get("extends"))
    return [
        Finding(path, 1, f"extends lacks {item!r}, which version 1 extends")
        for item in as_list(old.get("extends"))
        if item not in kept and item not in ALLOWED_REMOVALS
    ]


def _check_lock_file_schedule(new: Preset, path: str) -> list[Finding]:
    """Check that the lock file maintenance has a schedule of its own."""
    schedule = as_mapping(new.get("lockFileMaintenance")).get("schedule")
    if as_list(schedule):
        return []
    return [Finding(path, 1, "lockFileMaintenance.schedule must be a list of rules")]


def _check_series(new: Preset, path: str) -> list[Finding]:
    """Check that each series of tags of the hub has one rule that reads it."""
    hub_rules = [
        as_mapping(rule)
        for rule in as_list(new.get("packageRules"))
        if HUB_PACKAGE in as_list(as_mapping(rule).get("matchPackageNames"))
    ]
    return [
        *_check_one_series(hub_rules, PIN_SERIES, ACTIONS_SERIES, path),
        *_check_one_series(hub_rules, ACTIONS_SERIES, PIN_SERIES, path),
    ]


def _check_one_series(
    hub_rules: list[Mapping[str, object]],
    series: Series,
    other: Series,
    path: str,
) -> list[Finding]:
    """Check that exactly one rule of the hub matches `series`, and reads it.

    Two series of tags live in one repository. A rule for one series that also
    matches a tag of the other series would let two rules set the versioning
    of one dependency, and Renovate would apply the later one.
    """
    matching = [
        rule
        for rule in hub_rules
        if matches_regex(rule, "matchCurrentValue", series.sample_tag)
    ]
    if len(matching) != 1:
        message = (
            f"{len(matching)} rules for {HUB_PACKAGE} have a matchCurrentValue "
            f"that matches the tag {series.sample_tag} of the {series.name}, "
            "and exactly 1 must"
        )
        return [Finding(path, 1, message)]
    return _check_versioning(matching[0], series, other, path)


def _check_versioning(
    rule: Mapping[str, object], series: Series, other: Series, path: str
) -> list[Finding]:
    """Check that the rule sets a regex versioning that reads only `series`."""
    versioning = rule.get("versioning")
    if not isinstance(versioning, str) or not versioning.startswith(VERSIONING_PREFIX):
        message = (
            f"the rule of the {series.name} must set versioning to a "
            f"{VERSIONING_PREFIX} value, got {versioning!r}"
        )
        return [Finding(path, 1, message)]
    pattern = versioning.removeprefix(VERSIONING_PREFIX)
    try:
        regex = re.compile(_to_python_syntax(pattern))
    except re.error as error:
        message = f"the versioning of the {series.name} is not a regex: {error}"
        return [Finding(path, 1, message)]
    findings = []
    if regex.search(series.sample_tag) is None:
        message = (
            f"the versioning of the {series.name} does not read {series.sample_tag}"
        )
        findings.append(Finding(path, 1, message))
    if regex.search(other.sample_tag) is not None:
        message = (
            f"the versioning of the {series.name} reads {other.sample_tag}, "
            f"a tag of the {other.name}"
        )
        findings.append(Finding(path, 1, message))
    return findings


def _to_python_syntax(pattern: str) -> str:
    """Return a JavaScript regex as a Python regex, for the one form that differs.

    Renovate names a group `(?<name>...)`, and Python names it `(?P<name>...)`.
    The look-behind forms `(?<=` and `(?<!` stay as they are.
    """
    return re.sub(r"\(\?<([A-Za-z_]\w*)>", r"(?P<\1>", pattern)
