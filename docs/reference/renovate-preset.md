# Renovate preset

`default.json` is the shared [Renovate](https://docs.renovatebot.com/)
preset. A repository extends it with `github>sealambda/.github`
([adopt the preset](../how-to/adopt-the-hub.md#extend-the-renovate-preset)).
A repository's `renovate.json` holds only what differs: its managers,
constraints and package rules. Renovate applies the package rules of the
repository after those of the preset, so a rule in the repository wins.

## Base presets

| Preset | Effect |
| ------ | ------ |
| `config:best-practices` | The Renovate maintainers' recommended configuration. It pins GitHub Actions and Docker images by digest, proposes configuration migrations, flags abandoned packages and enables lock file maintenance. |
| `:semanticCommits` | Commit messages and pull request titles use semantic prefixes. |
| `:semanticCommitTypeAll(build)` | Every commit uses the type `build`. |
| `:label(dependencies)` | Every pull request gets the label `dependencies`. |
| `:approveMajorUpdates` | A major version waits on the Dependency Dashboard until a person ticks it. |

The commit scope is `deps`, the Renovate default.

## Timing

All times are UTC, the Renovate default. The schedules use cron syntax, which
Renovate recommends over its deprecated text syntax. The minutes field is
always `*`, because Renovate has no minute granularity.

| Setting | Value |
| ------- | ----- |
| `schedule` | `* 0-9 * * 1`: Monday before 10:00. |
| `lockFileMaintenance` | `* 0-9 1 * *`: the first day of the month, before 10:00. |
| `minimumReleaseAge` | 7 days, for every package that has a release date. A withdrawn or compromised release is less likely to reach a repository. |

Renovate can't check the age of a lock file maintenance, a pin, a
replacement, a bump, a lock file update or a rollback, nor of a Nix flake
input that follows a Git ref, because none has a release date. The age check
stays pending for them and Renovate never creates the branch, so two rules
set `minimumReleaseAge` to `null` for these updates.

A repository that runs Renovate once a day needs a window of several hours,
because Renovate acts only when a run falls inside the window. A repository
that wants no window sets `schedule` to `["* * * * *"]`.

## Package rules

| Rule | Reason |
| ---- | ------ |
| Packages from the npm registry, which pnpm installs from, wait 7 days. | `config:best-practices` shortens the wait for that registry to 3 days. |
| Development dependencies keep their declared range. | `config:best-practices` pins them to one version. The lock file already fixes the resolved version. |
| One pull request for the Mix minor and patch versions. | Fewer pull requests and fewer deployments. |
| One pull request for the pnpm minor and patch versions. | The same. |
| One pull request for the Elixir quality tools: Credo, Dialyxir, `mix_audit` and Sobelow. | The tools move together. |
| One pull request for the GitHub Actions. | The same as Mix. |
| OpenTofu providers come from the OpenTofu registry. | `tofu init` uses that registry. |
| The `required_version` of a Terraform root is ignored. | It names OpenTofu, which Renovate would look up as Terraform. |

## Other settings

- The Nix manager is on, and Renovate updates `flake.lock`. A repository lists
  the managers it uses in `enabledManagers`.
- `osvVulnerabilityAlerts` is on. Renovate reads the OSV advisory database
  for direct dependencies, besides GitHub's Dependabot alerts. Renovate marks
  this option as experimental.

## Security fixes

The preset puts nothing in `vulnerabilityAlerts`. Renovate skips the
release-age wait and the schedule for a security fix. Two package rules add
the label `security` and decide the merge:

- A fix that changes only the lock file merges automatically after the checks
  pass.
- Any other fix changes a declared range or a major version. It opens as a
  draft pull request, and Renovate never merges it.

One exception follows from Renovate itself. Renovate forces its defaults for
`vulnerabilityAlerts` on a security fix, and these include no Dashboard
approval. A security fix for a major version therefore opens at once as a
draft pull request, without the tick that other majors need. The draft rule
keeps it from merging.

A repository that merges only through a person sets `automerge` to `false` in
a package rule that matches `isVulnerabilityAlert = true`.

## Version 2

`v2.json` is the second version of the preset. It sits next to `default.json`,
which doesn't change, so a repository moves when it chooses. A repository
extends it with `github>sealambda/.github:v2#<tag>`, where `<tag>` is a release
of the hub. Renovate reads `:v2` as the file `v2.json` and `#<tag>` as the Git
tag to read it from.

The file holds every rule of version 1 and extends no other file of the hub, so
a repository that pins a tag reads one file at that tag. Everything in the
sections above holds for version 2, except the changes below.

| Setting | Version 1 | Version 2 |
| ------- | --------- | --------- |
| `:approveMajorUpdates` | A major version waits on the Dependency Dashboard. | Dropped. A major version opens as a pull request with the label `major`. |
| `matchIsBreaking` | No rule. | A breaking version opens as a pull request with the label `breaking`. [Labels of a breaking update](#labels-of-a-breaking-update) lists the versioning schemes that report it. |
| Minor of a `0.x` version | No rule. | A minor update of a current version `0.x` opens with the label `breaking`. The rule covers the versioning schemes that don't report it. |
| `rebaseWhen` | The Renovate default. | `conflicted`: Renovate rebases a pull request only when it conflicts. A pull request that merges by itself is the exception: it rebases when it falls behind its base branch, as [Rebase](#rebase) says. |
| `lockFileMaintenance` | `* 0-9 1 * *`: the first day of the month, before 10:00. | `* 0-9 * * 1`: Monday before 10:00. |
| `mise` | The Renovate default. | `enabled` is `true`, stated in the file. |

The security rules of version 1 stay, so a security fix opens at once, as
[Security fixes](#security-fixes) says.

### The hub pin, the actions series and the hub input

The hub repository has two series of tags: `v1.2.3` for the preset and the
reusable workflows, and `actions-v1.2.3` for the actions series. Both are tags
of one repository, so Renovate sees one package, `sealambda/.github`, with the
tags of both series. Three package rules keep the series apart:

| Rule | Matches | Effect |
| ---- | ------- | ------ |
| Hub pin | The package `sealambda/.github` with a current value that starts with `v` and a digit | The `regex` versioning reads only tags of the form `v1.2.3`. The pull request opens on any day, in the group `Hub preset pin`. |
| Actions series | The package `sealambda/.github` with a current value that starts with `actions-v` | The `regex` versioning reads only tags of the form `actions-v1.2.3`. The pull request opens on any day, and Renovate never merges it, because the update changes a workflow. |
| Hub input | The Nix manager, the dependency named `hub`, the package `https://github.com/sealambda/.github` and the update types `digest`, `patch` and `minor` | The update changes only `flake.lock`. It opens on any day and merges when the checks pass. |

Without the `regex` versioning, a coercing versioning could read
`actions-v1.0.0` as the version `1.0.0` and offer it as an update of the pin.
The two current values can't match one tag, so one rule decides each
dependency. The versioning reads the group `major`, `minor` and `patch` of the
tag. Renovate 44.181.0 gave `1` as the major of `v1.2.3` for the pin, rejected
`actions-v1.2.3` there, and did the reverse for the actions series.

"Any day" means the schedule only: the rules set `schedule` to an empty list.
The wait of 7 days still applies to the hub pin and the actions series. Their
data source, `github-tags`, gives each tag a release date, and no rule removes
the wait for them. The hub input has no wait, because its Git ref has no
release date, as [Timing](#timing) says.

The Nix manager reads a flake input with the `git` versioning. That versioning
parses only a commit hash, and it gives every hash the same version number, so
Renovate 44.181.0 reports a new revision as `digest` or `patch` and never as
`major`. The hub input rule lists `minor` too, though the manager doesn't report
it, and leaves `major` out. If a major update ever appears, it follows the
schedule and waits for a person.

The hub input merges with no wait and no person, so it's the one route to the
code of the hub that has neither. It relies on the review rules of the hub
repository, which are meant to let a commit reach the ref that the input
follows only through a reviewed pull request. The preset can't check that. The
rule matches the
package as well as the name `hub`, so an input of that name that points to
another repository gets no automatic merge. The Nix manager names the package
`https://github.com/<owner>/<repo>` for an input of the type `github`. An input
of another type, such as a `git` URL, doesn't match, and its update waits for a
person.

A repository whose merge of `flake.lock` deploys, or that doesn't trust the
review rules of the hub, keeps the update for a person. It sets `automerge` to
`false` in a package rule of its own that matches the dependency `hub`.

### Rebase

`rebaseWhen` is `conflicted` for every update. A rebase dismisses an approval
in a repository that dismisses a stale review, so Renovate rebases a pull
request that a person reviews only when it conflicts.

A pull request that Renovate merges by itself has no approval to keep, and
`conflicted` would stall it: a repository that requires an up-to-date branch
refuses the merge, and Renovate never brings the branch up to date. Two package
rules set `rebaseWhen` to `behind-base-branch` for these pull requests: the hub
input rule, and a rule that repeats the matcher of the security rule that
merges a fix inside the declared range. The security rule comes from
`default.json` and version 2 may not change it, so the second rule sits beside
it. Renovate reads `rebaseWhen` in a package rule, and the validator accepts it
there.

### Labels of a breaking update

A major update gets the label `major`. The label `breaking` comes from two
rules, and which one labels an update depends on the versioning of the package.
Renovate decides `matchIsBreaking` with the check `isBreaking` of the
versioning. A versioning without that check reports an update as breaking only
when it's a major update. The second rule matches a minor update of a current
version that starts with `0.` or `v0.`, whatever the versioning says.

The table shows what Renovate 44.181.0 reports for the versioning schemes that
have the check. The values come from calling the check of each versioning with
the pairs `0.1.0` to `0.2.0`, `0.1.0` to `0.1.1`, `1.2.3` to `2.0.0` and
`1.2.3` to `1.3.0`. The source of the checks of `semver` and `cargo` adds one
case that no pair covers: the check returns true when the current or the new
version is a prerelease, so an update from or to a prerelease is breaking. The
checks of `npm`, `composer` and `semver-coerced` call the check of `semver`.

| Versioning | Where Renovate uses it | `matchIsBreaking` is true for |
| ---------- | ---------------------- | ----------------------------- |
| `semver`, `npm`, `composer`, `semver-coerced` | The npm data source, which pnpm uses, and the Composer manager | A major update, every update of a `0.x` version, patches included, and an update from or to a prerelease. |
| `cargo` | The Cargo manager | A major update, a minor update of `0.x`, any change of `0.0.x`, and an update from or to a prerelease. |
| `python` | The `devbox` manager | Any major or minor update. |
| `github-actions`, `semver-partial` | The GitHub Actions manager, and the mise and GitLab CI managers | Nothing. The check returned false for all four pairs. |
| No check, such as `hex`, `docker`, `pep440`, `maven`, `git`, `regex` | The Hex data source, which Mix uses, the Docker data source, the Nix manager, and the hub pin and the actions series | A major update only. |

So the second rule labels these updates:

- A minor update of `0.x` for the versioning schemes that have no check, and for
  `github-actions` and `semver-partial`.
- The same update for the hub pin, because its tag `v0.2.0` starts with `v0.`.
  The tag `actions-v0.2.0` of the actions series doesn't match. Renovate never
  merges that update, so a person reviews it anyway.

These updates stay without the label `breaking`:

- A patch update of `0.x` for a versioning that has no check, for
  `github-actions` and `semver-partial`, and for `cargo` and `python`.
- A major update for `github-actions` and `semver-partial`. It gets the label
  `major` and no more.
- An update whose current version Renovate doesn't know, such as a range that
  no lock file resolves. The rule tests the locked version, then the current
  version, then the current value.

A calendar-style version that starts with `0.`, such as `0.2026.11`, is a `0.x`
version. A change of its second number is a minor update, so the second rule
gives it the label `breaking`, although a date isn't a promise about the API.
The label is the only effect: neither rule changes a schedule or a merge
decision.

A `breaking` label can come from both rules for one update, and Renovate adds
the label once.

### The check `presetcompat`

The command `presetcompat check default.json v2.json` compares the two files.
The flake check `presetcompat` runs it on the files of the hub, and the check
`renovate-config` validates `v2.json` like `default.json`. The command reports
each of these problems in `v2.json`:

- `minimumReleaseAge` isn't `"7 days"`.
- `osvVulnerabilityAlerts` isn't `true`.
- A package rule of `default.json` is missing or changed. Version 2 may add
  rules, and it may not change one.
- An `extends` item of `default.json` is missing. The one allowed removal is
  `:approveMajorUpdates`.
- `lockFileMaintenance.schedule` isn't a list with at least one entry, or
  `lockFileMaintenance.enabled` is `false`.
- `schedule` isn't a list with at least one entry.
- `rebaseWhen` isn't `"conflicted"`.
- A rule that sets `automerge` to `true` has no rule with the same matchers
  that sets `rebaseWhen` to `"behind-base-branch"`. The rule can be that rule
  itself.
- `enabled` is `false` at the top level, or `ignorePresets` is set, or the
  `enabled` key of `nix` or `mise` is `false`.
- A rule that version 2 adds sets `enabled` to `false`, or sets
  `minimumReleaseAge` below 7 days, to `null` or to a value that the tool can't
  read.
- A rule that version 2 adds sets `automerge` to `true` without a
  `matchUpdateTypes` list, or with a list that holds `major`.
- No rule adds the label `breaking` where `matchIsBreaking` is true, or no rule
  adds it to a minor update of a `0.x` version through a `matchCurrentVersion`
  in the form `/regex/`, or either rule has another matcher. A regex of the
  second rule must match `0.1.0` and `v0.1.0`, and not `1.0.0` or `10.0.0`.
- A rule that sets `automerge` to `true` for the dependency `hub` doesn't match
  the package `https://github.com/sealambda/.github`.
- The tag `v1.2.3` and the tag `actions-v1.2.3` don't each match exactly one
  rule for `sealambda/.github`, through its `matchCurrentValue` in the form
  `/regex/`. Or the `versioning` of that rule isn't a `regex:` value that reads
  its own tag and not the tag of the other series. Or the regex holds a
  look-ahead, a look-behind or a back reference, which the RE2 engine of
  Renovate rejects.

The command prints each problem as `path:line: message`, with line 1, because a
problem is about the file. The exit status is 0 when every invariant holds, 1
when one breaks, 2 when a file can't be read, isn't JSON or isn't an object, or
when the command line is wrong, and 3 for a bug in the tool.

A clean run proves that the files, read as JSON, keep the values and the rules
above. It doesn't prove how Renovate behaves. The tool doesn't run Renovate, so
it needs no network. It doesn't evaluate the package rules in the order in which
Renovate applies them, so a later rule can still override an earlier one. It
looks at the keys of one rule at a time. It checks the switches that the list
above names, not every `enabled` key: the `enabled` key of a manager other than
`nix` and `mise` isn't read. The code of that list is
`nix/scripts/presetcompat/guards.py`. It doesn't read the presets that `v2.json`
extends, so it can't tell what `config:best-practices` sets.

```console
nix build .#checks.x86_64-linux.presetcompat -L
nix build .#checks.x86_64-linux.check-presetcompat-tests -L
```

The check `check-presetcompat-tests` holds the unit tests. Each invariant has a
test that breaks it in a small pair of presets.

### Limits

Six things in version 2 are unverified. No test of the hub runs Renovate on a
real repository, and the validator checks the form of the file, not what the
rules do:

1. The flake input named `hub` is a convention. The rule matches the name
   `hub` and the package of the hub, and no repository has run it.
2. The pin and the actions series assume that Renovate reads the tag of the
   `extends` entry, and the comment of a pinned workflow, as the current value
   of the package `sealambda/.github`. The Renovate source gives that name and
   that value to the `extends` entry. No repository has run the path, and
   neither has the part that follows a tag of the hub into a nested `local>`
   reference, which is why the file holds every rule and doesn't extend another
   file.
3. The mise manager is on (`enabled` is `true`), and no test runs it.
4. `rebaseWhen` is `conflicted`, with `behind-base-branch` for the two rules
   that merge by themselves, and no test runs it. The values come from the
   Renovate documentation, and the reading of the two rules from the Renovate
   44.181.0 source, where `conflicted` stops the rebase of a branch that's only
   behind its base.
5. The rule that removes the wait for a flake input follows from the source of
   the Nix manager, which reads a Git ref and so has no release date. No test
   runs a flake input through the age check.
6. The two rules that add the label `breaking` rest on a reading of the
   Renovate 44.181.0 source and on calls of the check of each versioning.
   Renovate hasn't run them on a real update.

Other limits:

- The wait of 7 days for the hub pin and the actions series rests on the
  release dates that the `github-tags` data source reports. It stays pending
  for a tag that has no date.
- Lock file maintenance runs every week in version 2, so each repository that
  moves gets a pull request that often when the lock files change.
- `presetcompat` finds the rules for the hub tags by their `matchCurrentValue`
  in the form `/regex/`. A glob, a negated value and a regex with flags, such as
  `/^v/i`, count as no match.
- `presetcompat` reads a regex with the Python engine, and Renovate reads it
  with RE2 or JavaScript. The tool refuses the forms that RE2 rejects in the
  `versioning` of the two series. It doesn't compile the other regexes with
  RE2, so a form that only RE2 rejects can still pass elsewhere.
- `presetcompat` reads each added rule alone. It doesn't tell whether an
  earlier rule already removes the wait for the same package.
