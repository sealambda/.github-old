# Hub releases

Every merge to `main` of the hub is released: it gets a tag and a release note
at the merged commit, or the next release covers it. The note says in its first
line whether the changes since the previous release touch the rules that
consumers read. The procedure is in
[Release the hub](../how-to/release-the-hub.md).

## Tag series

A release tag has the form `v<major>.<minor>.<patch>`. Each number is `0` or a
decimal number without a leading zero. The pattern is
`^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`. A tag of another form,
such as `v1.2`, `v01.2.3`, `v1.2.3-rc1` or `latest`, isn't a release tag, and
the release tool ignores it.

The hub has no major versions. It changes by expanding first and contracting
later, so the major number stays 1.

| Rules changed | Next version after `v1.4.2` |
| ------------- | --------------------------- |
| `yes` | `v1.5.0`: the minor number rises and the patch number resets. |
| `no` | `v1.4.3`: the patch number rises. |

The first release is `v1.0.0` with `rules changed: yes`.

## Previous release

The previous release of a commit is the highest release tag that the commit
contains: `git tag --merged <commit>`, filtered by the pattern above. The
order is by number, so `v1.10.0` is higher than `v1.9.0`. A tag on a branch
that the commit doesn't contain doesn't count.

The answer and the notes come from the previous release, not from the previous
run. When a run is skipped, the next release covers the commits of the skipped
one.

## Covered commits

A commit is covered when a release tag contains it, which means that a later
commit carries that tag: `git tag --contains <commit>`, filtered by the pattern
above. The release of the later commit lists the covered commit in its notes.
A covered commit gets no tag of its own: a second tag would sort behind the
release that already covers it.

This happens when a run is replaced by a newer push and someone runs the old
run again after the newer release exists. `release plan` and `release publish`
print `commit <hash> is covered by release <tag>` and exit 0. The tag in the
message is the lowest release tag that contains the commit. They create
nothing.

A commit that itself carries a release tag isn't covered but released: see
[Commands](#commands).

## Rules changed

A person doesn't type the answer. The tool derives it from the paths that
differ between the previous release and the released commit, with renames
counted as a delete and an add.

The answer is `no` only when every changed path is on the list below. Every
other path gives `yes`, including a path that no one has classified yet and a
path that isn't valid UTF-8 (the tool reads it with the replacement character
U+FFFD, which no pattern names, except inside a folder that a `**` pattern
covers). The
first release gives `yes` without a comparison, because it has no previous
release. A merge that changes no path gives `no`.

A consumer reads the hub in four ways: through its flake (the `lib` functions,
the apps, the files that `sync-config` copies, the base of the wrapped
documentation tools and the Vale style), through the
reusable workflow `secrets.yml`, through the Renovate preset `default.json`,
and through the default community files that GitHub applies to every
repository of the organization. A path is on the list only when none of the
four reads it.

| Pattern | Why no consumer reads it |
| ------- | ------------------------ |
| `docs/how-to/**`, `docs/reference/**`, `docs/decisions/**`, `docs/specs/**` | The pages, decision records and design specs of the hub. The `docs` and `decisions` checks of a consumer read the consumer's own pages. A consumer can still follow a link into these folders, so a moved or deleted page needs its links updated in the same pull request ([Limits](#limits)). Only these four folders are listed, because they're the folders of the hub's layout. GitHub reads default community files from the `docs/` folder, so every other path below `docs/` stays `yes` ([source][community-files]). |
| `README.md` | The root file only. GitHub shows it for this repository and doesn't apply it to others. A README in a subfolder isn't listed. |
| `nix/tests/**` | The tests of the hub's own tools and functions, and the synthetic consumer. Only the hub's own CI runs them: the checks that end in `-tests` run the tests of the tools, the check `lib-functions` runs `nix/tests/lib`, and the job `consumer` of `ci.yml` builds the consumer `nix/tests/consumers/legacy`. |
| `vale/Sealambda/*.test.yml` | The test cases of the Vale style. The flake builds the style from the rule files and leaves the test cases out. |
| `LICENSE` | The license of this repository. GitHub has no default license file for other repositories. |
| `LICENSES/**` | The license texts of the REUSE layout. Only the hub's `licenses` check reads them. |
| `REUSE.toml` | The license annotations of the hub's own files. Only the hub's `licenses` check reads it. |
| `.github/CODEOWNERS` | GitHub reads the file of each repository and doesn't inherit one. It sets the reviewers of the hub only. |
| `.github/workflows/ci.yml` | The hub's own CI. It has no `workflow_call` trigger, so no consumer calls it. |
| `.gitignore` | The ignore list of the hub's own work tree. |

