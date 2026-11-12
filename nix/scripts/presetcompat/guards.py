"""Invariants about what version 2 of the Renovate preset may switch off.

Version 2 keeps the guarantees of version 1. These invariants cover the
settings and the rules that a later edit could weaken without a trace in the
checks of `presetcompat.compare`: a setting that turns Renovate off, a rule
that removes the release age, the labels of a breaking update, and the
automatic merge of the hub input.

Like the rest of the tool, the invariants read the structure of the parsed
files. They don't evaluate the package rules in the order in which Renovate
applies them, so they prove that a rule exists and that its own keys are safe,
and not what Renovate does with the rule next to the others.
"""

import re
from collections.abc import Mapping

from decisions.findings import Finding
from presetcompat.values import Rule, as_list, as_mapping, describe_rule, matches_regex

Preset = Mapping[str, object]
"""A preset file, as parsed JSON."""

REQUIRED_REBASE_WHEN = "conflicted"
"""The value of `rebaseWhen` in version 2."""

MINIMUM_AGE_SECONDS = 7 * 24 * 60 * 60
"""The shortest wait that a rule added in version 2 may set: 7 days."""

ALLOWED_ADDED_RULES: Mapping[str, str] = {}
"""Rules that version 2 adds and that may set a short age or `enabled: false`.

Each key is the `description` of the rule and each value is the reason that the
rule is safe. The mapping is empty: no rule that version 2 adds needs the
exception.
"""

BREAKING_LABEL = "breaking"
"""The label that marks a breaking update."""

HUB_INPUT = "hub"
"""The name of the flake input that holds the hub."""

_SECONDS_PER_UNIT = {
    "s": 1,
    "sec": 1,
    "secs": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "mins": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hrs": 3600,
    "hour": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
    "w": 604800,
    "week": 604800,
    "weeks": 604800,
    "month": 2592000,
    "months": 2592000,
    "y": 31557600,
    "yr": 31557600,
    "yrs": 31557600,
    "year": 31557600,
    "years": 31557600,
}
"""Time units that Renovate reads in `minimumReleaseAge`, in seconds.

Renovate reads them with the `ms` library and adds the month as 30 days. A
capital `M` alone is a month too.
"""

_AGE_PART = r"\s*\d+(?:\.\d+)?\s*[A-Za-z]+\s*"
"""One part of an age: a number and a unit."""


def check_guards(old: Preset, new: Preset, path: str) -> list[Finding]:
    """Return every invariant of this module that `new` breaks.

    Args:
        old: Version 1 of the preset.
        new: Version 2 of the preset.
        path: The path of `new`, for the findings.
    """
    messages = [
        *_check_switches(new),
        *_check_rebase_when(new),
        *_check_added_rules(old, new),
        *_check_breaking_labels(new),
        *_check_hub_input_merge(new),
    ]
    return [Finding(path, 1, message) for message in messages]


def _check_switches(new: Preset) -> list[str]:
    """Check that no setting of `new` turns Renovate or a preset off."""
    messages = []
    if new.get("enabled") is False:
        messages.append("enabled must not be false at the top level")
    if "ignorePresets" in new:
        messages.append("ignorePresets must not be set")
    if as_mapping(new.get("lockFileMaintenance")).get("enabled") is False:
        messages.append("lockFileMaintenance.enabled must not be false")
    return messages


def _check_rebase_when(new: Preset) -> list[str]:
    """Check that `rebaseWhen` is `REQUIRED_REBASE_WHEN`."""
    value = new.get("rebaseWhen")
    if value == REQUIRED_REBASE_WHEN:
        return []
    return [f'rebaseWhen must be "{REQUIRED_REBASE_WHEN}", got {value!r}']


def age_in_seconds(value: object) -> int | float | None:
    """Return a `minimumReleaseAge` string in seconds, or None if unreadable.

    The string is one or more parts of a number and a unit, such as "7 days" or
    "1 week 12 hours". A value that isn't a string, a string of another form
    and an unknown unit all return None.
    """
    if not isinstance(value, str) or not re.fullmatch(f"(?:{_AGE_PART})+", value):
        return None
    total: int | float = 0
    for number, unit in re.findall(r"(\d+(?:\.\d+)?)\s*([A-Za-z]+)", value):
        key = "month" if unit == "M" else unit.lower()
        seconds = _SECONDS_PER_UNIT.get(key)
        if seconds is None:
            return None
        total += float(number) * seconds
    return total


