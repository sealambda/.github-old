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
| `docs` | Vale style Sealambda | The hub's `vale/Sealambda` folder |

## Nix

The dev shells hold no Nix. The CI installs it, so its version isn't a nixpkgs
attribute. The file `versions.json` at the root of the hub holds the version
that the organization standardizes on:

```json
{
  "$schema": "./schemas/versions.schema.json",
  "nix": "2.35.4"
}
```

The [schema](../../schemas/versions.schema.json) follows JSON Schema draft
2020-12. The key `nix` is required and holds `MAJOR.MINOR.PATCH`, the version
in the name of a release at `releases.nixos.org`. The key `$schema` is
optional, for editors. The file holds no other key: nixpkgs pins every other
tool.

### Who reads it

Each step that uses `cachix/install-nix-action` sets the input `install_url`
to the installer of that release:

```yaml
- uses: cachix/install-nix-action@<revision>
  with:
    install_url: https://releases.nixos.org/nix/nix-2.35.4/install
```

Without `install_url`, the action installs the version that its own revision
carries as its default, and an update of the action changes Nix without a
change in the hub. The hub's `ci.yml` and `secrets.yml` set it. A repository
that calls the reusable workflow `secrets.yml` runs the same Nix.

A developer's local Nix isn't checked, and neither is the `nix` package of the
locked nixpkgs. The version in `versions.json` is the one that the hub's CI
runs.

### The check

The flake check `versions` reads `versions.json` and every workflow and action
of the hub. The only accepted way to install Nix in a workflow or a composite
action is `cachix/install-nix-action` with the `install_url` of
`versions.json`. The check reports each of these:

- `versions.json` is missing, isn't JSON, repeats a key in an object, or
  breaks the schema. A version with a line break, such as `"2.35.4\n"`, breaks
  the schema.
- A step that uses `cachix/install-nix-action` has an `install_url` that isn't
  exactly the installer address of the version in `versions.json`. A missing
  `install_url` and an expression are findings too.
- A `uses` step installs Nix with another action, because the check can't read
  the version that it installs. The name of the action, `owner/name` in any
  case, holds the word `nix` together with `install` in either order, or one
  of the fragments `determinate-nix`, `nix-quick-install`, `lix-installer`,
  `install-nix` and `nix-installer`. The word `nix` starts the name, follows a
  character that isn't a letter or a digit, or follows `install`, so the name
  `phoenix-install` isn't a finding.
- A `run` script downloads or runs another installer. The script, in any
  case, holds `nixos.org/nix/install`, `releases.nixos.org/nix/`,
  `install.determinate.systems`, `install.lix.systems` or `nix-installer`.

The files are every `.yml` or `.yaml` file directly in a folder
`.github/workflows`, at any depth of the tree, so a workflow skeleton under
`templates/` is read, every `.yml` or `.yaml` file directly in the folder
`workflow-templates` at the root of the tree, and every `action.yml` or
`action.yaml` below the root. The folder `workflow-templates` holds the
[starter workflows][starter] of an organization when the repository is its
`.github` repository. A starter workflow is a workflow file, so it follows the
same rules. The hub has no starter workflows, and a repository that has some
gets them checked. The `.properties.json` and icon files of that folder aren't
YAML, so the check skips them, and so it skips a file in a subfolder of
`workflow-templates` or in a `workflow-templates` folder below the root.
A file in a subfolder of `workflows` isn't a workflow, because GitHub doesn't
run it. A file that isn't valid YAML is a finding, because it could hide a
step. A local action (`uses: ./path`) and a Docker image are skipped, and the
`action.yml` of a local action is read.

[starter]: https://docs.github.com/en/actions/how-tos/reuse-automations/create-workflow-templates

Each finding prints as `path:line: message`, and one run prints all of them.
A finding appears once: when a YAML anchor makes two `steps` lists one node,
the two steps have the same path, line and message, and the run prints that
finding once.
The exit status is 0 for no finding, 1 for findings, 2 for a usage error or a
file that can't be read, and 3 for an internal error. When `versions.json` is
invalid, the version is unknown, so the check skips the addresses and still
reports the other installers.

The check knows the other installers by name and by address, and the list is
the constant `KNOWN_INSTALLERS` in `nix/scripts/versions/installers.py`. An
installer that the list doesn't match passes. Examples are an action with an
unrelated name, a script that builds the address of an installer from parts,
a Docker image, and a binary that a repository holds. Review covers these.
The check doesn't prove that no other Nix runs in the CI.

```console
nix build .#checks.x86_64-linux.versions -L
```

The tests of the check are the check `check-versions-tests`. To change the
version, follow [Change a toolchain version](../how-to/change-a-toolchain-version.md).

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
