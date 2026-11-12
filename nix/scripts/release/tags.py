"""The tag series of the hub and the rule for the next version.

A release tag has the form `v<major>.<minor>.<patch>`. Each number is `0` or
a decimal number without a leading zero. Any other tag name, such as `v1.2`,
`v01.2.3`, `v1.2.3-rc1` or `latest`, is not a release tag, and every function
here ignores it.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

_NUMBER = r"(0|[1-9][0-9]*)"
_RELEASE_TAG = re.compile(rf"v{_NUMBER}\.{_NUMBER}\.{_NUMBER}")


@dataclass(frozen=True, order=True)
class Version:
    """A version of the hub. Instances compare by major, minor and patch.

    Attributes:
        major: The major number. The hub starts at 1 and does not raise it.
        minor: The minor number. A change of the rules raises it.
        patch: The patch number. A change that leaves the rules alone raises
            it.
    """

    major: int
    minor: int
    patch: int

    @property
    def tag(self) -> str:
        """The tag name of the version, such as `v1.2.3`."""
        return f"v{self.major}.{self.minor}.{self.patch}"


FIRST_VERSION = Version(1, 0, 0)
"""The version of the first release."""


def parse_tag(name: str) -> Version | None:
    """Return the version that a tag name holds, or `None` for another name."""
    match = _RELEASE_TAG.fullmatch(name)
    if match is None:
        return None
    major, minor, patch = (int(group) for group in match.groups())
    return Version(major, minor, patch)


def _release_versions(names: Iterable[str]) -> list[Version]:
    """Return the versions of the release tags in `names`, in input order."""
    return [version for name in names if (version := parse_tag(name))]


def highest_release(names: Iterable[str]) -> Version | None:
    """Return the highest version among the release tags in `names`.

    Args:
        names: Tag names of any form. The function ignores the names that are
            not release tags.

    Returns:
        The highest version, or `None` when no name is a release tag.
    """
    return max(_release_versions(names), default=None)


def lowest_release(names: Iterable[str]) -> Version | None:
    """Return the lowest version among the release tags in `names`.

    Args:
        names: Tag names of any form. The function ignores the names that are
            not release tags.

    Returns:
        The lowest version, or `None` when no name is a release tag.
    """
    return min(_release_versions(names), default=None)


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
