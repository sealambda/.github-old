"""The tag series of the hub and the rule that each one follows.

The hub releases two series from one history. The hub series (`HUB`) covers the
rules that a flake consumer reads, and the actions series (`ACTIONS`) covers the
workflow and action files that a consumer calls by tag. A `Series` holds what
differs between them: the tag prefix, the rule that turns changed paths into a
kind of release (`Bump`), the first line of the notes and the "latest" label.
Everything else, from the plan to the call of `gh`, is shared.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum

from release.paths import (
    ACTIONS_DATA_PATTERNS,
    ACTIONS_FILE_PATTERNS,
    matches_any,
    rules_changed,
)
from release.tags import ACTIONS_PREFIX, HUB_PREFIX


class Bump(Enum):
    """The kind of release that a set of changed paths asks for.

    Attributes:
        NONE: No release. Only the actions series returns it.
        PATCH: The patch number rises.
        MINOR: The minor number rises and the patch number resets.
    """

    NONE = "none"
    PATCH = "patch"
    MINOR = "minor"


PathRule = Callable[[Iterable[str]], Bump]
"""A rule that turns the changed paths of a range into a `Bump`."""


@dataclass(frozen=True)
class Series:
    """A tag series and the rule that decides its releases.

    Attributes:
        name: The name on the command line, such as `hub`.
        prefix: The prefix of the tags, such as `v`.
        label: The text before `: yes` or `: no` in the first line of the
            notes.
        make_latest: Whether the release takes the "latest" label on GitHub. At
            most one series can have it, so that the label stays with the hub.
        bump_for_changes: The rule for the paths that differ between the
            previous release and the commit.
        bump_for_first_release: The rule for the paths of the whole tree, when
            the series has no release yet. The actions series returns `NONE`
            for a tree without a workflow or action file, so its first tag
            lands on the first commit that has one.
    """

    name: str
    prefix: str
    label: str
    make_latest: bool
    bump_for_changes: PathRule
    bump_for_first_release: PathRule


def _hub_bump(paths: Iterable[str]) -> Bump:
    """Return `MINOR` when a path is a rule of the hub series, else `PATCH`.

    The hub series releases every commit, so it never returns `NONE`: a change
    of no path, or of paths that no consumer reads, gives a patch.
    """
    return Bump.MINOR if rules_changed(paths) else Bump.PATCH


def _hub_first_bump(paths: Iterable[str]) -> Bump:
    """Return `MINOR`: the first release of the hub series has no comparison."""
    del paths
    return Bump.MINOR


def _actions_bump(paths: Iterable[str]) -> Bump:
    """Return the kind of release that the changed paths ask of the actions series.

    A workflow or action file gives `MINOR`: a consumer that calls the tag runs
    different steps. A change to the data files alone (`versions.json`) gives
    `PATCH`: the steps stay the same and only the value that they read moves.
    Any other path gives no release. A path of both groups gives `MINOR`.
    """
    kinds = {_actions_kind(path) for path in paths}
    if Bump.MINOR in kinds:
        return Bump.MINOR
    if Bump.PATCH in kinds:
        return Bump.PATCH
    return Bump.NONE


def _actions_first_bump(paths: Iterable[str]) -> Bump:
    """Return `MINOR` when the tree holds a workflow or action file, else `NONE`.

    The first release of the actions series reads the whole tree. A data file
    alone starts nothing: the tag of the first release can't move or go, and
    `actions-v1.0.0` must mark the first file that a consumer can call. A tree
    with `versions.json` and no workflow or action file therefore gets no
    release, and the first file that a merge adds starts the series.
    """
    if any(matches_any(path, ACTIONS_FILE_PATTERNS) for path in paths):
        return Bump.MINOR
    return Bump.NONE


def _actions_kind(path: str) -> Bump:
    """Return the kind of release that one path asks of the actions series."""
    if matches_any(path, ACTIONS_FILE_PATTERNS):
        return Bump.MINOR
    if matches_any(path, ACTIONS_DATA_PATTERNS):
        return Bump.PATCH
    return Bump.NONE


HUB = Series(
    name="hub",
    prefix=HUB_PREFIX,
    label="rules changed",
    make_latest=True,
    bump_for_changes=_hub_bump,
    bump_for_first_release=_hub_first_bump,
)
"""The hub series: `v<major>.<minor>.<patch>`, the rules of the flake."""

ACTIONS = Series(
    name="actions",
    prefix=ACTIONS_PREFIX,
    label="workflow or action files changed",
    make_latest=False,
    bump_for_changes=_actions_bump,
    bump_for_first_release=_actions_first_bump,
)
"""The actions series: `actions-v<major>.<minor>.<patch>`, the called files."""

ALL_SERIES: tuple[Series, ...] = (HUB, ACTIONS)
"""Every series, the default first."""
