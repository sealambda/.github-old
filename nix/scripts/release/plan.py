"""Plan the release of one commit. Planning has no side effect."""

from dataclasses import dataclass

from release import repo
from release.notes import render_notes
from release.paths import rules_changed
from release.runner import Runner
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
class Plan:
    """The release that a commit gets.

    Attributes:
        commit: The full hash of the commit to tag.
        tag: The tag of the release.
        previous: The previous release tag, `None` for the first release.
        rules_changed: The answer that the first line of the notes holds.
        notes: The text of the release.
    """

    commit: str
    tag: str
    previous: str | None
    rules_changed: bool
    notes: str


def _answer_since(git: Runner, commit: str, previous: Version | None) -> bool:
    """Tell whether the rules changed between `previous` and `commit`.

    The first release (`previous` is `None`) has nothing to compare with, so
    its answer is `True`.
    """
    if previous is None:
        return True
    return rules_changed(repo.changed_paths(git, previous.tag, commit))


def _make_plan(
    git: Runner, commit: str, previous: Version | None, changed: bool, tag: str
) -> Plan:
    """Build the plan of the release `tag` for `commit`.

    The notes list the subject of each commit after `previous`.
    """
    base = None if previous is None else previous.tag
    subjects = repo.commit_subjects(git, base, commit)
    return Plan(commit, tag, base, changed, render_notes(changed, subjects))


def plan_release(git: Runner, revision: str) -> Plan | AlreadyReleased | Covered:
    """Decide what releasing a commit means.

    The previous release is the highest release tag merged into the commit. The
    answer `rules changed` is `yes` for the first release, and otherwise it
    comes from the paths that differ between the previous release and the
    commit (`release.paths`). The notes list the subject of each commit since
    the previous release.

    Args:
        git: The runner of git in the repository to release.
        revision: A name for the commit, such as `HEAD` or a hash.

    Returns:
        `AlreadyReleased` when the commit carries a release tag. `Covered`
        when no tag points at the commit but a release tag contains it, which
        happens when a run for an older commit starts after a newer release. A
        `Plan` otherwise.

    Raises:
        ReleaseError: The new tag exists on a commit that does not contain
            the commit, for example on another branch.
        CommandError: A git command failed, for example because `revision`
            names no commit.
    """
    commit = repo.resolve_commit(git, revision)
    carried = highest_release(repo.tags_at(git, commit))
    if carried is not None:
        return AlreadyReleased(commit, carried.tag)
    covering = lowest_release(repo.tags_containing(git, commit))
    if covering is not None:
        return Covered(commit, covering.tag)

    previous = highest_release(repo.tags_merged_into(git, commit))
    changed = _answer_since(git, commit, previous)
    tag = next_version(previous, changed).tag
    holder = repo.tag_commit(git, tag)
    if holder is not None:
        raise ReleaseError(
            f"the tag {tag} exists on commit {holder}, which does not contain "
            f"{commit}: the version {tag} is taken"
        )
    return _make_plan(git, commit, previous, changed, tag)


def plan_for_existing_tag(git: Runner, released: AlreadyReleased) -> Plan:
    """Plan the release for a tag that a commit already carries.

    The tag stays what it is. The previous release is the highest release tag
    among the ancestors of the commit, so a second release tag on the same
    commit is not the previous release. The answer and the notes come from
    that previous release, the same as for a new tag.

    Args:
        git: The runner of git in the repository to release.
        released: The commit and its tag, from `plan_release`.

    Raises:
        CommandError: A git command failed.
    """
    at_commit = set(repo.tags_at(git, released.commit))
    ancestors = set(repo.tags_merged_into(git, released.commit)) - at_commit
    previous = highest_release(ancestors)
    changed = _answer_since(git, released.commit, previous)
    return _make_plan(git, released.commit, previous, changed, released.tag)
