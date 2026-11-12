"""Decide from changed paths whether the rules of the hub changed.

A consumer reads the hub through its flake, its reusable workflow, the Renovate
preset and the default community files that GitHub applies to every repository
of the organization. A change to a path that `RULE_FREE_PATTERNS` does not
list may change what a consumer does, so it counts as a change of the rules.
This is the safe answer for a path that nobody has classified.

The actions series (`release.series`) has its own paths: the workflow and
action files that a consumer calls by the tag of that series, and the data
file that an action reads. `ACTIONS_FILE_PATTERNS` and `ACTIONS_DATA_PATTERNS`
name them. The hub series leaves them out of its rules, because the actions
series releases them.
"""

from collections.abc import Iterable
from pathlib import PurePosixPath

ACTIONS_FILE_PATTERNS: tuple[str, ...] = (".github/actions/**",)
"""The workflow and action files that the actions series releases.

The reusable workflow `secrets.yml` is not here: it stays in the hub series. A
pattern names a file that the hub holds. The pull request that adds a reusable
workflow for consumers to call by the actions tag adds its pattern here, with
the tests and the page, so that the file gets its classification with its
contract.
"""

ACTIONS_DATA_PATTERNS: tuple[str, ...] = ("versions.json",)
"""The data files that an action reads and that the actions series releases.

`versions.json` holds the pinned version of Nix. The action `setup-nix` reads
it, and the hub's own `versions` check reads it. No function of the flake reads
it, so a change to it never changes what a flake consumer evaluates.
"""

RULE_FREE_PATTERNS: tuple[str, ...] = (
    "docs/how-to/**",
    "docs/reference/**",
    "docs/decisions/**",
    "docs/specs/**",
    "README.md",
    "nix/tests/**",
    "vale/Sealambda/*.test.yml",
    "LICENSE",
    "LICENSES/**",
    "REUSE.toml",
    ".github/CODEOWNERS",
    ".github/workflows/ci.yml",
    ".gitignore",
    *ACTIONS_FILE_PATTERNS,
    *ACTIONS_DATA_PATTERNS,
)
"""The paths that no consumer reads through the hub series, as glob patterns.

The last two groups are the paths of the actions series. A consumer reads them
by the tag of that series, never through the flake, `secrets.yml`, the preset
or the community files, which the hub series covers. A change to them gives a
patch release of the hub series, and the actions series decides its own
release. Before the actions series existed, `versions.json` was a rule of the
hub series: its readers were the hub's own `versions` check and no consumer.

The patterns follow `PurePosixPath.full_match`: `*` stays inside one path
component, and `**` matches any number of components. A path is relative to the
root of the repository. The four `docs/` patterns name the folders that the
hub's layout holds (`CONTRIBUTING.md` and the `decisions` tool name
`docs/specs/`). Every other path below `docs/` is a rule: GitHub reads default
community files from the `docs/` folder, at least the pull request template and
its `PULL_REQUEST_TEMPLATE/` folder, so a file there can reach every repository
of the organization. A folder that the hub doesn't name, such as
`docs/ISSUE_TEMPLATE/`, stays a rule: only a named folder is free. Sources,
read on 2026-11-12:
https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file
and
https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository.
`docs/reference/hub-releases.md` gives the reason for each pattern: change both
together. A test compares the patterns of that table with this tuple.
"""


def matches_any(path: str, patterns: Iterable[str]) -> bool:
    """Tell whether `path` matches at least one glob pattern.

    Args:
        path: A path relative to the root of the repository, with `/` as the
            separator.
        patterns: Glob patterns in the form of `RULE_FREE_PATTERNS`.
    """
    candidate = PurePosixPath(path)
    return any(candidate.full_match(pattern) for pattern in patterns)


def is_rule_free(path: str) -> bool:
    """Tell whether no consumer reads the file at `path`.

    Args:
        path: A path relative to the root of the repository, with `/` as the
            separator.
    """
    return matches_any(path, RULE_FREE_PATTERNS)


def rules_changed(paths: Iterable[str]) -> bool:
    """Tell whether a set of changed paths changes the rules of the hub.

    Args:
        paths: The paths that differ between two commits, including the old
            path of a renamed file and the path of a deleted file.

    Returns:
        `True` when at least one path is not rule-free. An empty set returns
        `False`: nothing changed.
    """
    return not all(is_rule_free(path) for path in paths)
