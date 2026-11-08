"""Turn the URL of the `origin` remote into a repository name and a permalink."""

import re

_SCP_LIKE = re.compile(
    r"^[\w.-]+@github\.com:(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)
"""`git@github.com:owner/repo.git`, the short SSH form."""

_URL = re.compile(
    r"""
    ^(?:https?|ssh|git)://              # a scheme that git uses
    (?:[^@/\s]+@)?                      # optional user, such as `git@`
    github\.com(?::[0-9]+)?             # the host and an optional port
    /(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?/?$
    """,
    re.IGNORECASE | re.VERBOSE,
)
"""`https://github.com/owner/repo(.git)` and `ssh://git@github.com/owner/repo.git`."""


def parse_github_remote(url: str) -> str:
    """Return the `owner/name` of a GitHub remote URL.

    The accepted forms are `git@github.com:owner/repo.git`,
    `https://github.com/owner/repo` and `ssh://git@github.com/owner/repo.git`,
    each with or without the `.git` suffix. The host is `github.com`.

    Args:
        url: The URL of the remote, as `git remote get-url` prints it.

    Returns:
        The repository as `owner/name`.

    Raises:
        ValueError: The URL is not a `github.com` repository URL. The message
            shows the URL through `redact_userinfo`, so it holds no credential.
    """
    for pattern in (_SCP_LIKE, _URL):
        match = pattern.match(url.strip())
        if match:
            return f"{match['owner']}/{match['repo']}"
    raise ValueError(f"not a github.com repository URL: {redact_userinfo(url)}")


def redact_userinfo(url: str) -> str:
    """Return `url` with the user name and password replaced by `***`.

    A remote URL can hold a token, such as
    `https://x-access-token:<token>@github.com/owner/repo`, and a message may
    reach a CI log. Every message that shows a remote URL must pass it here.
    Everything between the scheme, if any, and the last `@` is the user
    information. The cut is at the last `@`, not at the first `/`, so that a
    secret with a `/` does not leak its tail. A GitHub repository name has no
    `@`, so a valid URL loses only its user information.

    Args:
        url: A remote URL in any form, or any other text.

    Returns:
        The stripped URL, without user information. A text without `@` comes
        back unchanged, apart from surrounding whitespace.
    """
    text = url.strip()
    scheme, separator, rest = text.partition("://")
    if not separator:
        scheme, rest = "", text
    else:
        scheme += separator
    _, at_sign, host_and_path = rest.rpartition("@")
    return f"{scheme}{'***@' if at_sign else ''}{host_and_path}"


def permalink(repository: str, commit: str, path: str) -> str:
    """Return the GitHub permalink of a file at a commit.

    Args:
        repository: The `owner/name` of the repository.
        commit: The full hash of the commit.
        path: The path of the file in that commit, with `/` separators.
    """
    return f"https://github.com/{repository}/blob/{commit}/{path}"
