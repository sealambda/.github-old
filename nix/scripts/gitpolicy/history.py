"""The questions that the Git policy asks git.

Each function runs read-only git commands through a `Runner` in the local
repository. None of them contacts a remote: the caller fetches the history
first.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from gitpolicy.vocabulary import DEFAULT_COMMENT
from release.runner import Runner, command_runner

# The names that `git config --list` prints for the two aliases of the comment
# setting. Git writes the section and the variable name in lower case.
_COMMENT_SETTINGS = ("core.commentchar", "core.commentstring")


@dataclass(frozen=True)
class Commit:
    """One commit of a range.

    Attributes:
        sha: The full hash of the commit.
        message: The message as Git stores it, without the final newline, or
            `None` when its bytes are not valid UTF-8 text.
        is_merge: Whether the commit has more than one parent.
    """

    sha: str
    message: str | None
    is_merge: bool


def git_runner(prefix: Sequence[str] = ("git",)) -> Runner:
    """Build the runner of git for the Git policy.

    The runner decodes the output of git as strict UTF-8 and raises
    `UnicodeDecodeError` for bytes that are not text. The shared runner of the
    release tool replaces such bytes by default. The Git policy needs the
    exception instead: a message that is not UTF-8 is a finding of its own
    commit, which `_read_message` turns into `None`. The command line and the
    tests build every runner of git with this function.

    Args:
        prefix: The program and the arguments that every call starts with.
    """
    return command_runner(prefix, errors="strict")


def _read_message(git: Runner, sha: str) -> str | None:
    """Return the stored message of a commit, `None` if it is not UTF-8 text.

    Git re-encodes a message that declares another encoding to UTF-8, so only
    a message with no valid encoding fails to decode.

    Raises:
        CommandError: Git cannot read the commit.
    """
    try:
        return git(["log", "-1", "--format=%B", "--end-of-options", sha]).rstrip("\n")
    except UnicodeDecodeError:
        return None


def commits_in_range(git: Runner, revision_range: str) -> list[Commit]:
    """Return the commits of a range, the oldest first.

    The range holds every commit that its end reaches and its start does not,
    merge commits included. A range with no commit returns an empty list.
    One `git` command lists the commits and one more reads each message, so
    that a message with bytes that are not UTF-8 fails alone.

    `--end-of-options` ends the options before the range, so a range that
    starts with `-` is a revision for Git, never an option. Git 2.24 added the
    option, and the hub's Git is newer.

    Args:
        git: The runner of git.
        revision_range: A range of the form `A..B`.

    Raises:
        CommandError: Git cannot read the range, for example when a revision
            does not exist.
    """
    listing = git(
        ["rev-list", "--reverse", "--parents", "--end-of-options", revision_range]
    )
    commits: list[Commit] = []
    for line in listing.splitlines():
        sha, *parents = line.split()
        commits.append(Commit(sha, _read_message(git, sha), len(parents) > 1))
    return commits


def cleanup_setting(git: Runner) -> str:
    """Return the value of `commit.cleanup`, or `default` when it is not set.

    The value is returned as written. Git merges its system, user and
    repository configuration files, and the repository wins.

    Raises:
        CommandError: Git failed, for example when it is not installed.
    """
    return git(["config", "--default", "default", "--get", "commit.cleanup"]).strip()


def comment_setting(git: Runner) -> str:
    """Return the string that `core.commentChar` or `core.commentString` sets.

    The two names are aliases of one setting, and the one that Git reads last
    wins, so the function reads all settings in the order that Git reads them
    and keeps the last of the two. It returns `#`, the default of Git, when
    neither is set. The value `auto` is returned as written: Git picks the
    character at the time of the commit, and nothing tells the caller which.

    Raises:
        CommandError: Git failed, for example when it is not installed.
    """
    value = DEFAULT_COMMENT
    for entry in git(["config", "--null", "--list"]).split("\0"):
        name, _, setting = entry.partition("\n")
        if name in _COMMENT_SETTINGS:
            value = setting
    return value


def current_branch(git: Runner) -> str | None:
    """Return the name of the checked-out branch, `None` for a detached HEAD.

    Raises:
        CommandError: Git failed, for example outside a repository.
    """
    return git(["branch", "--show-current"]).strip() or None
