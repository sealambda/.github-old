# Adopt the hub in a repository

Use the hub's parts in a Sealambda repository. Each section below is
independent: adopt the parts the repository needs. The community files need no
step, because GitHub applies them.

## Add the toolchain

Add the hub as a flake input that the repository's nixpkgs follows, so that
every repository evaluates one nixpkgs revision.

1. Add the hub input, the development shell, the formatter and the formatting
   check to the repository's `flake.nix`. Replace `node` with a dev shell from
   [Toolchain versions](../reference/versions.md). Put the repository's own
   treefmt-nix modules in the list that `mkTreefmt` takes.

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
         pkgs = nixpkgs.legacyPackages.aarch64-darwin;
         treefmt = hub.lib.mkTreefmt pkgs [ ];
       in
       {
         devShells.aarch64-darwin.default = pkgs.mkShell {
           inputsFrom = [ hub.devShells.aarch64-darwin.node ];
         };
         formatter.aarch64-darwin = treefmt.config.build.wrapper;
         checks.aarch64-darwin.formatting = treefmt.config.build.check self;
       };
   }
   ```

2. Run `nix flake lock`, then `nix flake check`.

The repository's `flake.lock` pins the hub. To take a newer hub revision, run
`nix flake update hub`. Renovate opens the same update as a pull request.

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

1. Run `nix run github:sealambda/.github#sync-config` in the repository root.
   Commit the files that it writes.
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

   ```sh
   nix develop .#docs -c vale --minAlertLevel=error .
   ```

   Define the repository's own `docs` shell with `inputsFrom =
   [ hub.devShells.<system>.docs ]`, or add the same Vale package to it.

   If an earlier `vale sync` left a style directory such as
   `.vale/styles/Microsoft`, Git now shows it as untracked. Delete each style
   directory but keep `config`: `rm -rf -- .vale/styles/Microsoft
   .vale/styles/Readability`. Vale takes a rule from the Nix style when both
   paths hold a rule of the same name, but a stale rule that only the old
   directory has still runs. Remove any `.vale/styles/*` rule from
   `.gitignore`, because nothing writes there any more.

   Outside `nix develop` or direnv, for example in an editor extension, Vale
   finds no styles and reports the same error. Start the editor from the dev
   shell, or use direnv with the flake.

4. To fail CI when a copy differs from the hub, add the check to the
   repository's `flake.nix`:

   ```nix
   checks.aarch64-darwin.config-in-sync = hub.lib.mkConfigCheck pkgs self;
   ```

The check compares the copies with the hub revision that `flake.lock` pins. To
take a newer revision, run `nix flake update hub`, then `sync-config`.

To relax a markdownlint rule for one directory, add a `.markdownlint-cli2.yaml`
to it. markdownlint-cli2 merges that file with the synced one at the root, as
the hub does in `.github`.

## Call the reusable workflows

The hub offers `secrets.yml` and `docs.yml`. Each workflow runs its tools from
the repository's flake. The comment at the top of the workflow file states what
the flake must expose.

1. Call the workflow from a job. Pin it to a commit SHA, which Renovate bumps.
   The `runs-on` input is optional. It takes JSON.

   ```yaml
   jobs:
     docs:
       uses: sealambda/.github/.github/workflows/docs.yml@<sha>
       permissions:
         contents: read
       with:
         runs-on: '["ubuntu-24.04-arm"]'
   ```

2. List the job in the `needs` of the repository's `ci` job, as the hub's
   `.github/workflows/ci.yml` does.
