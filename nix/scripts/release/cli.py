"""The command line of the tool.

Usage:

    release plan [--commit REVISION]
    release publish [--commit REVISION]

`REVISION` is a name for a commit and defaults to `HEAD`. Both commands run in
the git repository of the current directory.

`plan` prints the tag, the commit, the previous release and the notes of the
release that the commit gets. It changes nothing and does not call `gh`.
`publish` creates the GitHub release, and with it the tag, at the commit. It
needs `gh`, and `gh` reads `GH_TOKEN` and `GH_REPO` from the environment.

Two cases get no new tag. A commit that a later release tag contains is
covered by that release: both commands say so and exit 0. A commit that
carries a release tag is released: `plan` says so, and `publish` asks GitHub
whether the release for the tag exists. It exits 0 when it does, and it
creates the missing release for the existing tag when it does not.

Exit status: 0 for success, 1 when the release cannot be made (a command failed,
the new tag exists on a commit that does not contain this one, or the tag on
GitHub names another commit after `publish` created the release), 2 for a
usage error, 3 for an internal error. The message goes to standard error for
status 1 and above.

An internal error is an exception that the tool does not expect, which means a
bug in the tool. The traceback goes to standard error.
"""

import argparse
import sys
import traceback
from collections.abc import Sequence
from dataclasses import dataclass
from typing import NoReturn

from release.plan import AlreadyReleased, Covered, Plan, ReleaseError, plan_release
from release.publish import ensure_release, publish_release
from release.runner import CommandError, Runner, command_runner

EXIT_OK = 0
EXIT_CANNOT_RELEASE = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3


class UsageError(Exception):
    """The command line is wrong."""


class _Parser(argparse.ArgumentParser):
    """An argument parser that raises `UsageError` instead of exiting."""

    def error(self, message: str) -> NoReturn:
        """Raise `UsageError` with the usage text and the problem."""
        raise UsageError(f"{self.format_usage().strip()}\n{self.prog}: {message}")


@dataclass(frozen=True)
class Args:
    """The validated arguments.

    Attributes:
        command: `plan` or `publish`.
        commit: The revision of the commit to release.
    """

    command: str
    commit: str


def _parse(argv: Sequence[str]) -> Args:
    """Parse the arguments.

    Raises:
        UsageError: The command is missing or unknown, or an option is wrong.
    """
    parser = _Parser(
        prog="release",
        description="Plan or create the release of a commit of the hub.",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for name, summary in (
        ("plan", "print the release that the commit gets, and change nothing"),
        ("publish", "create the GitHub release and its tag at the commit"),
    ):
        command = commands.add_parser(name, help=summary, description=summary)
        command.add_argument(
            "--commit",
            default="HEAD",
            metavar="REVISION",
            help="the commit to release (default: HEAD)",
        )
    parsed = parser.parse_args(argv)
    return Args(parsed.command, parsed.commit)


def _describe(plan: Plan) -> str:
    """Return the text that `plan` prints for a new release."""
    previous = "none" if plan.previous is None else plan.previous
    return (
        f"tag: {plan.tag}\n"
        f"commit: {plan.commit}\n"
        f"previous release: {previous}\n"
        f"--- notes ---\n{plan.notes}"
    )


def _run_for_tagged_commit(
    args: Args, git: Runner, gh: Runner, released: AlreadyReleased
) -> str:
    """Return the text for a commit that carries a release tag.

    `plan` only reports. `publish` asks GitHub for the release of the tag and
    creates it when it is missing.

    Raises:
        CommandError: A git or `gh` command failed.
    """
    done = f"commit {released.commit} is already released as {released.tag}\n"
    if args.command == "plan" or not ensure_release(gh, git, released):
        return done
    return (
        f"commit {released.commit} carries the tag {released.tag} without a "
        f"release: created the release for the existing tag\n"
    )


def _run(args: Args, git: Runner, gh: Runner) -> str:
    """Run the command and return the text to print.

    Raises:
        ReleaseError: The new tag exists on a commit that does not contain the
            commit to release.
        CommandError: A git or `gh` command failed.
    """
    outcome = plan_release(git, args.commit)
    if isinstance(outcome, Covered):
        return f"commit {outcome.commit} is covered by release {outcome.tag}\n"
    if isinstance(outcome, AlreadyReleased):
        return _run_for_tagged_commit(args, git, gh, outcome)
    if args.command == "plan":
        return _describe(outcome)
    publish_release(gh, outcome)
    return f"released {outcome.tag} at commit {outcome.commit}\n"


def main(
    argv: Sequence[str] | None = None,
    *,
    git: Runner | None = None,
    gh: Runner | None = None,
) -> int:
    """Run a command and return the exit status.

    Args:
        argv: The arguments after the program name. `None` reads `sys.argv`.
        git: The runner of git. `None` runs `git` in the current directory.
        gh: The runner of `gh`. `None` runs `gh`.

    Returns:
        `EXIT_OK`, `EXIT_CANNOT_RELEASE`, `EXIT_USAGE` or `EXIT_INTERNAL`. An
        exception that no other clause handles is a bug in the tool: its
        traceback goes to standard error and the status is `EXIT_INTERNAL`.
    """
    try:
        args = _parse(sys.argv[1:] if argv is None else argv)
        text = _run(args, git or command_runner(["git"]), gh or command_runner(["gh"]))
    except UsageError as error:
        print(error, file=sys.stderr)
        return EXIT_USAGE
    except (ReleaseError, CommandError) as error:
        print(f"release: {error}", file=sys.stderr)
        return EXIT_CANNOT_RELEASE
    except Exception:  # the last resort: report any bug with its trace
        traceback.print_exc()
        print("release: internal error, the traceback is above", file=sys.stderr)
        return EXIT_INTERNAL
    print(text, end="")
    return EXIT_OK
