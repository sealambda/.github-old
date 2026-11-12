"""Plan the release of one commit in one series. Planning has no side effect."""

from dataclasses import dataclass

from release import repo
from release.notes import render_notes
from release.runner import Runner
from release.series import Bump, Series
from release.tags import Version, highest_release, lowest_release, next_version


class ReleaseError(Exception):
    """The commit cannot be released as the rules require."""


@dataclass(frozen=True)
class AlreadyReleased:
    """The commit carries a release tag.

    The tag says nothing about the GitHub release: the release can be missing
    (`release.publish.ensure_release` checks and repairs that).

    Attributes:
        commit: The full hash of the commit.
        tag: The tag of the commit. A commit with several release tags
            reports the highest.
    """

    commit: str
    tag: str


@dataclass(frozen=True)
class Covered:
    """A release tag on a later commit already covers the commit.

    The release of that later commit lists the commits since its own previous
    release, so it lists this commit. Another release for this commit would
    make a tag that sorts above its place in the history.

    Attributes:
        commit: The full hash of the commit.
        tag: The release tag that contains the commit. When several tags
            contain it, this is the lowest.
    """

    commit: str
    tag: str


@dataclass(frozen=True)
class NoRelease:
    """The commit changes no path that the series releases.

    Only a series that has paths of its own returns this (the actions series).
    It is not an error: the commit belongs to no release of that series.

    Attributes:
        commit: The full hash of the commit.
        previous: The previous release tag of the series, `None` when the
            series has no release and the tree holds no file that starts it.
    """

    commit: str
    previous: str | None


@dataclass(frozen=True)
class Plan:
    """The release that a commit gets.

    Attributes:
        commit: The full hash of the commit to tag.
        tag: The tag of the release.
        previous: The previous release tag, `None` for the first release.
        rules_changed: The answer that the first line of the notes holds. For
            the actions series it answers whether a workflow or action file
            changed.
        notes: The text of the release.
        make_latest: Whether the release takes the "latest" label on GitHub.
    """

    commit: str
    tag: str
    previous: str | None
    rules_changed: bool
    notes: str
    make_latest: bool = True


def _previous_tag(series: Series, previous: Version | None) -> str | None:
    """Return the tag name of the previous release, `None` for the first."""
    return None if previous is None else previous.tag_with(series.prefix)


def _bump_since(
    git: Runner, series: Series, commit: str, previous: Version | None
) -> Bump:
    """Return the kind of release that `commit` asks of `series`.

    The first release (`previous` is `None`) has no commit to compare with, so
    the rule reads the paths of the whole tree of `commit`.
    """
    if previous is None:
        return series.bump_for_first_release(repo.tree_paths(git, commit))
    base = previous.tag_with(series.prefix)
    return series.bump_for_changes(repo.changed_paths(git, base, commit))


def _make_plan(
    git: Runner,
    series: Series,
    commit: str,
    previous: Version | None,
    changed: bool,
    tag: str,
) -> Plan:
    """Build the plan of the release `tag` of `series` for `commit`.

    The notes list the subject of each commit after `previous`.
    """
    base = _previous_tag(series, previous)
    subjects = repo.commit_subjects(git, base, commit)
    notes = render_notes(changed, subjects, label=series.label)
    return Plan(commit, tag, base, changed, notes, series.make_latest)


def plan_release(
    git: Runner, revision: str, series: Series
) -> Plan | AlreadyReleased | Covered | NoRelease:
    """Decide what releasing a commit means in a series.

    The previous release is the highest tag of the series merged into the
    commit. The kind of release comes from the rule of the series: for the first
    release it reads the tree, and otherwise the paths that differ between the
    previous release and the commit (`release.series`). The notes list the
    subject of each commit since the previous release. Tags of the other series
    never count.

    Args:
        git: The runner of git in the repository to release.
        revision: A name for the commit, such as `HEAD` or a hash.
        series: The series to release. It has no default, so a caller can't
            plan the hub series by omission.

    Returns:
        `AlreadyReleased` when the commit carries a tag of the series.
        `Covered` when no tag points at the commit but a tag of the series
        contains it, which happens when a run for an older commit starts after
        a newer release. `NoRelease` when the rule of the series asks for no
        release. A `Plan` otherwise.

    Raises:
        ReleaseError: The new tag exists on a commit that does not contain
            the commit, for example on another branch.
        CommandError: A git command failed, for example because `revision`
            names no commit.
    """
    commit = repo.resolve_commit(git, revision)
    carried = highest_release(repo.tags_at(git, commit), series.prefix)
    if carried is not None:
        return AlreadyReleased(commit, carried.tag_with(series.prefix))
    covering = lowest_release(repo.tags_containing(git, commit), series.prefix)
    if covering is not None:
        return Covered(commit, covering.tag_with(series.prefix))

    previous = highest_release(repo.tags_merged_into(git, commit), series.prefix)
    bump = _bump_since(git, series, commit, previous)
    if bump is Bump.NONE:
        return NoRelease(commit, _previous_tag(series, previous))
    changed = bump is Bump.MINOR
    tag = next_version(previous, changed).tag_with(series.prefix)
    holder = repo.tag_commit(git, tag)
    if holder is not None:
        raise ReleaseError(
            f"the tag {tag} exists on commit {holder}, which does not contain "
            f"{commit}: the version {tag} is taken"
        )
    return _make_plan(git, series, commit, previous, changed, tag)


def plan_for_existing_tag(
    git: Runner, released: AlreadyReleased, series: Series
) -> Plan:
    """Plan the release for a tag that a commit already carries.

    The tag stays what it is. The previous release is the highest tag of the
    series among the ancestors of the commit, so a second tag on the same
    commit is not the previous release. The answer and the notes come from that
    previous release, the same as for a new tag. When the rule of the series
    asks for no release, the answer is `no`: the tag exists and needs a release.

    Args:
        git: The runner of git in the repository to release.
        released: The commit and its tag, from `plan_release`.
        series: The series of the tag.

    Raises:
        CommandError: A git command failed.
    """
    at_commit = set(repo.tags_at(git, released.commit))
    ancestors = set(repo.tags_merged_into(git, released.commit)) - at_commit
    previous = highest_release(ancestors, series.prefix)
    bump = _bump_since(git, series, released.commit, previous)
    return _make_plan(
        git, series, released.commit, previous, bump is Bump.MINOR, released.tag
    )