Every other tracked path stays `yes`. This table groups them by the reader
that makes them rules:

| Paths | Who reads them |
| ----- | -------------- |
| `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md`, `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/**` | GitHub applies them to every repository of the organization that has no file of its own. A change reaches every repository. |
| Every other path below `docs/`, such as `docs/PULL_REQUEST_TEMPLATE/**`, `docs/ISSUE_TEMPLATE/**` and a file directly in `docs/` | GitHub reads default community files from `docs/` as well as from the root and `.github/`. Its documentation names the pull request template and the folder `docs/PULL_REQUEST_TEMPLATE/` there. It places issue templates and discussion category forms in `.github/` only, and the hub still treats every unnamed folder as a rule, so it never has to decide which ones GitHub reads. |
| `flake.nix`, `nix/lib/**`, `flake.lock`, `treefmt.nix` | The flake of every consumer. `nix/lib/` holds the functions that the flake exports as `lib` and the tools that its apps and checks run. |
| `config/**` | `sync-config` copies them into every consumer, and the wrappers of the `docs` check and shell read them from the Nix store as the base of Vale, markdownlint-cli2 and lychee ([Wrapped documentation tools](wrapped-tools.md)). |
| `vale/Sealambda/*.yml` (the rules) | The Vale style of `mkDocsCheck`. |
| `nix/scripts/**` | The tools that the flake runs. The `decisions` and `workflows` tools and `check-docs.sh` run in the checks of a consumer, and the `gitpolicy` tool runs in its CI and in a hook that it adds. |
| `schemas/**` | The `decisions` tool validates records against them. |
| `.github/workflows/secrets.yml` | The reusable workflow that consumers call. |
| `default.json` | The Renovate preset that consumers extend. |
| `versions.json` | The pinned version of Nix that workflows install. |
| `templates/**` | People copy them into consumers, and the `versions` check reads the workflows below `templates/`. |
| `.editorconfig`, `.markdownlint-cli2.yaml`, `.vale.ini`, `.vale/**`, `lychee.toml`, `.github/.markdownlint-cli2.yaml` | The hub's own copies of the files in `config/`. The check `config-in-sync` keeps the copies equal, and the source in `config/` is the rule. |
| `renovate.json`, `pyproject.toml` | The hub's own Renovate and Python settings. No consumer reads them, and no one has classified them as free: they stay `yes`. |

The list is `RULE_FREE_PATTERNS` in `nix/scripts/release/paths.py`. The
patterns follow `PurePosixPath.full_match`: `*` stays inside one path
component and `**` crosses components. To change the list, change that file and
the first table together: a test of `check-release-tests` fails when the
patterns of the table and the list differ. A new tracked path starts as `yes`.
Add it to the list only after finding that none of the four readers reads it.

The sources for the `docs/` rows are
[Creating a default community health file][community-files] and
[Creating a pull request template][pr-template]. The first lists the places
where GitHub reads default files and the issue templates in `.github/`. The
second names `docs/` and `docs/PULL_REQUEST_TEMPLATE/` for pull request
templates.

[community-files]: https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file
[pr-template]: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository

## Release note

The first line is `rules changed: yes` or `rules changed: no`. A blank line
follows, then one bullet with the subject of each commit since the previous
release, the newest first. Each subject is a Markdown code span:

```text
rules changed: no

- `docs: fix a link in the adoption guide`
- `docs(readme): list the release procedure`
```

