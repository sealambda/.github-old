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
- **Nix version.** `versions.json` holds the version of Nix that the
  organization standardizes on, with a JSON Schema in `schemas/`. The hub's
  workflows install that version with `cachix/install-nix-action`, and the
  flake check `versions` fails when a step sets another `install_url` or uses
  an installer of Nix that it knows by name or address. An unknown installer
  passes, and review covers it.
- **Dependency updates.** `default.json`, a shared
  [Renovate](https://docs.renovatebot.com/) preset for update timing,
  grouping and security fixes. A repository's `renovate.json` extends it and
  adds only its own managers, constraints and rules.
- **Tool configuration.** Settings for the tools that read only a file in the
  repository: EditorConfig, markdownlint-cli2, Vale and lychee. The
  `sync-config` app copies the files, and the `config-in-sync` check fails
  when a copy differs.
- **CI building blocks.** The reusable workflow `secrets.yml` (gitleaks), the
  flake check `lib.mkDocsCheck` (markdownlint-cli2, lychee and Vale with the
  hub's own style, which keeps pages in the present tense), and the
  flake check `lib.mkDecisionsCheck`, which validates the decision records and
  every citation of a record, a spec or a page. The JSON Schemas of the records
  and the ledger are in `schemas/`. The `decisions` app retires a record into
  the ledger.

## Documentation

The pages follow [Diátaxis](https://diataxis.fr/).

- **How-to guides.**
  [Adopt the hub in a repository](docs/how-to/adopt-the-hub.md),
  [Change a toolchain version](docs/how-to/change-a-toolchain-version.md),
  [Retire a decision record](docs/how-to/retire-a-decision-record.md) and
  [Add third-party content](docs/how-to/add-third-party-content.md).
- **Reference.** [Toolchain versions](docs/reference/versions.md),
  [Elixir quality checks](docs/reference/elixir-qa.md), the
  [Renovate preset](docs/reference/renovate-preset.md),
  [decision records](docs/reference/decision-records.md),
  [writing style](docs/reference/writing-style.md), the
  [leak check](docs/reference/leak-check.md) and
  [licensing](docs/reference/licensing.md).
- **Explanation.** The [decision records](docs/decisions/) say why the hub
  works as it does. [ADR 0005](docs/decisions/0005-check-decision-records-with-a-hermetic-flake-check.md)
  explains the decision records check.
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
