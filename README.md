# Sealambda hub

This repository holds Sealambda's engineering standards. It isn't a community
project. It's public because GitHub reads default community files only from a
public `.github` repository, and private repositories consume it without
credentials ([ADR 0002](docs/decisions/0002-public-hub-repository.md)). It
holds no secrets and no operational detail, and the
[leak check](docs/reference/leak-check.md) fails when a file holds a private
name or identifier.

Sealambda repositories consume it. Each repository adopts the parts it needs
and keeps its own facts.

## What it provides

- **Community files.** `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md`, the
  issue forms and the pull request template. GitHub shows them in every
  repository of the organization, public or private, that has no file of its
  own ([GitHub documentation](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file)).
  A repository inherits them without any step. A file of the same name in the
  repository overrides one.
- **Toolchain.** A Nix flake with pinned development shells and the
  organization's treefmt configuration, `lib.mkTreefmt`.
- **Nix version.** `versions.json` holds the version of Nix that the hub's CI
  runs, with a JSON Schema in `schemas/`. A repository that calls the reusable
  workflow `secrets.yml` runs the same version. The hub's workflows install it
  with `cachix/install-nix-action`, and the flake check `versions` fails when a
  step sets another `install_url` or uses an installer of Nix that it knows by
  name or address. An unknown installer passes, and review covers it. The
  check reads only the hub's own files, and the other workflows of a consumer
  choose their own Nix.
- **Releases.** Every merge to `main` is covered by a release, a tag
  `v1.<minor>.<patch>` on the merged commit or on a later one. The first line
  of the note says
  `rules changed: yes` or `rules changed: no`
  ([Hub releases](docs/reference/hub-releases.md)).
- **Dependency updates.** `default.json`, a shared
  [Renovate](https://docs.renovatebot.com/) preset for update timing,
  grouping and security fixes. A repository's `renovate.json` extends it and
  adds only its own managers, constraints and rules.
- **Tool configuration.** Settings for the tools that read only a file in the
  repository: EditorConfig, markdownlint-cli2, Vale and lychee. The
  `sync-config` app copies the files, and the `config-in-sync` check fails
  when a copy differs. The `docs` check and the `docs` dev shell take the
  rules of the last three from the hub without a copy, and a repository's own
  file adds to them ([Wrapped documentation tools](docs/reference/wrapped-tools.md)).
- **CI building blocks.** The reusable workflow `secrets.yml` (gitleaks), the
  flake check `lib.mkDocsCheck` (markdownlint-cli2, lychee and Vale, each
  wrapped with the hub's base configuration, and the hub's own Vale style,
  which keeps pages in the present tense), and the
  flake check `lib.mkDecisionsCheck`, which validates the decision records and
  every citation of a record, a spec or a page. The JSON Schemas of the records
  and the ledger are in `schemas/`. The `decisions` app retires a record into
  the ledger. The flake check `lib.mkWorkflowsCheck` fails when a job has no
  `timeout-minutes` or when a pull request workflow has no `concurrency`
  group ([Workflow checks](docs/reference/workflow-checks.md)). The tool
  `gitpolicy`, as `lib.mkGitPolicyTool`, checks that a commit header is a
  Conventional Commit and that a branch name is `<type>/<slug>`. It runs in CI
  and in a Git hook that a repository adds, because a flake check sees no
  history
  ([Git policy](docs/reference/git-policy.md)). The command `secrets-scan`, as
  `lib.mkSecretsScan`, scans the history or the staged changes with a secret
  scanner, gitleaks by default, and the hub's base configuration
  ([Secrets scan](docs/reference/secrets-scan.md)).

## Documentation

The pages follow [Diátaxis](https://diataxis.fr/).

- **How-to guides.**
  [Adopt the hub in a repository](docs/how-to/adopt-the-hub.md),
  [Change a toolchain version](docs/how-to/change-a-toolchain-version.md),
  [Retire a decision record](docs/how-to/retire-a-decision-record.md),
  [Add third-party content](docs/how-to/add-third-party-content.md),
  [Release the hub](docs/how-to/release-the-hub.md),
  [Test a hub function](docs/how-to/test-a-hub-function.md) and
  [Run the synthetic consumer](docs/how-to/run-the-synthetic-consumer.md).
- **Reference.** [Toolchain versions](docs/reference/versions.md),
  [Elixir quality checks](docs/reference/elixir-qa.md), the
  [Renovate preset](docs/reference/renovate-preset.md),
  [decision records](docs/reference/decision-records.md),
  [writing style](docs/reference/writing-style.md), the
  [leak check](docs/reference/leak-check.md),
  [workflow checks](docs/reference/workflow-checks.md), the
  [Git policy](docs/reference/git-policy.md),
  [wrapped documentation tools](docs/reference/wrapped-tools.md),
  [secrets scan](docs/reference/secrets-scan.md),
  [licensing](docs/reference/licensing.md),
  [CI of the hub](docs/reference/hub-ci.md) and
  [hub releases](docs/reference/hub-releases.md).
- **Explanation.** The [decision records](docs/decisions/) say why the hub
  works as it does. [ADR 0005](docs/decisions/0005-check-decision-records-with-a-hermetic-flake-check.md)
  explains the decision records check, and
  [ADR 0006](docs/decisions/0006-check-commits-and-branches-with-a-hub-tool.md)
  explains why the Git policy is a hub tool.
  [ADR 0007](docs/decisions/0007-layer-the-repository-configuration-over-a-hub-base.md)
  explains how a repository's configuration layers over the hub's base.
- **Templates.** [Templates](templates/README.md) for decision records and
  pages.

## Contribute

Read [CONTRIBUTING.md](CONTRIBUTING.md). To report a vulnerability, read
[SECURITY.md](SECURITY.md).

## License

The hub is licensed under the [Mozilla Public License 2.0](LICENSE), SPDX
identifier `MPL-2.0`. [Licensing](docs/reference/licensing.md) lists the
third-party content and the license of each part, and the flake check
`licenses` verifies the data.
