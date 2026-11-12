"""Clean the text of a commit message file as Git does when it records it.

Git calls the `commit-msg` hook with the file of the message before it cleans
the message up, so the file can still hold the comment lines of the editor
template. A check that read the file as it is would take a comment for the
header or the body. `clean_commit_message` applies the cleanup mode of Git, so
the check sees the message that the commit gets.

The mode comes from the `--cleanup` option of `git commit` and from the
`commit.cleanup` setting. The documentation of `git commit` gives the default:
`strip` when the message is to be edited and `whitespace` when it is not, for
example with `--message` or `--file`. The hook cannot tell which of the two
runs, so the caller passes the mode of the setting and `strip` when the
setting is missing. The string that starts a comment line comes from
`core.commentChar`, which the caller reads. See `docs/reference/git-policy.md`
for the one difference that remains.
"""

import re
from enum import StrEnum

from gitpolicy.vocabulary import DEFAULT_COMMENT

# The line that `git commit --verbose` writes before the diff. Git drops it
# and everything after it. It is the comment string, a space and these dashes.
_SCISSORS = " ------------------------ >8 ------------------------"

# Git ends a line with a line feed. A carriage return before it belongs to the
# line ending, so `\r\n` ends a line too. No other character ends a line:
# `str.splitlines` would also split on a form feed or a Unicode line
# separator, which Git keeps inside the line.
_LINE_END = re.compile(r"\r?\n")

# The whitespace that Git strips: the space, the tab and the line ends. Git
# does not strip a Unicode space such as the no-break space.
_GIT_SPACE = " \t\n\r"


class CleanupMode(StrEnum):
    """The values of `commit.cleanup` that change the text, as Git names them.

    Attributes:
        STRIP: Remove comment lines, trailing whitespace and the blank lines
            around the message.
        WHITESPACE: As `STRIP`, and keep the comment lines.
        VERBATIM: Change nothing.
        SCISSORS: As `WHITESPACE`; the text after the scissors line goes. The
            tool drops that text in every mode but `VERBATIM`, because the
            hook cannot see whether `git commit --verbose` wrote it.
    """

    STRIP = "strip"
    WHITESPACE = "whitespace"
    VERBATIM = "verbatim"
    SCISSORS = "scissors"


def _before_scissors(lines: list[str], comment: str) -> list[str]:
    """Return the lines above the scissors line, or all of them without one."""
    scissors = comment + _SCISSORS
    for index, line in enumerate(lines):
        if line.startswith(scissors):
            return lines[:index]
    return lines


def clean_commit_message(
    text: str,
    mode: CleanupMode = CleanupMode.STRIP,
    comment: str = DEFAULT_COMMENT,
) -> str:
    """Return the message that Git records for the text of a message file.

    The text ends at the scissors line, except in `VERBATIM` mode, which
    returns the text as it is. In `STRIP` mode, lines that start with the
    comment string are comments and go. In every other mode they stay. Blank
    lines at the start and at the end go, and so does the whitespace at the end
    of each line. Blank lines between paragraphs stay. Git also collapses a run
    of blank lines to one, and this function does not, because no rule reads
    past the second line.

    Args:
        text: The content of the file that the `commit-msg` hook receives.
        mode: How Git cleans the message.
        comment: The string that starts a comment line and the scissors line,
            from `core.commentChar` or `core.commentString`. Git's default is
            `#`.

    Returns:
        The message, with no final newline unless the mode is `VERBATIM`. It is
        empty when nothing remains.
    """
    if mode is CleanupMode.VERBATIM:
        return text
    kept = [
        line.rstrip(_GIT_SPACE)
        for line in _before_scissors(_LINE_END.split(text), comment)
        if mode is not CleanupMode.STRIP or not line.startswith(comment)
    ]
    return "\n".join(kept).strip("\n")