GitHub renders the notes as Markdown, and the subject is the text of a
contributor. Inside a code span, a link, an `@` mention and a `#` reference stay
plain text. The fence of the span is one backtick longer than the longest run of
backticks in the subject.

The title of the release is its tag.

The notes hold at most 100000 bytes (`MAX_NOTES_BYTES` in
`nix/scripts/release/notes.py`). When the commits don't fit, the notes list
the newest commits and end with one line, `older commits omitted: <count>`.
This happens for the first release of a long history. The bound is the hub's
own choice. The GitHub documentation of the "Create a release" call states no
maximum for the body. The API rejects a body of more than 125000 characters
with the message `body is too long (maximum is 125000 characters)`, and the
hub's bound stays below that number.

## The release job

The job `release` in `.github/workflows/ci.yml` runs for a push to `main`,
after the job `ci` succeeds. It isn't part of the `ci` aggregate, so a failed
release doesn't fail the checks of the merge.

| Setting | Value |
| ------- | ----- |
| Permission | `contents: write` on this job only. |
| Checkout | The whole history and every tag, without stored credentials. |
| Build step | `nix build .#release --out-link "$RUNNER_TEMP/release"`, with no token. |
| Command | `"$RUNNER_TEMP/release/bin/release" publish --commit "$GITHUB_SHA"` |
| Environment | `GH_TOKEN` is the job token and `GH_REPO` is the repository. Only the command step has them. |

Nix evaluates the flake, fetches its inputs and builds the command in the
build step. That step has no token. The command step runs the built command
and no Nix, so no Nix process holds the token.

The workflow concurrency group never cancels a run in progress, so a run on
`main` is never cancelled while it runs ([CI of the hub](hub-ci.md)). A group
holds one running and one pending run, and a newer pending run replaces an
older one.
When pushes arrive faster than runs finish, the replaced push gets no tag of
its own, and the next release covers its commits.

## Commands

The `release` command runs in the current Git repository. `git` and `gh` come
from the hub's nixpkgs. The flake exports it as `packages.release`, and
`nix run .#release` runs it. It belongs to this repository: it plans from the
paths that the hub's own rules classify, so a consumer has no use for it, and
the hub makes no promise about its interface to other repositories.

| Command | What it does |
| ------- | ------------ |
| `release plan [--commit REVISION]` | Prints the tag, the commit, the previous release and the notes. It changes nothing and doesn't call `gh`. |
| `release publish [--commit REVISION]` | Creates the GitHub release, and with it the tag, at exactly that commit. |

`REVISION` defaults to `HEAD`. `publish` handles four cases, in this order:

1. The commit carries a release tag. `publish` asks GitHub with
   `gh release view <tag>` whether the release of that tag exists. When it
   does, `publish` prints `commit <hash> is already released as <tag>` and
   exits 0. When GitHub answers that the release doesn't exist, `publish`
   creates it for the existing tag with `gh release create <tag>
   --verify-tag`. The notes come from the release before that tag, the same
   as for a new tag. When the question fails for another reason, such as a
   refused token or a network error, `publish` exits 1 and creates nothing.
   `plan` only prints that the commit is released: it doesn't call `gh`.
