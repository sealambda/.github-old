# The CI of the hub

The workflow `.github/workflows/ci.yml` runs the hub's own checks on every
pull request and on every push to `main`. The job `ci` of the workflow is the
one required status check of the `main` ruleset.

## Concurrency

The workflow sets one `concurrency` group for each run.

| Event | Group | A newer run in the group |
| ----- | ----- | ------------------------ |
| Pull request | Workflow name, ref and head commit of the pull request | Waits for the run in progress. |
| Push to `main` | Workflow name and ref | Waits for the run in progress. |

No run cancels another run. The group of a pull request names the head
commit, so a run for a new head commit starts at once, and the run for the
older commit finishes. A newer run for the same head commit waits for the run
in progress, because the two share a group. A run on `main` is never cancelled
while it runs, because a cancelled run could leave a merge without its
release.

A push that updates a pull request and its base branch together can start two
runs for one head commit, one for each update. The pull requests of a stack
have this case after a push of the whole stack. The two runs share a group, so
they run one after the other and both finish.

A group holds one run in progress and one pending run. A third run in the
same group replaces the pending run, and GitHub cancels it. For a pull
request, that's a third run for the same head commit. For `main`, it's a push
that arrives while one run is in progress and another is pending. The replaced
push gets no release of its own, and the next release covers its commits
([Hub releases](hub-releases.md)).

## The job `ci`

The job `ci` fails unless every job that it needs succeeded. It runs even when
a needed job fails or is cancelled, because `if: always()` keeps GitHub from
skipping it, and GitHub reports a skipped required check as a success.

| Case | Result of `ci` |
| ---- | -------------- |
| Every needed job succeeds. | `ci` succeeds. |
| A needed job fails. | `ci` fails. |
| A person cancels the run. | `ci` fails. |
| A needed job is skipped. | `ci` fails. |
| The job `git-policy` is skipped on a push. | `ci` succeeds. |

The job `git-policy` runs on pull requests only, so a push to `main` skips it.
That skip is the only one that `ci` accepts.

A run that GitHub cancels because a newer run took its place leaves a failed
`ci` on the head commit, beside the `ci` of the newer run. GitHub doesn't
document which of two checks with one name a ruleset reads. The group of a
pull request avoids the case: no run replaces another run for the same head
commit while it runs.
