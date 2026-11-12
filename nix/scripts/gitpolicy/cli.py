"""The command line of the tool.

Usage:

    gitpolicy commit-msg FILE [--allow-autosquash]
    gitpolicy range A..B
    gitpolicy branch [NAME]

`commit-msg` checks the message in `FILE`, the way Git passes it to the
`commit-msg` hook. It reads the bytes of the file and decodes them as UTF-8
with no change of line ends, so a carriage return stays what Git sees. It then
cleans the text, as Git does when it records the message: the `commit.cleanup`
setting of the repository picks the mode, `strip` applies when the setting is
missing, and `core.commentChar` or `core.commentString` gives the string that
starts a comment line. `--allow-autosquash` lets a `fixup!`, `squash!` or
`amend!` header pass. `range` checks every commit that `B` reaches and `A` does
not, and it never lets such a header pass, because a commit that lands must
stand alone. `branch` checks `NAME`, or the checked-out branch when `NAME` is
missing. An empty `NAME` is a bad name, not a missing one. A `NAME` that starts
with `-` needs `--` before it, and the check then reports it as a bad name.
Every command runs `git` in the current directory.

Exit status: 0 when nothing is wrong, and for `--help`; 1 when a message or a
name breaks a rule; 2 for a usage error, a file that cannot be read, a failing
`git` command or a `git` command that prints text that is not UTF-8, such as a
branch name in another encoding; 3 for an internal error. Each problem is printed to
standard output on its own line, with the file, the commit or the branch in
front, and one run prints all of them.

An internal error is an exception that the tool does not expect, which means a
bug in the tool. The traceback goes to standard error. Status 1 stays reserved
for findings, so that a caller can tell a bug from a problem in the history.
"""

import argparse
import sys
import traceback
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from gitpolicy.branch import check_branch_name
from gitpolicy.cleanup import CleanupMode, clean_commit_message
from gitpolicy.commit import check_commit_message, check_stored_commit
from gitpolicy.history import (
    cleanup_setting,
    comment_setting,
    commits_in_range,
    current_branch,
    git_runner,
)
from gitpolicy.vocabulary import DEFAULT_COMMENT
from release.runner import CommandError, Runner

EXIT_CLEAN = 0
EXIT_PROBLEMS = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3

# The number of hexadecimal digits of a commit hash in the output.
_SHORT_SHA = 7


class UsageError(Exception):
    """The command line is wrong, not the message or the name that it checks."""


class _HelpShown(Exception):
    """The parser printed the help text, so the run is over and nothing is wrong."""


class _Parser(argparse.ArgumentParser):
    """An argument parser that raises instead of exiting.

    A usage error raises `UsageError`. The help option prints the help text and
    raises `_HelpShown`. Abbreviations of options are off: an option is
    spelled in full, so `--he` is an error and not `--help`.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Create the parser with abbreviations of options turned off."""
        super().__init__(allow_abbrev=False, **kwargs)

    def error(self, message: str) -> NoReturn:
        """Raise `UsageError` with the usage text and the problem."""
        raise UsageError(f"{self.format_usage().strip()}\n{self.prog}: {message}")

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        """Raise `_HelpShown`: `argparse` exits only after it printed the help."""
        raise _HelpShown


@dataclass(frozen=True)
class CommitMsgArgs:
    """The validated arguments of `commit-msg`.

    Attributes:
        path: The message file.
        allow_autosquash: Whether an autosquash header passes.
    """

    path: Path
    allow_autosquash: bool


@dataclass(frozen=True)
class RangeArgs:
    """The validated arguments of `range`.

    Attributes:
        revision_range: A range of the form `A..B`, checked by `_require_range`.
    """

    revision_range: str


@dataclass(frozen=True)
class BranchArgs:
    """The validated arguments of `branch`.

    Attributes:
        name: The branch name. It is `None` when no name was given, which means
            the checked-out branch. An empty string is a name that was given,
            and a bad one.
    """

    name: str | None


Args = CommitMsgArgs | RangeArgs | BranchArgs


