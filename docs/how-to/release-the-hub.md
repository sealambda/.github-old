# Release the hub

A merge to `main` releases the hub. No one runs a command for a normal release.
This page says what a merge triggers, how to read the release, what to do when
the job fails and how to undo a change. The
[Hub releases](../reference/hub-releases.md) page has the tag series and the
rule for `rules changed`.

## What a merge triggers

1. The jobs of the workflow `CI` run on the merge commit.
2. When the job `ci` succeeds, the job `release` runs `release publish` for
   that commit.
3. The job creates the tag and the release at the merge commit with one
   `gh release create` call. The release note starts with `rules changed: yes`
   or `rules changed: no`.

A commit that already has a release tag gets no second tag. A commit that a
later release contains gets no tag either: that release covers it.

## Read a release

Open the release in the repository's Releases list, or run:

```console
gh release view <tag> --repo sealambda/.github
```

- `rules changed: no` means every changed path is one that no consumer
  evaluates, such as documentation. The patch number rose.
- `rules changed: yes` means at least one changed path can change what a
  consumer evaluates, or no one has classified it. The minor number rose and the
  patch number reset.
- The bullets list the subject of each commit since the previous release. A
  very long list ends with `older commits omitted: <count>`.

To see the answer for a commit before it merges, run `release plan` in a
checkout of the branch. It prints the tag, the previous release and the notes,
and it changes nothing:

```console
nix run .#release -- plan
```

The previous release is the highest release tag that the branch contains. A
branch that's behind `main` doesn't contain the newest tags, so it shows an
older previous release, a lower tag and notes that list more commits than the
merge will. Rebase the branch on `main` first, and fetch the tags, to see what
the merge gets.

## When the release job fails

A failed `release` job doesn't fail the checks of the merge. The merge stays
without a release until a re-run or the next release. The next release covers
its commits, because the answer and the notes come from the previous tag.

1. Open the failed run in the Actions tab and read the log of the step
   `Publish the release`.
2. Fix a cause outside the repository, such as an outage of GitHub, and re-run
   the failed job. The command is safe to repeat. GitHub doesn't document what
   a failed `gh release create` call leaves behind, so the command checks
   instead of assuming: it asks GitHub whether the release of an existing tag
   exists, and it creates the release when it's missing.
3. Don't fix the failure by creating or moving a tag by hand.

A tag can exist without a release, for example after a failed call or after
someone deleted the release and kept the tag. The re-run of the job repairs it.
It prints `carries the tag ... without a release: created the release for the
existing tag`. The notes come from the release before that tag.

The re-run of a commit that a later release contains prints
`commit ... is covered by release ...` and exits 0. Nothing is wrong: that
release lists the commit in its notes. The same happens when a newer push
replaced a run before it started and someone runs the old run again. The
commit has no release of its own, and the next release covers it.

The message `the tag ... exists on commit ...` means that the version this
commit would get is taken by a release on a commit that doesn't contain this
one, for example on another branch. Open the tags of the repository and decide
how to continue the series. Don't move the tag.

The message of `gh release view` in the log tells a failed check from a
missing release. A failed check, such as a refused token, stops the job
without creating anything. Fix the token or the permission and re-run the job.

## Undo a change

Undo a change with a new pull request that reverts it. The merge of that pull
request is a new release. Never move or delete a tag, and never delete a
release to hide a change: a consumer may already use the tag, and GitHub
documents that the tag name of a deleted immutable release can't be reused.
The workflow never moves or deletes a tag. The organization's GitHub
configuration decides what stops another actor
([Immutable releases](../reference/hub-releases.md#immutable-releases)).

## Check the release tool

Run the tests of the tool with `nix flake check`, or only the tests:

```console
nix build .#checks.x86_64-linux.check-release-tests -L
```
