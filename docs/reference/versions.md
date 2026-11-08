# Toolchain versions

The dev shells in the hub's `flake.nix` define the toolchain. A version is the
name of a nixpkgs attribute, and `flake.lock` pins one revision of
`nixpkgs-unstable`, so each attribute resolves to one exact package.

## Dev shells

Each shell except `base` includes `base` through `inputsFrom`. The `default`
shell is `base`.

| Shell | Package | nixpkgs attribute |
| ----- | ------- | ----------------- |
| `base` | actionlint | `actionlint` |
| `base` | git | `git` |
| `base` | gitleaks | `gitleaks` |
| `base` | zizmor | `zizmor` |
| `elixir` | Erlang/OTP 29 | `beam.packages.erlang_29.erlang` |
| `elixir` | Elixir 1.20 | `beam.packages.erlang_29.elixir_1_20` |
| `node` | Node.js 26 (LTS), without npm | `nodejs-slim_26` |
| `node` | pnpm 12 | `pnpm_12` |
| `tofu` | OpenTofu | `opentofu` |
| `docs` | lychee | `lychee` |
| `docs` | markdownlint-cli2 | `markdownlint-cli2` |
| `docs` | Vale | `vale` |
| `docs` | Vale style Microsoft | `valeStyles.microsoft` |
| `docs` | Vale style Readability | `valeStyles.readability` |

## Rules

- Toolchains come from `nixpkgs-unstable`.
- A consumer sets `inputs.nixpkgs.follows = "hub/nixpkgs"`, so every
  repository evaluates the same nixpkgs revision.
- Renovate bumps the nixpkgs revision in `flake.lock`. A major version changes
  only when the attribute name changes.
- Node.js moves between long-term support (LTS) majors only.
- Organization repositories use pnpm. They don't use npm, npx, Yarn, Bun or
  Corepack.
- Library versions stay in the lock file of each application.
