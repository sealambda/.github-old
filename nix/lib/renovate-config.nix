# The Renovate configuration gate. `flake.nix` imports this file and exports
# `mkRenovateConfigCheck` as `lib.mkRenovateConfigCheck`, which a consumer
# calls. `standards.nix` adds the check to `mkStandards`. The script that the
# check runs is `nix/scripts/renovate-config.sh`, and the rules are in
# `docs/reference/renovate-config-check.md`.
{ lib, hubPackagesFor }:
{
  /**
    Builds a check that fails when a Renovate configuration file of a source
    tree is not valid. The files are the names that Renovate reads at the
    root, such as `renovate.json`, `.github/renovate.jsonc` and
    `.renovaterc.json5`, and each path in `presets`. A tree with none of them
    passes. The check runs `renovate-config-validator --strict --no-global` on
    the files, so a configuration that needs a migration fails too. It also
    fails when `package.json` holds the key `renovate`, which the validator
    can't check, when a configuration name is a dangling symbolic link, and
    when a preset path leaves `src`. The validator doesn't resolve `extends`,
    so a preset name that doesn't exist passes. The rules, the exit statuses
    and the limits are in
    `docs/reference/renovate-config-check.md`. The check needs no network. The
    same command runs locally and in CI: `nix flake check`, or
    `nix build .#checks.<system>.renovate-config -L`.

    The validator comes from the hub's own nixpkgs, whatever nixpkgs the
    calling flake uses: the function takes only the system from `pkgs`. Every
    consumer then runs one version of Renovate, which is the version that
    decides what a valid file is. `mkDocsCheck` does the same.

    Pass the whole `self` of the calling flake.

    # Inputs

    `pkgs`
    : The package set of one system. Only its system is used.

    `src`
    : The source tree to check, normally the `self` of the calling flake.

    `presets`
    : A list of file paths relative to the root of `src`, default empty. Each
      one is a shared preset that the repository publishes, such as
      `default.json`. The check validates it as a repository configuration,
      and it fails with exit status 2 when a listed file doesn't exist or its
      path leaves the root of `src`.

    # Type

    ```
    mkRenovateConfigCheck :: AttrSet -> (Path | AttrSet) -> { presets :: [String]; } -> Derivation
    ```
  */
  mkRenovateConfigCheck =
    pkgs: src:
    {
      presets ? [ ],
    }:
    let
      hubPkgs = hubPackagesFor pkgs;
      renovateConfig = hubPkgs.writeShellApplication {
        name = "renovate-config";
        runtimeInputs = [
          hubPkgs.renovate
          hubPkgs.jq
        ];
        text = builtins.readFile ../scripts/renovate-config.sh;
      };
    in
    hubPkgs.runCommand "renovate-config" { } ''
      HOME="$TMPDIR" ${lib.getExe renovateConfig} ${src} ${lib.escapeShellArgs presets}
      touch "$out"
    '';
}
