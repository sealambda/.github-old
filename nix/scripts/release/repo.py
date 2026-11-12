"""The questions that a release plan asks git.

Each function runs read-only git commands through a `Runner` in the local
repository. None of them contacts a remote: the caller fetches the history and
the tags first.
"""

from release.runner import Runner


def resolve_commit(git: Runner, revision: str) -> str:
    """Return the full hash of the commit that `revision` names.

    Raises:
        CommandError: The revision does not name a commit.
    """
    return git(["rev-parse", "--verify", f"{revision}^{{commit}}"]).strip()


def tags_at(git: Runner, commit: str) -> list[str]:
    """Return the names of the tags that point at `commit`.

    An annotated tag counts: git peels it to its commit.
    """
    return git(["tag", "--points-at", commit]).split()


def tags_merged_into(git: Runner, commit: str) -> list[str]:
    """Return the names of the tags whose commit is `commit` or an ancestor."""
    return git(["tag", "--merged", commit]).split()


def tags_containing(git: Runner, commit: str) -> list[str]:
    """Return the names of the tags whose commit is `commit` or a descendant."""
    return git(["tag", "--contains", commit]).split()


def tag_commit(git: Runner, tag: str) -> str | None:
    """Return the commit that the tag `tag` points at, `None` if no tag has it."""
    if not git(["tag", "--list", tag]).strip():
        return None
    return git(["rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"]).strip()


def changed_paths(git: Runner, base: str, commit: str) -> list[str]:
    """Return the paths that differ between two commits.

    Renames are not detected, so a renamed file lists both its old and its new
    path. A path is relative to the root of the repository.
    """
    output = git(["diff", "--name-only", "--no-renames", "-z", base, commit])
    return [path for path in output.split("\0") if path]


def tree_paths(git: Runner, commit: str) -> list[str]:
    """Return the paths of all files in the tree of `commit`.

    A path is relative to the root of the repository. A submodule counts as one
    path.
    """
    output = git(["ls-tree", "-r", "--name-only", "--full-tree", "-z", commit])
    return [path for path in output.split("\0") if path]


def commit_subjects(git: Runner, base: str | None, commit: str) -> list[str]:
    """Return the subject line of each commit after `base` up to `commit`.

    Args:
        git: The runner of git.
        base: The commit to start after, or `None` for the whole history of
            `commit`.
        commit: The last commit.

    Returns:
        The subjects, the newest first.
    """
    revisions = commit if base is None else f"{base}..{commit}"
    return git(["log", "--format=%s", revisions]).splitlines()
