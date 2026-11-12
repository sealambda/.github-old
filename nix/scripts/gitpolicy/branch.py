"""The rules for a branch name.

A name is `main`, a name under a bot prefix such as `renovate/`, or
`<type>/<slug>`: a type from the one list of `gitpolicy.vocabulary`, a slash
and a lower-case slug of words that single hyphens join.
`check_branch_name` is a pure function: it reads a name and returns the
problems.
"""

import re

from gitpolicy.vocabulary import BOT_BRANCH_PREFIXES, BRANCH_TYPES, TRUNK_BRANCH

# The slug of a branch: words of lower-case letters and digits, joined by
# single hyphens, with no hyphen at either end.
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

_FORM = "the branch name must be '<type>/<slug>'"


def _is_bot_branch(name: str) -> bool:
    """Return whether the name is a bot's: a prefix and a topic after it."""
    return any(
        name.startswith(prefix) and len(name) > len(prefix)
        for prefix in BOT_BRANCH_PREFIXES
    )


def check_branch_name(name: str) -> list[str]:
    """Return the problems of a branch name, or an empty list.

    `main` and the names under a bot prefix pass. Any other name must be
    `<type>/<slug>` with a type from `BRANCH_TYPES` and a slug of lower-case
    words that single hyphens join, for example `fix/listen-address`.

    Args:
        name: The short name of the branch, with no `refs/heads/` prefix.

    Returns:
        One text per problem, in the order of the rules.
    """
    if name == TRUNK_BRANCH or _is_bot_branch(name):
        return []
    branch_type, separator, slug = name.partition("/")
    if not separator:
        return [f"{_FORM}: '{name}' has no '/'"]
    problems: list[str] = []
    if branch_type not in BRANCH_TYPES:
        problems.append(
            f"the type '{branch_type}' must be one of: {', '.join(BRANCH_TYPES)}"
        )
    if not _SLUG.fullmatch(slug):
        problems.append(
            f"the slug '{slug}' must be lower-case letters and digits, "
            "joined by single hyphens"
        )
    return problems
