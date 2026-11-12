"""Invariants about what version 2 of the Renovate preset may switch off.

Version 2 keeps the guarantees of version 1. These invariants cover the
settings and the rules that a later edit could weaken without a trace in the
checks of `presetcompat.compare`: a setting that turns Renovate or a manager
off, the schedule, a rule that removes the release age, the labels of a
breaking update, the rebase of a pull request that merges by itself, and the
automatic merge of a major update and of the hub input.

Like the rest of the tool, the invariants read the structure of the parsed
files. They don't evaluate the package rules in the order in which Renovate
applies them, so they prove that a rule exists and that its own keys are safe,
and not what Renovate does with the rule next to the others.
"""

import re

from decisions.findings import Finding
from presetcompat.values import (
    HUB_PACKAGE,
    REQUIRED_RELEASE_AGE,
    Preset,
    Rule,
    as_list,
    as_mapping,
    describe_rule,
    matches_regex,
)

REQUIRED_REBASE_WHEN = "conflicted"
"""The value of `rebaseWhen` in version 2."""

AUTOMERGE_REBASE_WHEN = "behind-base-branch"
"""The value of `rebaseWhen` for a pull request that Renovate merges by itself.

With `conflicted`, Renovate never updates a pull request that only fell behind
its base branch. A repository that requires an up-to-date branch then refuses
the merge, and nobody reviews the stuck pull request. A pull request that
merges by itself has no approval to keep, so it can rebase.
"""

BREAKING_LABEL = "breaking"
"""The label that marks a breaking update."""

HUB_INPUT = "hub"
"""The name of the flake input that holds the hub."""

HUB_INPUT_SOURCE = f"https://github.com/{HUB_PACKAGE}"
"""The package name that the Nix manager gives to a GitHub input of the hub.

The manager builds it from the `original` entry of `flake.lock`, so the rule for
the input `hub` can tell the hub from another input that has the same name.
"""

MANAGER_SWITCHES = ("nix", "mise")
"""The managers that version 2 turns on, and that no setting may turn off."""

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
        *_check_automerge_rebase(new),
        *_check_added_rules(old, new),
        *_check_breaking_labels(new),
        *_check_hub_input_source(new),
    ]
    return [Finding(path, 1, message) for message in messages]


def _check_switches(new: Preset) -> list[str]:
    """Check that no setting of `new` turns Renovate, a manager or a preset off.

    The top-level `schedule` must also hold at least one entry: an empty list
    runs Renovate on every day, and a missing one does the same.
    """
    messages = []
    if new.get("enabled") is False:
        messages.append("enabled must not be false at the top level")
    if "ignorePresets" in new:
        messages.append("ignorePresets must not be set")
    if as_mapping(new.get("lockFileMaintenance")).get("enabled") is False:
        messages.append("lockFileMaintenance.enabled must not be false")
    if not as_list(new.get("schedule")):
        messages.append("schedule must be a list with at least one entry")
    messages.extend(
        f"{manager}.enabled must not be false"
        for manager in MANAGER_SWITCHES
        if as_mapping(new.get(manager)).get("enabled") is False
    )
    return messages


def _check_rebase_when(new: Preset) -> list[str]:
    """Check that `rebaseWhen` is `REQUIRED_REBASE_WHEN`."""
    value = new.get("rebaseWhen")
    if value == REQUIRED_REBASE_WHEN:
        return []
    return [f'rebaseWhen must be "{REQUIRED_REBASE_WHEN}", got {value!r}']


def _match_keys(rule: Rule) -> dict[str, object]:
    """Return the matchers of a rule: the keys that select what it applies to."""
    return {key: value for key, value in rule.items() if key.startswith("match")}


def _check_automerge_rebase(new: Preset) -> list[str]:
    """Check that a pull request that merges by itself rebases when it is behind.

    Every rule with `automerge: true` needs a rule that has the same matchers and
    sets `rebaseWhen` to `AUTOMERGE_REBASE_WHEN`. That can be the rule itself, or
    a later rule that repeats the matchers, which a rule kept from version 1 needs
    because version 2 may not change it.
    """
    rules = [as_mapping(rule) for rule in as_list(new.get("packageRules"))]
    rebasing = [
        _match_keys(rule)
        for rule in rules
        if rule.get("rebaseWhen") == AUTOMERGE_REBASE_WHEN
    ]
    return [
        "a rule that sets automerge to true has no rule with the same matchers "
        f'that sets rebaseWhen to "{AUTOMERGE_REBASE_WHEN}": {describe_rule(rule)}'
        for rule in rules
        if rule.get("automerge") is True and _match_keys(rule) not in rebasing
    ]


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


def _required_age_seconds() -> int | float:
    """Return `REQUIRED_RELEASE_AGE` in seconds.

    Raises:
        ValueError: The constant isn't a wait that `age_in_seconds` reads. This
            is a bug in the tool, and it shows at import.
    """
    seconds = age_in_seconds(REQUIRED_RELEASE_AGE)
    if seconds is None:
        raise ValueError(f"unreadable REQUIRED_RELEASE_AGE: {REQUIRED_RELEASE_AGE!r}")
    return seconds


MINIMUM_AGE_SECONDS = _required_age_seconds()
"""The shortest wait that a rule added in version 2 may set."""


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


def _automerge_problem(rule: Rule) -> str | None:
    """Return why a rule that merges by itself may merge a major update, or None.

    A rule with `automerge: true` must list the update types that it covers, and
    the list must not hold `major`: a person reviews a major update.
    """
    if rule.get("automerge") is not True:
        return None
    types = as_list(rule.get("matchUpdateTypes"))
    if not types or "major" in types:
        return (
            "sets automerge to true without a matchUpdateTypes list that "
            "leaves out major"
        )
    return None


def _added_rule_problems(rule: Rule) -> list[str]:
    """Return what a rule that version 2 adds does that weakens the preset."""
    problems = [
        problem for problem in (_age_problem(rule), _automerge_problem(rule)) if problem
    ]
    if rule.get("enabled") is False:
        problems.append("sets enabled to false")
    return problems


def _check_added_rules(old: Preset, new: Preset) -> list[str]:
    """Check that a rule added in `new` keeps the age, stays on and merges no major.

    A rule is added when `old` has no equal rule. A changed rule of version 1 is
    a finding of `presetcompat.compare` and is also an added rule here.
    """
    known = as_list(old.get("packageRules"))
    messages: list[str] = []
    for rule in as_list(new.get("packageRules")):
        if rule in known or not isinstance(rule, dict):
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


def _check_hub_input_source(new: Preset) -> list[str]:
    """Check that a rule that merges the input `HUB_INPUT` names its source.

    The name `hub` is a convention, so a rule that merges by that name alone
    would also merge an unrelated input of that name. The rule must match the
    package `HUB_INPUT_SOURCE` too.
    """
    messages = []
    for entry in as_list(new.get("packageRules")):
        rule = as_mapping(entry)
        if rule.get("automerge") is not True:
            continue
        if HUB_INPUT not in as_list(rule.get("matchDepNames")):
            continue
        if HUB_INPUT_SOURCE not in as_list(rule.get("matchPackageNames")):
            messages.append(
                f"the rule that merges the input {HUB_INPUT} must match the "
                f"package {HUB_INPUT_SOURCE}: {describe_rule(rule)}"
            )
    return messages
