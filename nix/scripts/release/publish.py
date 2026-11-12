"""Create the GitHub release for a plan."""

import json

from release.plan import AlreadyReleased, Plan, ReleaseError, plan_for_existing_tag
from release.runner import CommandError, Runner
from release.series import HUB, Series

RELEASE_NOT_FOUND = "release not found"
"""What `gh release view` prints to standard error for a missing release.

`gh` exits with status 1 for this and for every other failure, so the text is
the only way to tell them apart. It is the message `ErrReleaseNotFound` in the
source of `gh` (`pkg/cmd/release/shared/fetch.go`).
"""


def remote_tag_commit(gh: Runner, tag: str) -> str:
    """Return the full hash of the commit that `tag` names on GitHub.

    The function reads the tag with the REST endpoints `git/ref/tags/<tag>` and,
    for an annotated tag, `git/tags/<hash>`. `gh` fills `{owner}` and `{repo}`
    from `GH_REPO`.

    Args:
        gh: The runner of `gh`.
        tag: The tag name.

    Raises:
        CommandError: `gh` failed, for example because the tag does not exist.
    """
    endpoint = "repos/{owner}/{repo}/git"
    target = json.loads(gh(["api", f"{endpoint}/ref/tags/{tag}"]))["object"]
    if target["type"] == "tag":
        target = json.loads(gh(["api", f"{endpoint}/tags/{target['sha']}"]))["object"]
    return str(target["sha"])


def publish_release(gh: Runner, plan: Plan, *, tag_exists: bool = False) -> None:
    """Create the release of `plan` with one `gh release create` call.

    The call has no assets, so it is one request to the API. When it fails, the
    caller cannot tell from the exit status whether GitHub created the tag
    before it failed: GitHub does not document the call as atomic. The next run
    finds out, because a tag without a release goes through `ensure_release`.

    For a new tag, `--target` names the full hash of the commit, so the tag
    lands on that commit and not on the head of the default branch. GitHub
    ignores `--target` when the tag already exists on its side, which happens
    when someone else pushed the tag after the checkout of this run. The call
    then succeeds and attaches the release to the other commit. So after the
    call for a new tag, this function reads the tag back from GitHub and
    refuses to report success when it names another commit.

    For a tag that exists, `--verify-tag` makes the call fail when the tag is
    not in the GitHub repository, and no `--target` is needed. The notes go
    through standard input, which has no limit on the length of an argument.
    A plan with `make_latest` set to `False` adds `--latest=false`, so that the
    release does not take the "latest" label from the hub release. The hub
    series keeps the default, which `gh` chooses by date and version, and its
    call has no such argument.

    Args:
        gh: The runner of `gh`. The repository and the token come from the
            environment of the process (`GH_REPO`, `GH_TOKEN`).
        plan: The release to create.
        tag_exists: `True` when the tag of `plan` already exists, and the call
            only adds the release to it.

    Raises:
        CommandError: `gh` failed.
        ReleaseError: The tag on GitHub names a commit other than the one of
            `plan`. The release exists and is attached to that tag, and the
            tool changes nothing more: a person decides what to do with it.
    """
    placement = ["--verify-tag"] if tag_exists else ["--target", plan.commit]
    label = [] if plan.make_latest else ["--latest=false"]
    gh(
        [
            "release",
            "create",
            plan.tag,
            *placement,
            "--title",
            plan.tag,
            "--notes-file",
            "-",
            *label,
        ],
        stdin=plan.notes,
    )
    if tag_exists:
        return
    actual = remote_tag_commit(gh, plan.tag)
    if actual != plan.commit:
        raise ReleaseError(
            f"the tag {plan.tag} on GitHub names commit {actual}, not "
            f"{plan.commit}: someone created the tag after the checkout, and "
            f"the release is attached to it"
        )


def release_exists(gh: Runner, tag: str) -> bool:
    """Ask GitHub whether a release exists for `tag`.

    A draft release counts: `gh release view` finds it too.

    Args:
        gh: The runner of `gh`.
        tag: The tag name.

    Returns:
        `True` when the release exists, `False` when GitHub says that it does
        not.

    Raises:
        CommandError: `gh` failed for any other reason, such as a refused token
            or a network error. The answer is then unknown, and the caller
            must not create anything.
    """
    try:
        gh(["release", "view", tag, "--json", "tagName"])
    except CommandError as error:
        if error.stderr == RELEASE_NOT_FOUND:
            return False
        raise
    return True


def ensure_release(
    gh: Runner, git: Runner, released: AlreadyReleased, series: Series = HUB
) -> bool:
    """Make sure that a release exists for the tag that a commit carries.

    A tag can exist without a release, for example when someone deleted the
    release and kept the tag. This function asks GitHub, and it creates the
    release for the existing tag when it is missing. The notes come from the
    release before that tag (`release.plan.plan_for_existing_tag`), and the
    release has the "latest" setting of the series.

    Args:
        gh: The runner of `gh`.
        git: The runner of git in the repository.
        released: The commit and the release tag that it carries.
        series: The series of the tag. The default is the hub series.

    Returns:
        `True` when this call created the release, `False` when it existed.

    Raises:
        CommandError: A `gh` or git command failed. Nothing is created when
            the question to GitHub fails.
    """
    if release_exists(gh, released.tag):
        return False
    plan = plan_for_existing_tag(git, released, series)
    publish_release(gh, plan, tag_exists=True)
    return True
