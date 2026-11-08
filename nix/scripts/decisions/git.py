"""The `git` commands that retiring a record needs.

Every function runs `git -C <root>` as a child process and reads the local
repository only. None of them contacts a remote: `git fetch` is the job of the
caller's user.
"""

import subprocess
from pathlib import Path


class GitError(Exception):
    """A `git` command failed, or `git` is not installed."""


def run_git(root: Path, *args: str) -> str:
    """Run `git -C root args` and return its standard output.

    Args:
        root: A directory inside the repository.
        *args: The git arguments, after `-C root`.

    Returns:
        The standard output, decoded as UTF-8.

    Raises:
        GitError: `git` is missing, or it exits with a nonzero status. The
            message holds the arguments and the standard error of git.
    """
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
    except FileNotFoundError as error:
        raise GitError("git is not installed or not on PATH") from error
    if completed.returncode != 0:
        command = " ".join(args)
        raise GitError(f"git {command} failed: {completed.stderr.strip()}")
    return completed.stdout


def toplevel(directory: Path) -> Path:
    """Return the root of the work tree that holds `directory`.

    Raises:
        GitError: `directory` is not inside a git work tree.
    """
    return Path(run_git(directory, "rev-parse", "--show-toplevel").strip())


def remote_url(root: Path, name: str) -> str:
    """Return the URL of the remote `name`, after `url.*.insteadOf` rewrites.

    Raises:
        GitError: The repository has no remote of that name.
    """
    return run_git(root, "remote", "get-url", name).strip()


def ref_exists(root: Path, ref: str) -> bool:
    """Tell whether `ref` names a commit in the local repository."""
    try:
        run_git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    except GitError:
        return False
    return True


def last_commit(root: Path, ref: str, path: str) -> str | None:
    """Return the last commit on `ref` that changed `path`.

    This is `git log -1 --format=%H <ref> -- <path>`. For a file that a later
    commit deleted, the commit is the deleting one.

    Returns:
        The full 40-character hash, or `None` when no commit on `ref` touches
        the path.
    """
    output = run_git(root, "log", "-1", "--format=%H", ref, "--", path).strip()
    return output or None


def has_local_changes(root: Path, path: str) -> bool:
    """Tell whether `path` has staged, unstaged or untracked changes."""
    return bool(run_git(root, "status", "--porcelain", "--", path).strip())


def blob_id(root: Path, revision: str, path: str) -> str:
    """Return the id of the file `path` in `revision`.

    Raises:
        GitError: The revision has no such file.
    """
    return run_git(root, "rev-parse", f"{revision}:{path}").strip()


def earlier_paths(root: Path, path: str) -> list[str]:
    """Return the names that the file `path` had in the history of `HEAD`.

    This follows renames with `git log --follow`, which includes commits that
    no remote has. A copy is not a rename and is not followed.

    Returns:
        The older paths, the most recent first. The list is empty for a file
        that was never renamed, and for a file that no commit holds.

    Raises:
        GitError: `git log` fails, for example because `HEAD` has no commit.
    """
    output = run_git(
        root,
        "log",
        "--follow",
        "-M",
        "--name-status",
        "-z",
        "--format=",
        "HEAD",
        "--",
        path,
    )
    tokens = output.split("\0")
    paths: list[str] = []
    index = 0
    while index < len(tokens) and tokens[index]:
        # `R<score>` has an old and a new path; `A`, `M` and `D` have one.
        if tokens[index].startswith("R"):
            paths.append(tokens[index + 1])
            index += 3
        else:
            index += 2
    return paths


def remove_file(root: Path, path: str) -> None:
    """Delete `path` from the work tree and stage the deletion (`git rm`).

    Raises:
        GitError: Git refuses, for example because the file has changes.
    """
    run_git(root, "rm", "--quiet", "--", path)


def stage_file(root: Path, path: str) -> None:
    """Stage the whole work tree text of `path` in the index (`git add`).

    Raises:
        GitError: Git refuses, for example because another process holds the
            index lock.
    """
    run_git(root, "add", "--", path)


def restore_file(root: Path, path: str) -> None:
    """Put `path` back as `HEAD` has it, in the index and in the work tree.

    Raises:
        GitError: Git refuses, or `HEAD` has no such file.
    """
    run_git(root, "restore", "--source=HEAD", "--staged", "--worktree", "--", path)
