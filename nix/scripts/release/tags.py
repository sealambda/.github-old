"""The tag series of the hub and the rule for the next version.

A release tag has the form `<prefix><major>.<minor>.<patch>`. Each number is
`0` or a decimal number without a leading zero. The hub has two series that
differ in the prefix only: the hub series (`HUB_PREFIX`, for example `v1.2.3`)
and the actions series (`ACTIONS_PREFIX`, for example `actions-v1.2.3`). Any
other tag name, such as `v1.2`, `v01.2.3`, `v1.2.3-rc1` or `latest`, is not a
release tag of either series, and every function here ignores it. A tag of one
series is never a tag of the other: the match covers the whole name, so the
prefix `v` doesn't match inside `actions-v1.2.3`.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache

HUB_PREFIX = "v"
"""The prefix of the tags of the hub series, such as `v1.2.3`."""

ACTIONS_PREFIX = "actions-v"
"""The prefix of the tags of the actions series, such as `actions-v1.2.3`."""

_NUMBER = r"(0|[1-9][0-9]*)"


@cache
def _release_pattern(prefix: str) -> re.Pattern[str]:
    """Return the pattern of the release tags that start with `prefix`."""
    return re.compile(rf"{re.escape(prefix)}{_NUMBER}\.{_NUMBER}\.{_NUMBER}")


@dataclass(frozen=True, order=True)
class Version:
    """A version of a tag series. Instances compare by major, minor and patch.

    Attributes:
        major: The major number. A series starts at 1 and does not raise it.
        minor: The minor number. A change of the rules raises it.
        patch: The patch number. A change that leaves the rules alone raises
            it.
    """

    major: int
    minor: int
    patch: int

    @property
    def tag(self) -> str:
        """The tag name of the version in the hub series, such as `v1.2.3`."""
        return self.tag_with(HUB_PREFIX)

    def tag_with(self, prefix: str) -> str:
        """Return the tag name of the version in the series of `prefix`."""
        return f"{prefix}{self.major}.{self.minor}.{self.patch}"


FIRST_VERSION = Version(1, 0, 0)
"""The version of the first release."""


def parse_tag(name: str, prefix: str = HUB_PREFIX) -> Version | None:
    """Return the version that a tag name holds, or `None` for another name.

    Args:
        name: A tag name of any form.
        prefix: The prefix of the series. The default is the hub series.
    """
    match = _release_pattern(prefix).fullmatch(name)
    if match is None:
        return None
    major, minor, patch = (int(group) for group in match.groups())
    return Version(major, minor, patch)


def _release_versions(names: Iterable[str], prefix: str) -> list[Version]:
    """Return the versions of the release tags in `names`, in input order."""
    return [version for name in names if (version := parse_tag(name, prefix))]


def highest_release(names: Iterable[str], prefix: str = HUB_PREFIX) -> Version | None:
    """Return the highest version among the release tags in `names`.

    Args:
        names: Tag names of any form. The function ignores the names that are
            not release tags of the series.
        prefix: The prefix of the series. The default is the hub series.

    Returns:
        The highest version, or `None` when no name is a release tag.
    """
    return max(_release_versions(names, prefix), default=None)


def lowest_release(names: Iterable[str], prefix: str = HUB_PREFIX) -> Version | None:
    """Return the lowest version among the release tags in `names`.

    Args:
        names: Tag names of any form. The function ignores the names that are
            not release tags of the series.
        prefix: The prefix of the series. The default is the hub series.

    Returns:
        The lowest version, or `None` when no name is a release tag.
    """
    return min(_release_versions(names, prefix), default=None)


def next_version(previous: Version | None, rules_changed: bool) -> Version:
    """Return the version of the next release.

    Args:
        previous: The version of the previous release, `None` for the first.
        rules_changed: Whether the rules changed since the previous release.

    Returns:
        `FIRST_VERSION` without a previous release. A change of the rules
        raises the minor number and resets the patch number. Any other change
        raises the patch number.
    """
    if previous is None:
        return FIRST_VERSION
    if rules_changed:
        return Version(previous.major, previous.minor + 1, 0)
    return Version(previous.major, previous.minor, previous.patch + 1)