def _age_problem(rule: Rule) -> str | None:
    """Return why the `minimumReleaseAge` of a rule is too short, or None."""
    if "minimumReleaseAge" not in rule:
        return None
    age = rule["minimumReleaseAge"]
    seconds = age_in_seconds(age)
    if age is None:
        return "sets minimumReleaseAge to null, which removes the wait"
    if seconds is None:
        return f"sets minimumReleaseAge to {age!r}, which is no wait of 7 days"
    if seconds < MINIMUM_AGE_SECONDS:
        return f"sets minimumReleaseAge to {age!r}, below 7 days"
    return None


def _added_rule_problems(rule: Rule) -> list[str]:
    """Return what a rule that version 2 adds does that weakens the preset."""
    problems = []
    age_problem = _age_problem(rule)
    if age_problem:
        problems.append(age_problem)
    if rule.get("enabled") is False:
        problems.append("sets enabled to false")
    return problems


def _check_added_rules(old: Preset, new: Preset) -> list[str]:
    """Check that a rule added in `new` neither shortens the age nor disables.

    A rule is added when `old` has no equal rule. The rules of `ALLOWED_ADDED_RULES`
    are exempt. A changed rule of version 1 is a finding of
    `presetcompat.compare` and is also an added rule here.
    """
    known = as_list(old.get("packageRules"))
    messages: list[str] = []
    for rule in as_list(new.get("packageRules")):
        if rule in known or not isinstance(rule, dict):
            continue
        if rule.get("description") in ALLOWED_ADDED_RULES:
            continue
        messages.extend(
            f"an added rule {problem}: {describe_rule(rule)}"
            for problem in _added_rule_problems(rule)
        )
    return messages


def _has_only(rule: Rule, allowed: set[str]) -> bool:
    """Return whether every key of the rule is in `allowed`."""
    return set(rule) <= allowed


def _is_breaking_rule(rule: Rule) -> bool:
    """Return whether a rule labels every update that `matchIsBreaking` selects."""
    return (
        rule.get("matchIsBreaking") is True
        and BREAKING_LABEL in as_list(rule.get("addLabels"))
        and _has_only(rule, {"description", "matchIsBreaking", "addLabels"})
    )


def _is_minor_zero_rule(rule: Rule) -> bool:
    """Return whether a rule labels a minor update of every version `0.x`.

    The rule matches the current versions `0.1.0` and `v0.1.0`, not `1.0.0`
    and not `10.0.0`, and has no other matcher.
    """
    return (
        "minor" in as_list(rule.get("matchUpdateTypes"))
        and matches_regex(rule, "matchCurrentVersion", "0.1.0")
        and matches_regex(rule, "matchCurrentVersion", "v0.1.0")
        and not matches_regex(rule, "matchCurrentVersion", "1.0.0")
        and not matches_regex(rule, "matchCurrentVersion", "10.0.0")
        and BREAKING_LABEL in as_list(rule.get("addLabels"))
        and _has_only(
            rule,
            {"description", "matchUpdateTypes", "matchCurrentVersion", "addLabels"},
        )
    )


def _check_breaking_labels(new: Preset) -> list[str]:
    """Check that the two rules that add the label `breaking` are there.

    `matchIsBreaking` selects what the versioning of a package calls breaking.
    A versioning without that check, and a versioning whose check never reports
    a minor version of `0.x`, need the second rule.
    """
    rules = [as_mapping(rule) for rule in as_list(new.get("packageRules"))]
    messages = []
    if not any(_is_breaking_rule(rule) for rule in rules):
        messages.append(
            "packageRules has no rule that adds the label breaking where "
            "matchIsBreaking is true, with no other matcher"
        )
    if not any(_is_minor_zero_rule(rule) for rule in rules):
        messages.append(
            "packageRules has no rule that adds the label breaking to a minor "
            "update of a version 0.x, through a matchCurrentVersion regex, "
            "with no other matcher"
        )
    return messages


def _check_hub_input_merge(new: Preset) -> list[str]:
    """Check that no rule merges a major update of the hub input by itself.

    A rule that sets `automerge` to true for the input named `HUB_INPUT` must
    list the update types it covers, and the list must not hold `major`.
    """
    messages = []
    for entry in as_list(new.get("packageRules")):
        rule = as_mapping(entry)
        if rule.get("automerge") is not True:
            continue
        if HUB_INPUT not in as_list(rule.get("matchDepNames")):
            continue
        types = as_list(rule.get("matchUpdateTypes"))
        if not types or "major" in types:
            messages.append(
                f"the rule that merges the input {HUB_INPUT} must list "
                f"matchUpdateTypes without major: {describe_rule(rule)}"
            )
    return messages