2. A later release tag contains the commit. The commit is covered, and
   `publish` creates nothing ([Covered commits](#covered-commits)).
3. The tag that the commit gets exists on a commit that doesn't contain this
   one, for example on another branch. `publish` exits 1 and creates nothing.
4. Otherwise `publish` makes one `gh release create <tag> --target <hash>`
   call without assets and the tag lands on that exact commit. The tool
   doesn't create a tag in the local repository. GitHub ignores `--target`
   when the tag already exists on its side, for example when someone pushed
   the tag after the checkout of the run. So `publish` then reads the tag back
   with `gh api repos/{owner}/{repo}/git/ref/tags/<tag>`, and it follows an
   annotated tag to its commit. When the tag names another commit, `publish`
   exits 1 and doesn't print that it released the commit. The release exists
   by then and is attached to that tag. The tool changes nothing more.

The state of a failed call: GitHub doesn't document that `gh release create`
makes the tag and the release in one step, or what a failed call leaves. The
tool doesn't assume either. After a failure, a re-run of the same command finds
the commit with a tag and no release, and case 1 repairs it, or it finds no
tag and case 4 runs again. The same repair applies when someone deletes a
release and keeps its tag. A draft release for the tag counts as existing,
because `gh release view` finds drafts too.

`publish` tells a missing release from another failure by the standard error
of `gh release view`, which is `release not found` in `gh` 2.103 (the message
`ErrReleaseNotFound` in
[`pkg/cmd/release/shared/fetch.go`](https://github.com/cli/cli/blob/v2.103.3/pkg/cmd/release/shared/fetch.go)).
`gh` exits with status 1 for every failure, so the exit status alone doesn't
tell them apart. A change of that message in a later `gh` makes `publish` exit
1 for a missing release and create nothing, and the tests of the tool name the
message.

Exit status: 0 for success, 1 when the release can't be made, 2 for a usage
error and 3 for an internal error.

```console
nix run .#release -- plan
```

The command starts Python with `-P`, so the current directory isn't on the
import path. A file in the repository that the command runs in, such as
`argparse.py` or a package `release`, can't replace the code of the tool.

The tests are the flake check `check-release-tests`. It also builds the
`release` command, runs `release --help` and `release plan` in a temporary
repository with one commit, and runs `release plan` again next to a package
`release` that would shadow the tool. This covers the wrapper, its run-time
inputs and the default runners, which the unit tests replace.

## Immutable releases

The workflow creates each tag once and never moves or deletes it. What stops
another actor from moving or deleting a tag is the organization's GitHub
configuration: the repository setting immutable releases and tag rulesets.
This page doesn't define either, and the hub's code doesn't check them.

GitHub documents the immutable releases setting in
[Immutable releases](https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/immutable-releases):

- The tag of a published release can't move to another commit and can't be
  deleted while the release exists.
- The assets of a published release can't change. The hub's releases have no
  assets.
- When someone deletes an immutable release, the tag can go, but the tag name
  can never be used again.
- The release title and the notes stay editable.

The setting applies to releases that GitHub publishes after it's on. The hub's
tool never deletes a release or a tag. It also doesn't skip a retired tag name:
it computes the next version from the tags that exist.

To read the setting of the hub:

```console
gh api repos/sealambda/.github/immutable-releases
```

The answer holds `enabled` and `enforced_by_owner`.

## Limits

- Whether a tag is immutable depends on the organization's GitHub
  configuration, not on the hub's code.
- A tag name that GitHub retired after the deletion of an immutable release
  can't be reused. The tool computes the next version from the highest tag that
  exists, so it can compute a retired name again. A person decides how to
  continue the series then.
- The answer `rules changed` follows paths, not meaning. A change that only
  touches a listed path can still matter to a person, and a change to an
  unlisted path can be harmless. The second case is the cost of the safe
  default.
- A file that every repository inherits, such as `CONTRIBUTING.md`, can link
  to a page below `docs/how-to/`, `docs/reference/`, `docs/decisions/` or
  `docs/specs/`. Those folders are free of rules. A rename or a deletion of
  such a page gives `rules changed: no`, although the link breaks in every
  repository that inherits the file. The `docs` check of the hub catches the
  broken link inside the hub only.
- A consumer sees two more links into `docs/reference/`: the `link:` URLs of
  the Vale rules `vale/Sealambda/CurrentState.yml` and
  `vale/Sealambda/History.yml` name `docs/reference/writing-style.md`, and the
  header that `nix/scripts/decisions/ledger_edit.py` writes into the ledger of
  a consumer names `docs/reference/decision-records.md`. A rename or a
  deletion of one of those pages gives `rules changed: no` and breaks the
  link in every consumer. The tool has no way to force `yes`, so update the
  link in the same pull request: the file that holds the link is a rule path, so
  the answer is `yes`.
- A covered commit gets no check of the release that covers it: `publish`
  trusts the tag and doesn't ask GitHub whether that release exists.
- A run that fails after the checks of a merge leaves the merge without a
  release until a re-run or the next release.