def _parse(argv: Sequence[str]) -> Args:
    """Parse the arguments.

    Raises:
        UsageError: The command is missing or unknown, an argument is missing,
            an option is unknown, or the range is not of the form `A..B`.
    """
    parser = _Parser(
        prog="gitpolicy",
        description="Check commit messages and branch names against the Git policy.",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    message = commands.add_parser(
        "commit-msg", help="check the message in a file, as the commit-msg hook does"
    )
    message.add_argument("target", metavar="FILE", help="the message file")
    message.add_argument(
        "--allow-autosquash",
        action="store_true",
        help="let a fixup!, squash! or amend! header pass",
    )
    revisions = commands.add_parser(
        "range", help="check every commit that B reaches and A does not"
    )
    revisions.add_argument("target", metavar="A..B", help="the range of commits")
    branch = commands.add_parser("branch", help="check a branch name")
    branch.add_argument(
        "target",
        nargs="?",
        default=None,
        metavar="NAME",
        help="the branch name (default: the checked-out branch)",
    )
    parsed = parser.parse_args(argv)
    if parsed.command == "commit-msg":
        return CommitMsgArgs(Path(parsed.target), parsed.allow_autosquash)
    if parsed.command == "range":
        _require_range(parsed.target)
        return RangeArgs(parsed.target)
    return BranchArgs(parsed.target)


def _require_range(target: str) -> None:
    """Require a range of the form `A..B`: two revisions that are not options.

    Raises:
        UsageError: The text has no `..`, has `...`, has an empty side, or a
            side starts with `-`, which Git would read as an option.
    """
    start, dots, end = target.partition("..")
    if not dots or "..." in target or not start or not end:
        raise UsageError(f"the range must be of the form A..B, not {target}")
    if start.startswith("-") or end.startswith("-"):
        raise UsageError(f"a revision of the range must not start with '-': {target}")


def _cleanup_mode(git: Runner) -> CleanupMode:
    """Return the cleanup mode that the repository sets for `git commit`.

    A missing setting and the value `default` give `STRIP`: that is the default
    of Git for a message that an editor writes, the usual case of the hook.

    Raises:
        UsageError: The setting has a value that Git does not define.
        CommandError: Git cannot read the configuration.
    """
    setting = cleanup_setting(git)
    if setting == "default":
        return CleanupMode.STRIP
    try:
        return CleanupMode(setting)
    except ValueError as error:
        raise UsageError(f"commit.cleanup has the unknown value '{setting}'") from error


def _comment_string(git: Runner, mode: CleanupMode) -> str:
    """Return the string that starts a comment line in the message file.

    The mode `VERBATIM` keeps every line, so no string matters and the default
    returns. Otherwise the string comes from `core.commentChar` or
    `core.commentString`. The value `auto` has no answer: Git picks a character
    for the commit, from the first characters of the lines of the message, and
    does not tell the hook which one it picked.

    Raises:
        UsageError: The setting is `auto` or empty.
        CommandError: Git cannot read the configuration.
    """
    if mode is CleanupMode.VERBATIM:
        return DEFAULT_COMMENT
    setting = comment_setting(git)
    if setting == "auto":
        raise UsageError(
            "core.commentChar is 'auto': Git picks the comment character when "
            "it commits and the hook cannot learn it; set core.commentChar to "
            "a fixed character, or commit.cleanup to 'verbatim'"
        )
    if not setting:
        raise UsageError("core.commentChar is empty: Git needs at least one character")
    return setting


def _check_file(git: Runner, path: Path, *, allow_autosquash: bool) -> list[str]:
    """Return the lines to print for the message in a file.

    The file is read as bytes and decoded as UTF-8, so no line end changes. A
    text mode read would turn a lone carriage return into a line end, and the
    tool would see a line that Git does not see.

    Raises:
        OSError: The file cannot be read.
        UsageError: The file is not UTF-8 text, `commit.cleanup` is unknown, or
            the comment setting has no usable value.
        CommandError: Git cannot read the configuration.
    """
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        raise UsageError(f"{path} is not UTF-8 text") from error
    mode = _cleanup_mode(git)
    message = clean_commit_message(text, mode, _comment_string(git, mode))
    return [
        f"{path}: {problem}"
        for problem in check_commit_message(message, allow_autosquash=allow_autosquash)
    ]


def _check_range(git: Runner, revision_range: str) -> list[str]:
    """Return the lines to print for the commits of a range.

    Raises:
        CommandError: Git cannot read the range.
    """
    return [
        f"{commit.sha[:_SHORT_SHA]}: {problem}"
        for commit in commits_in_range(git, revision_range)
        for problem in check_stored_commit(commit.message, is_merge=commit.is_merge)
    ]


def _check_branch(git: Runner, name: str | None) -> list[str]:
    """Return the lines to print for a branch name.

    Args:
        git: The runner of git, used when `name` is `None`.
        name: The branch name, or `None` for the checked-out branch. An empty
            string is a name, and the check rejects it.

    Raises:
        UsageError: `name` is `None` and HEAD is detached.
        CommandError: Git cannot name the checked-out branch.
    """
    branch = current_branch(git) if name is None else name
    if branch is None:
        raise UsageError("HEAD is detached: pass the branch name")
    return [f"{branch}: {problem}" for problem in check_branch_name(branch)]


def _run(args: Args, git: Runner) -> list[str]:
    """Run the command and return the lines to print, one per problem.

    Raises:
        UsageError: An argument of the command or `commit.cleanup` is wrong.
        OSError: The message file cannot be read.
        CommandError: A git command failed.
    """
    match args:
        case CommitMsgArgs(path, allow_autosquash):
            return _check_file(git, path, allow_autosquash=allow_autosquash)
        case RangeArgs(revision_range):
            return _check_range(git, revision_range)
        case BranchArgs(name):
            return _check_branch(git, name)


def main(argv: Sequence[str] | None = None, *, git: Runner | None = None) -> int:
    """Run a command and return the exit status.

    Args:
        argv: The arguments after the program name. `None` reads `sys.argv`.
        git: The runner of git. `None` runs `git` in the current directory.

    Returns:
        `EXIT_CLEAN`, `EXIT_PROBLEMS`, `EXIT_USAGE` or `EXIT_INTERNAL`. An
        exception that no other clause handles is a bug in the tool: its
        traceback goes to standard error and the status is `EXIT_INTERNAL`.
    """
    try:
        args = _parse(sys.argv[1:] if argv is None else argv)
        lines = _run(args, git or git_runner())
    except _HelpShown:
        return EXIT_CLEAN
    except UsageError as error:
        print(error, file=sys.stderr)
        return EXIT_USAGE
    except (OSError, CommandError) as error:
        print(f"gitpolicy: {error}", file=sys.stderr)
        return EXIT_USAGE
    except UnicodeDecodeError as error:
        print(
            f"gitpolicy: a git command printed text that is not UTF-8: {error}",
            file=sys.stderr,
        )
        return EXIT_USAGE
    except Exception:  # the last resort: report any bug with its trace
        traceback.print_exc()
        print("gitpolicy: internal error, the traceback is above", file=sys.stderr)
        return EXIT_INTERNAL
    for line in lines:
        print(line)
    if lines:
        print(f"gitpolicy: {len(lines)} problem(s)", file=sys.stderr)
        return EXIT_PROBLEMS
    return EXIT_CLEAN
