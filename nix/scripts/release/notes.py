"""Render the text of a release."""

import re
from collections.abc import Sequence

MAX_NOTES_BYTES = 100_000
"""The most bytes that the notes of a release may hold.

This is a bound that the hub chose. It is not a limit that GitHub documents:
the REST documentation of "Create a release" states no maximum for `body`. The
API rejects a longer body with the message `body is too long (maximum is 125000
characters)`, so the bound stays well below that number. It counts UTF-8 bytes,
and a byte count is never lower than the character count.
"""


def _omitted_line(count: int) -> str:
    """Return the last line of notes that leave `count` older commits out."""
    return f"older commits omitted: {count}\n"


def _code_span(text: str) -> str:
    """Return `text` as one Markdown code span.

    GitHub renders the notes as Markdown, and the text of a commit subject comes
    from a contributor. Inside a code span, a link, an `@` mention, a `#`
    reference and an emphasis mark stay plain text. The fence is one backtick
    longer than the longest run of backticks in `text`, so no run in `text` can
    end the span. A space on each side keeps a backtick at the start or the end
    of `text` apart from the fence.
    """
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * (longest + 1)
    padding = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{padding}{text}{padding}{fence}"


def _size(text: str) -> int:
    """Return the size of `text` in UTF-8 bytes."""
    return len(text.encode("utf-8"))


def render_notes(
    rules_changed: bool,
    subjects: Sequence[str],
    limit: int = MAX_NOTES_BYTES,
) -> str:
    """Return the notes of a release.

    The first line is `rules changed: yes` or `rules changed: no`. A blank line
    follows, then one bullet for the subject of each commit. A bullet holds the
    subject as a Markdown code span, so the text of a contributor cannot add a
    link, a mention or a reference to the notes. When the whole text would
    exceed `limit`, the notes keep the first subjects, which are the newest
    commits, and end with one line, `older commits omitted: <count>`. Notes
    that fit have no such line.

    Args:
        rules_changed: The answer for the release.
        subjects: The subject lines of the commits in the release, newest
            first. Each is one line.
        limit: The most bytes (UTF-8) that the notes may hold. The default is
            `MAX_NOTES_BYTES`. A limit that cannot hold the first line and the
            last line gives notes that exceed it, and the first line stays.
    """
    answer = "yes" if rules_changed else "no"
    header = f"rules changed: {answer}\n\n"
    bullets = [f"- {_code_span(subject)}\n" for subject in subjects]
    if _size(header) + sum(_size(bullet) for bullet in bullets) <= limit:
        return header + "".join(bullets)

    budget = limit - _size(header) - _size(_omitted_line(len(bullets)))
    kept = 0
    for bullet in bullets:
        budget -= _size(bullet)
        if budget < 0:
            break
        kept += 1
    return header + "".join(bullets[:kept]) + _omitted_line(len(bullets) - kept)
