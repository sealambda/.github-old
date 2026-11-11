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

A third rule sets `minimumReleaseAge` to `null` for the digest update of a
reusable workflow from this hub, which a repository pins with `uses:`. Renovate
ages that update by the date of the head commit of the `main` branch, and the
wait exists to let people vet third-party releases.

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
| The digest update of a reusable workflow from this hub isn't held back by `minimumReleaseAge`. The rule matches the `github-actions` manager, the dependency type `workflow` and the dependency name `sealambda/.github`. | The hub is the organization's own, so the wait only delays a fix. See [Timing](#timing). |

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
