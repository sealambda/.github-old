"""Helpers that read the parsed JSON of a preset without failing on a bad shape.

A preset file is untrusted input: a key can hold any JSON value. These helpers
return an empty value for a wrong shape, so an invariant reports a finding
instead of raising an exception.
"""

import json
import re
from collections.abc import Mapping

Rule = Mapping[str, object]
"""A package rule, as parsed JSON."""


def as_list(value: object) -> list[object]:
    """Return `value` when it is a list, and an empty list otherwise."""
    return value if isinstance(value, list) else []


def as_mapping(value: object) -> Mapping[str, object]:
    """Return `value` when it is an object, and an empty one otherwise."""
    return value if isinstance(value, dict) else {}


def describe_rule(rule: object) -> str:
    """Return a short name for a package rule: its description, cut short."""
    text = as_mapping(rule).get("description")
    if not isinstance(text, str):
        text = json.dumps(rule, sort_keys=True)
    return text if len(text) <= 60 else text[:57] + "..."


def matches_regex(rule: Rule, key: str, text: str) -> bool:
    """Return whether the matcher `key` of a rule, a `/regex/`, finds `text`.

    The match is a search, as Renovate does it. A rule that lacks the key, a
    value that isn't of the form `/regex/` and an invalid regex all return
    false.
    """
    pattern = rule.get(key)
    if not isinstance(pattern, str) or not re.fullmatch(r"/.+/", pattern):
        return False
    try:
        return re.search(pattern[1:-1], text) is not None
    except re.error:
        return False
