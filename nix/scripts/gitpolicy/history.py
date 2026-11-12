"""The questions that the Git policy asks git.

Each function runs read-only git commands through a `Runner` in the local
repository. None of them contacts a remote: the caller fetches the history
first.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from gitpolicy.vocabulary import DEFAULT_COMMENT
from release.runner import CommandError, Runner, command_runner

# The names that `git config` prints for the two aliases of the comment
# setting. Git writes the section and the variable name in lower case.
_COMMENT_SETTINGS = ("core.commentchar", "core.commentstring")

# The options that make `git log` print the same text on every machine: no
# signature check from `log.showSignature`, and UTF-8 whatever the setting
# `i18n.logOutputEncoding` says.
_STABLE_OUTPUT = ["--no-show-signature", "--encoding=UTF-8"]

# The pattern that selects the same two names, for `git config --get-regexp`.
_COMMENT_PATTERN = r"^core\.comment(char|string)$"


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
    a message with no valid encoding fails to decode. Two options make the text
    the same on every machine. `--no-show-signature` keeps the signature check
    that `log.showSignature` adds out of the output, and `--encoding=UTF-8`
    keeps `i18n.logOutputEncoding` from choosing another encoding.

    Raises:
        CommandError: Git cannot read the commit.
    """
    command = ["log", "-1", "--format=%B", *_STABLE_OUTPUT]
    try:
        return git([*command, "--end-of-options", sha]).rstrip("\n")
    except UnicodeDecodeError:
        return None


def _commits_one_by_one(git: Runner, revision_range: str) -> list[Commit]:
    """Return the commits of a range with one `git` command per message.

    This is the slow path. A message with bytes that are not UTF-8 fails the
    decoding of the whole output of a batch, so the caller falls back to this
    function, where such a message fails alone.

    Raises:
        CommandError: Git cannot read the range.
    """
    listing = git(
        ["rev-list", "--reverse", "--parents", "--end-of-options", revision_range]
    )
    commits: list[Commit] = []
    for line in listing.splitlines():
        sha, *parents = line.split()
        commits.append(Commit(sha, _read_message(git, sha), len(parents) > 1))
    return commits


def _commits_in_batch(git: Runner, revision_range: str) -> list[Commit]:
    """Return the commits of a range with one `git log` command.

    `-z` ends each commit with a NUL character. A NUL cannot be part of a
    message or of a hash, so the output splits into three fields per commit:
    the hash, the hashes of the parents and the message.

    Raises:
        CommandError: Git cannot read the range.
        UnicodeDecodeError: The message of some commit is not UTF-8 text.
    """
    output = git(
        ["log", "-z", "--reverse", "--format=%H%x00%P%x00%B", *_STABLE_OUTPUT]
        + ["--end-of-options", revision_range]
    )
    fields = output.split("\0")[:-1]  # the last field is empty: NUL ends a commit
    return [
        Commit(sha, message.rstrip("\n"), len(parents.split()) > 1)
        for sha, parents, message in zip(
            fields[0::3], fields[1::3], fields[2::3], strict=True
        )
    ]


def commits_in_range(git: Runner, revision_range: str) -> list[Commit]:
    """Return the commits of a range, the oldest first.

    The range holds every commit that its end reaches and its start does not,
    merge commits included. A range with no commit returns an empty list.
    One `git log` command reads all commits, so the cost of a long range is
    one process, not one per commit. If the output is not valid UTF-8, the
    function reads the commits again one by one, so that a message with such
    bytes becomes a problem of its own commit and the other commits are still
    checked.

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
    try:
        return _commits_in_batch(git, revision_range)
    except UnicodeDecodeError:
        return _commits_one_by_one(git, revision_range)


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
    wins. `git config --get-regexp` prints only the matching settings, in the
    order that Git reads them, so the function keeps the last. Settings that
    the function does not need never reach it: a value in another encoding
    cannot fail the decoding, and a secret in a URL is not read. It returns
    `#`, the default of Git, when neither is set. The value `auto` is returned
    as written: Git picks the character at the time of the commit, and nothing
    tells the caller which.

    Raises:
        CommandError: Git failed, for example when it is not installed.
    """
    try:
        listing = git(["config", "--null", "--get-regexp", _COMMENT_PATTERN])
    except CommandError as error:
        if error.stderr:
            raise
        return DEFAULT_COMMENT  # Git exits with 1 and prints nothing: no match
    value = DEFAULT_COMMENT
    for entry in listing.split("\0"):
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
