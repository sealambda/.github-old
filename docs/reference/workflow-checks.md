# Workflow checks

The flake check `workflows` reads the workflows of a repository and fails when a
job has no time limit or when a pull request workflow has no concurrency group.
It runs with `nix flake check`, locally and in CI, and it needs no network.

## Rules

| Rule | What it requires |
| ---- | ---------------- |
| Time limit | Every job that doesn't call a reusable workflow sets `timeout-minutes`. |
| Concurrency | Every workflow that a `pull_request` or `pull_request_target` event triggers sets a `concurrency` group. |

### Time limit

The value of `timeout-minutes` is a whole number from 1 to 360, or an
expression: a string that's exactly one balanced `${{ ... }}`, with optional
whitespace around it. The text between the delimiters isn't blank and holds no
other `${{`, and the first `}}` after the opening ends the string. The check
can't read the value of an expression, so it accepts one, for example
`${{ inputs.timeout-minutes }}`, and the bound of 360 doesn't apply to what the
expression gives at run time. These values are findings: a missing key,
zero, a negative number, a number above 360, a fractional number, a boolean, a
null, a string that holds no expression, and a string that holds an unclosed,
empty, repeated or padded expression, such as `${{ x`, `${{ }}`,
`${{ a }} ${{ b }}` and `5 ${{ a }}`. The check doesn't parse the expression
language, so it also rejects an expression whose string literal holds `}}`.

The check is stricter than GitHub for `"5"`, `5.0` and `5.5`. It reports all
three, because the hub holds a limit to a whole number that the file writes as
an integer, or to an expression.

A job that has `uses` calls a reusable workflow, and it's exempt. GitHub
doesn't allow `timeout-minutes` on such a job: the called workflow sets the
limits of its own jobs ([supported keywords][call-keywords]). The check neither
requires nor judges a `timeout-minutes` on a `uses` job, so a `uses` job that
carries one passes the check. actionlint reports it.

The check doesn't read the called workflow. A called workflow that sets no limit
on its jobs runs for 360 minutes, and the `uses` job that calls it passes the
check. The hub's `secrets.yml` is such a workflow: its input `timeout-minutes`
defaults to 360, so a caller that passes nothing gets six hours. The caller
passes the input to bound the scan, as [Adopt the hub in a
repository](../how-to/adopt-the-hub.md#call-the-reusable-workflow) shows.

GitHub gives a job 360 minutes when the key is missing. A job on a
GitHub-hosted runner may run for up to six hours, and a job on a self-hosted
runner for up to five days ([usage limits][limits]). The upper bound of 360 is
the hub's policy: it holds every job to six hours, and a job that needs more is
a design to review. The check doesn't judge a `timeout-minutes` on a step.

### Concurrency

A workflow that a pull request event triggers sets a `concurrency` group in one
of two places:

- At the top of the workflow, which covers every job.
- On every job of the workflow, a job that has `uses` included. GitHub allows
  `concurrency` on such a job ([supported keywords][call-keywords]).

The value sets a group when it's a string that isn't blank, or a mapping whose
`group` is a string that isn't blank. These values set no group and are
findings: a null, as in an empty `concurrency:`, an empty mapping, a mapping
that holds only `cancel-in-progress`, a blank string and a value of another
shape, such as a list. A workflow that has no job and no top-level group is a
finding.

A workflow whose only event is `workflow_call` is a reusable workflow. The
workflow of the caller owns the group, so the rule doesn't cover it. A workflow
that has `workflow_call` next to `pull_request` is covered, because the pull
request event runs it directly.

The check requires a group to exist. It doesn't read the group expression, and
it doesn't judge `cancel-in-progress`. The mapping form needs `group`, because
GitHub requires it there. [Control the concurrency of
workflows][concurrency] says what a group does.

## The `on` key

GitHub reads `on` as an event name, a list of names or a mapping with one key
for each name. The check reads the three forms. The YAML parser of the check
follows YAML 1.1, where the plain word `on` is the boolean true, so the check
accepts the key `on` both as that boolean and as a quoted string. A value of
another shape, such as a number, gives no event: actionlint reports it.

A finding about an event sits on the line of the event: the line of the name
for a single name, the line of the item for a list, and the line of the event
key for a mapping.

## Files

The check reads the files that the [`versions` check](versions.md) reads as
workflows: every `.yml` or `.yaml` file directly in a folder `.github/workflows`
at any depth of the tree, and every file of that kind directly in the folder
`workflow-templates` at the root. One module, `nix/scripts/decisions/workflow_files.py`,
selects and parses them for both checks. The `workflows` check doesn't read an
`action.yml`: a composite action has no jobs of its own to limit and no events.
A file that isn't valid YAML or isn't UTF-8 text is a finding, because it could
hide a job.

## Output

Each finding prints as `path:line: message`, and one run prints all of them.
The line of a missing time limit is the line of the job. The line of an invalid
time limit is the line of the key `timeout-minutes`. The exit status is 0 for
no finding, 1 for findings, 2 for a usage error or a file that can't be read,
and 3 for an internal error.

| Finding | Message |
| ------- | ------- |
| A job has no `timeout-minutes` | `job "<id>" has no timeout-minutes; set timeout-minutes to a whole number from 1 to 360 or to an expression` |
| A job has an invalid value | `job "<id>" has timeout-minutes <value>; set timeout-minutes to a whole number from 1 to 360 or to an expression` |
| A pull request workflow has no group | `the workflow runs on <event> and has no concurrency group; set concurrency at the top level or on every job` |

## Run the check

```console
nix build .#checks.x86_64-linux.workflows -L
```

A repository adds the check with `lib.mkWorkflowsCheck`, as
[Adopt the hub in a repository](../how-to/adopt-the-hub.md) shows. The function
takes the package set and the source tree:

```nix
workflows = hub.lib.mkWorkflowsCheck pkgs self;
```

It builds its tool from the hub's own nixpkgs, whatever nixpkgs the repository
follows. The check has no option and no exclusion. The tests of the check are
the checks `check-workflows-tests`, for the tool, and `lib-functions`, for the
function.

[call-keywords]: https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations
[limits]: https://docs.github.com/en/actions/reference/limits
[concurrency]: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
