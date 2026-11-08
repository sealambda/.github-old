# Adopt the hub in a repository

Use the hub's parts in a Sealambda repository. Adopt the parts the repository
needs. The sections that add a check or run a hub app use the hub input of
[Add the toolchain](#add-the-toolchain). The community files need no step,
because GitHub applies them.

## Add the toolchain

Add the hub as a flake input that the repository's nixpkgs follows, so that
every repository evaluates one nixpkgs revision.

1. Add the hub input, the development shell, the formatter and the formatting
   check to the repository's `flake.nix`. Replace `node` with a dev shell from
   [Toolchain versions](../reference/versions.md). Put the repository's own
   treefmt-nix modules in the list that `mkTreefmt` takes.

   The snippet defines every output for the three systems that the hub
   supports. `forAllSystems` applies a function to the package set of each
   system, and the later snippets of this page add their checks to the set that
   `checks` builds with it. CI runs `nix flake check` on Linux, so a check that
   only `aarch64-darwin` defines doesn't run there.

   ```nix
   {
     inputs = {
       hub.url = "github:sealambda/.github";
       nixpkgs.follows = "hub/nixpkgs";
     };

     outputs =
       {
         self,
         nixpkgs,
         hub,
         ...
       }:
       let
         systems = [
           "x86_64-linux"
           "aarch64-linux"
           "aarch64-darwin"
         ];
         forAllSystems =
           f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
         treefmtFor = forAllSystems (pkgs: hub.lib.mkTreefmt pkgs [ ]);
       in
       {
         devShells = forAllSystems (pkgs: {
           default = pkgs.mkShell {
             inputsFrom = [ hub.devShells.${pkgs.stdenv.hostPlatform.system}.node ];
           };
         });
         formatter = forAllSystems (
           pkgs: treefmtFor.${pkgs.stdenv.hostPlatform.system}.config.build.wrapper
         );
         checks = forAllSystems (pkgs: {
           formatting = treefmtFor.${pkgs.stdenv.hostPlatform.system}.config.build.check self;
         });
       };
   }
   ```

2. Run `nix flake lock`, then `nix flake check`.

The repository's `flake.lock` pins the hub. To take a newer hub revision, run
`nix flake update hub`. Renovate opens the same update as a pull request.

## Run a hub app

The hub offers the app `sync-config`. Run an app in the repository, with the
option `--inputs-from .`:

```sh
nix run --inputs-from . hub#<app>
```

The option makes `hub` mean the hub revision that the repository's `flake.lock`
pins, so the app is the version that the checks run. The address
`github:sealambda/.github#<app>` without the option runs the latest `main` of
the hub, which can differ from the pinned revision.

The command needs the `hub` input and its lock, which
[Add the toolchain](#add-the-toolchain) creates. A repository without a `hub`
input has no pinned revision, and Nix stops with the error `cannot find flake
'flake:hub' in the flake registries`. Add the input first.

## Extend the Renovate preset

Renovate resolves `github>sealambda/.github` to `default.json` at the root of
the hub.

1. Extend the preset in the repository's `renovate.json`:

   ```json
   {
     "$schema": "https://docs.renovatebot.com/renovate-schema.json",
     "extends": ["github>sealambda/.github"]
   }
   ```

2. Keep the repository's own `enabledManagers`, `constraints` and
   `packageRules` in the same file. Don't repeat a setting that the
   [preset](../reference/renovate-preset.md) already sets. To change one, such
   as the `schedule`, set it in the repository.

## Sync the tool configuration

Some tools read only a file in the repository. The `sync-config` app copies
the hub's version of each file into the repository.

1. Run `nix run --inputs-from . hub#sync-config` in the repository root, as
   [Run a hub app](#run-a-hub-app) explains. Commit the files that it writes.
2. Create the `Repository` Vale vocabulary,
   `.vale/styles/config/vocabularies/Repository/accept.txt`, with one term per
   line. An empty file is valid. The synced `.vale.ini` lists this vocabulary,
   and Vale stops with an error when a listed vocabulary is missing.
3. Run Vale in the hub's `docs` dev shell. Its Vale comes from the hub's
   `vale.withStyles` package, which sets `VALE_STYLES_PATH`, so Vale finds the
   Microsoft and Readability styles in the Nix store. The project `StylesPath`,
   `.vale/styles`, holds only the tracked vocabularies. Don't run
   `vale sync`: the synced `.vale.ini` lists no packages. Don't pass
   `--no-global`: that flag makes Vale ignore `VALE_STYLES_PATH`, and Vale
   then stops with the error "Style isn't on StylesPath."

   To reproduce the gate, run `nix build .#checks.<system>.docs -L`, as
   [Gate the documentation](#gate-the-documentation) describes. For an
   interactive run, enter the dev shell and run Vale on a file, with no flags:

   ```sh
   nix develop .#docs
   vale <file>
   ```

   Define the repository's own `docs` shell with `inputsFrom =
   [ hub.devShells.<system>.docs ]`, or add the same Vale package to it.

   If an earlier `vale sync` left a style directory such as
   `.vale/styles/Microsoft`, delete each style directory but keep `config`:
   `rm -rf -- .vale/styles/Microsoft .vale/styles/Readability`. Vale takes a
   rule from the Nix style when both paths hold a rule of the same name, but a
   stale rule that only the old directory has still runs. Keep, or add, these
   two rules in the repository's `.gitignore`, so that nobody commits a
   leftover style directory:

   ```gitignore
   .vale/styles/*
   !.vale/styles/config/
   ```

   Outside `nix develop` or direnv, for example in an editor extension, Vale
   finds no styles and reports the same error. Start the editor from the dev
   shell, or use direnv with the flake.

4. To fail CI when a copy differs from the hub, add this attribute next to
   `formatting` in the set that `checks` defines through `forAllSystems`
   ([Add the toolchain](#add-the-toolchain)):

   ```nix
   config-in-sync = hub.lib.mkConfigCheck pkgs self;
   ```

The check compares the copies with the hub revision that `flake.lock` pins. To
take a newer revision, run `nix flake update hub`, then `sync-config`.

To relax a markdownlint rule for one directory, add a `.markdownlint-cli2.yaml`
to it. markdownlint-cli2 merges that file with the synced one at the root, as
the hub does in `.github`.

## Gate the documentation

The `docs` check lints every Markdown file with markdownlint-cli2, lychee and
Vale. Where the Nix sandbox is enabled, which it always is on Linux CI, the
check reads no personal configuration and needs no network. Every tool reads
its configuration from the repository, so the repository needs the files that
`sync-config` writes and the `Repository` Vale vocabulary
([Sync the tool configuration](#sync-the-tool-configuration)).

1. Add the check to the set that `checks` defines through `forAllSystems` in the
   repository's `flake.nix`. Pass `self`, not a list of Markdown files, because
   lychee also checks links to files that aren't Markdown.

   ```nix
   docs = hub.lib.mkDocsCheck pkgs self;
   ```

2. Run `nix flake check`. To run only this check, run
   `nix build .#checks.<system>.docs -L`, with your system for `<system>`, such
   as `aarch64-darwin`. CI needs no separate job: the
   job that runs `nix flake check` runs this check too.
3. If the repository called the hub's earlier `docs.yml` workflow, remove that
   call. The hub no longer offers the workflow.
   - Delete the `docs` job and its entry in the `needs` of the `ci` job.
   - Update any branch protection or ruleset that requires the status check of
     the `docs` job.
   - Replace each documented docs command, for example in `AGENTS.md`, with
     `nix flake check`.

For an interactive run or an editor, use the `docs` dev shell. A personal
global Vale configuration can change the result there. The check is the
reference result.

## Gate the decision records

The `decisions` check validates the front matter of the decision records and
the ledger of deleted records, and it fails on a citation of a record, a spec or
a page that doesn't resolve. [Decision records](../reference/decision-records.md)
defines each rule. The check reads no network and no personal configuration.

1. Add the check to the set that `checks` defines through `forAllSystems` in the
   repository's `flake.nix`. Pass `self`, because the check reads every text
   file. Set `repository` to the name of the repository on GitHub. The check
   uses it to tell a citation of this repository from a citation of another one.

   ```nix
   decisions = hub.lib.mkDecisionsCheck pkgs self {
     repository = "sealambda/<repo>";
     exclude = [ ];
   };
   ```

2. Run `nix build .#checks.<system>.decisions -L`. Each finding is a line
   `path:line: message`. CI needs no separate job: the job that runs
   `nix flake check` runs this check too.
3. Fix the findings of the first run. A record often has the status
   `superseded` or `deprecated`, which the schema doesn't allow: delete a
   replaced record and list it in the ledger, as the reference says.
4. Add a path to `exclude` for a file that holds citations on purpose, such as a
   test fixture. The path is relative to the root of the repository.

The check builds its tool from the hub's own nixpkgs, whatever nixpkgs the
repository follows. Every repository then runs the same version of the tool, and
`nix flake update hub` updates it. [ADR 0005](../decisions/0005-check-decision-records-with-a-hermetic-flake-check.md)
gives the reasons.

## Call the reusable workflow

The hub offers the reusable workflow `secrets.yml`. It runs its tool from the
repository's flake. The comment at the top of the workflow file states what the
flake must expose.

1. Call the workflow from a job. Pin it to a commit SHA, which Renovate bumps.
   The `runs-on` input is optional. It takes JSON.

   ```yaml
   jobs:
     secrets:
       uses: sealambda/.github/.github/workflows/secrets.yml@<sha>
       permissions:
         contents: read
       with:
         runs-on: '["ubuntu-24.04-arm"]'
   ```

2. List the job in the `needs` of the repository's `ci` job, as the hub's
   `.github/workflows/ci.yml` does.
