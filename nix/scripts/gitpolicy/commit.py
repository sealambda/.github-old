"""The rules for a commit message.

The header follows the Conventional Commits 1.0.0 grammar, `type(scope)!:
description`, with the hub's limits: the type comes from one list in lower
case, the header has at most 100 characters and no final period, and a blank
line separates the header from the body. `check_commit_message` and
`check_stored_commit` are pure functions: they read their arguments and return
the problems, and they never read Git.
"""

import re

from gitpolicy.vocabulary import (
    AUTOSQUASH_PREFIXES,
    COMMIT_TYPES,
    HEADER_LIMIT,
    REVERT_TYPE,
)

# `type`, an optional `(scope)`, an optional `!` and the colon. What follows
# the colon is the description, checked apart so that each fault gets its own
# message. A type has no space, parenthesis, colon or exclamation mark.
_HEADER_START = re.compile(
    r"(?P<type>[^\s():!]+)"  # the type
    r"(?:\((?P<scope>[^()]*)\))?"  # the optional scope, with its parentheses
    r"!?:"  # the optional breaking-change mark and the colon
    r"(?P<rest>.*)"  # the description, with its leading space
)

# A scope is a lower-case noun: words of letters and digits that one hyphen,
# underscore, dot or slash separates, such as `ci`, `nix/lib` or `docs-site`.
_SCOPE = re.compile(r"[a-z0-9]+(?:[-_./][a-z0-9]+)*")

# The header that `git revert` writes by default.
_GIT_REVERT_START = 'Revert "'

# The start of the header that `git merge` and `git pull` write: `Merge branch`,
# `Merge remote-tracking branch`, `Merge pull request` and `Merge tag`.
_GIT_MERGE_START = "Merge "

_FORM = "the header must be 'type(scope)!: description'"

# What a person does about a merge commit. The hook and `range` both give it.
_MERGE_ADVICE = (
    "rebase the branch onto its base so that the history stays linear (the "
    "'Update branch' button of GitHub creates a merge commit; use its rebase "
    "option, or rebase locally)"
)


def _check_type(commit_type: str) -> list[str]:
    """Return the problem of a type that is not in the list, or nothing."""
    if commit_type in COMMIT_TYPES:
        return []
    return [f"the type '{commit_type}' must be one of: {', '.join(COMMIT_TYPES)}"]


def _check_scope(scope: str | None) -> list[str]:
    """Return the problem of a scope that is empty or malformed, or nothing.

    Args:
        scope: The text between the parentheses, or `None` when the header has
            none.
    """
    if scope is None or _SCOPE.fullmatch(scope):
        return []
    return [
        f"the scope '{scope}' must be lower-case words of letters and digits, "
        "joined by '-', '_', '.' or '/'"
    ]


def _check_description(rest: str) -> list[str]:
    """Return the problems of the text after the colon of the header.

    Args:
        rest: Everything after the colon. It must hold one space and then the
            description.
    """
    if not rest.startswith(" ") or rest.startswith("  "):
        return ["the colon of the header must be followed by exactly one space"]
    description = rest[1:]
    if not description.strip():
        return ["the header has no description after the colon"]
    problems: list[str] = []
    if description != description.strip():
        problems.append("the header has trailing whitespace")
    if description.rstrip().endswith("."):
        problems.append("the header must not end with a period")
    return problems


def _check_length(header: str) -> list[str]:
    """Return the problem of a header that is longer than the limit."""
    if len(header) <= HEADER_LIMIT:
        return []
    return [f"the header has {len(header)} characters; the limit is {HEADER_LIMIT}"]


def _check_form(header: str) -> list[str]:
    """Return the problems of the type, the scope and the description.

    A header that does not start with `type(scope)!:` gets one problem that
    names the form. A header that `git revert` wrote gets the hint for the
    `revert` type instead, and a header that `git merge` or `git pull` wrote
    gets the advice about merge commits. A person meets that header in the
    hook first, so the hook explains the case as `range` does.
    """
    match = _HEADER_START.fullmatch(header)
    if match is None:
        if header.startswith(_GIT_REVERT_START):
            return [
                f"{_FORM}; write '{REVERT_TYPE}: description' instead of the "
                "default header of git revert"
            ]
        if header.startswith(_GIT_MERGE_START):
            return [f"{_FORM}; this is a merge commit: {_MERGE_ADVICE}"]
        return [_FORM]
    return [
        *_check_type(match["type"]),
        *_check_scope(match["scope"]),
        *_check_description(match["rest"]),
    ]


def _check_separator(lines: list[str]) -> list[str]:
    """Return the problem of a body that does not follow a blank line."""
    if len(lines) > 1 and lines[1].strip():
        return ["the second line must be blank: a blank line ends the header"]
    return []


def check_commit_message(message: str, *, allow_autosquash: bool) -> list[str]:
    """Return the problems of a commit message, or an empty list.

    The first line is the header. A message that has no problem returns `[]`.
    Every problem of the message is in the list, so one run shows them all.

    Args:
        message: The full message, header first. The caller has removed what
            Git does not keep, such as comment lines.
        allow_autosquash: Whether a header that starts with `fixup! `,
            `squash! ` or `amend! ` passes. The commit-msg hook allows it,
            because a commit like that is a step of work that
            `git rebase --autosquash` removes. A check of finished history does
            not allow it. A message that passes this way is not checked
            further, because it copies the header of the commit that it
            corrects.

    Returns:
        One text per problem, in the order of the rules.
    """
    lines = message.split("\n")
    header = lines[0]
    if not header.strip():
        return ["the message has no header"]
    if header.startswith(AUTOSQUASH_PREFIXES):
        if allow_autosquash:
            return []
        prefix = header.split(" ", 1)[0]
        return [
            f"the header starts with '{prefix}': fold the commit into its target "
            "with 'git rebase --autosquash' before it lands"
        ]
    return [*_check_form(header), *_check_length(header), *_check_separator(lines)]


def check_stored_commit(message: str | None, *, is_merge: bool) -> list[str]:
    """Return the problems of a commit that Git already stores.

    A check of finished history never lets an autosquash header pass. Two
    cases have a problem of their own, and the message is not read for them:
    a merge commit, and a message that is not valid UTF-8 text.

    Args:
        message: The stored message, or `None` when its bytes are not valid
            UTF-8 text.
        is_merge: Whether the commit has more than one parent.

    Returns:
        One text per problem. A merge commit and an unreadable message get one
        problem each, and a commit that is both gets the merge problem only.
    """
    if is_merge:
        return [f"this is a merge commit: {_MERGE_ADVICE}"]
    if message is None:
        return [
            "the message is not valid UTF-8 text: amend the commit with a UTF-8 message"
        ]
    return check_commit_message(message, allow_autosquash=False)
