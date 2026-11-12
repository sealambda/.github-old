---
status: accepted
date: 2026-11-12
decision-makers: Sealambda maintainers
---

# Gate the documentation with a flake check instead of a reusable workflow

## Context and Problem Statement

[ADR 0001](0001-hub-as-single-source-of-standards.md) lists reusable workflows
as the way to share CI steps. The hub's `docs.yml` workflow runs
markdownlint-cli2, lychee and Vale in `nix develop .#docs`. That design has two
costs. Vale reads the personal global configuration of each developer, so the
same command can give different results on two machines. The flag
`--no-global` stops that, but it also makes Vale ignore `VALE_STYLES_PATH`,
which the Nix package of the styles sets. With the workflow, a repeatable
result would need a step that links the styles into the project `StylesPath`,
and a garbage-collector root that keeps the linked styles alive. The workflow
has neither. How can one command give the same result locally and in CI,
without that glue?

## Decision Drivers

- One command for CI and for a developer, with the same result.
- No user configuration, no network and no state outside the repository.
- Every tool reads its configuration from the checked repository.
- Few lines of glue that a maintainer must own.
- A consumer adopts the change with one line in its flake.

## Considered Options

- Keep the reusable workflow
- A flake check
- git-hooks.nix

## Decision Outcome

Chosen option: "A flake check" because it runs in the Nix sandbox. The sandbox
has no user configuration, so Vale needs no `--no-global` and no link step, and
the same derivation runs locally and in CI.

The hub exports `lib.mkDocsCheck pkgs src`. It builds a derivation that runs
markdownlint-cli2, lychee and Vale on `src`. A repository adds
`checks.<system>.docs = hub.lib.mkDocsCheck pkgs self;` to its flake. The hub
does the same, and removes the `docs.yml` workflow and the `docs` job of its
`ci` workflow. This amends ADR 0001 for documentation only: `secrets.yml` stays
a reusable workflow, because gitleaks needs the Git history, which a flake
source doesn't contain.

The `docs` dev shell stays for interactive runs and editors.

### Consequences

- Good, because `nix flake check`, or `nix build .#checks.<system>.docs -L`, is
  the one command, in CI and locally.
- Good, because Nix caches the result by the hash of the source, so a local
  re-run on an unchanged tree doesn't check it again. CI gains this caching
  only with a binary cache.
- Good, because the check reads no personal configuration and, on Linux, has no
  network. lychee runs offline, and the Vale styles are in the Nix store.
- Good, because the gate needs no `--no-global` flag, link script or
  garbage-collector root.
- Bad, because this is a breaking change for each consumer: it must replace its
  `docs` job with the check and update any required-check rule that names the
  job.
- Bad, because a failure shows in the log of the `nix flake check` step, not in
  a separate job.
- Bad, because the Vale in the dev shell differs from the gate when a developer
  has a personal global configuration. The gate is the reference result.
- Bad, because Vale in an editor outside `nix develop` finds no styles.

## Pros and Cons of the Options

### Keep the reusable workflow

- Good, because it needs no change in a consumer.
- Bad, because Vale needs `--no-global` for a repeatable result, and that flag
  breaks the style lookup. The workflow would need a step that links the styles
  into `StylesPath` and a garbage-collector root for them. It has neither.
- Bad, because the workflow and a local run are two paths that can differ.

### A flake check

- Good, because it's the usual Nix form of a lint gate, as in treefmt-nix.
- Good, because the sandbox gives a repeatable result without a flag.
- Good, because it's cached and runs the same way everywhere.
- Bad, because a consumer must change its flake and its CI.

### git-hooks.nix

- Good, because it runs the same tools on a commit and in a flake check.
- Bad, because it adds an input and a layer to maintain for three commands.
- Bad, because a hook that runs Vale from a flake check meets the same Vale
  lookup problem, so it solves nothing that the flake check doesn't.

## More Information

- [Adopt the hub in a repository](../how-to/adopt-the-hub.md) shows how a
  repository adds the check.
- [treefmt-nix](https://github.com/numtide/treefmt-nix) builds its formatting
  check the same way.
- [git-hooks.nix](https://github.com/cachix/git-hooks.nix)
- [Nix sandbox](https://nix.dev/manual/nix/latest/command-ref/conf-file#conf-sandbox)
