# The tool configuration that the hub copies into every repository. `flake.nix`
# imports this file. It uses `mkSyncConfig` for the `sync-config` app and for
# the tests of `nix/scripts/check-docs.sh`, and it exports `mkConfigCheck` as
# `lib.mkConfigCheck`, which a consumer calls.
{ lib }:
let
  # Tool configuration that a tool reads only from a file in the
  # repository. Each name is the path in the consumer; each value is the
  # hub's copy. `sync-config` writes the copies and `mkConfigCheck`
  # compares them.
  configFiles = {
    ".editorconfig" = ../../config/editorconfig;
    ".markdownlint-cli2.yaml" = ../../config/markdownlint-cli2.yaml;
    ".vale.ini" = ../../config/vale.ini;
    ".vale/styles/config/vocabularies/Sealambda/accept.txt" = ../../config/vale-vocabulary.txt;
    "lychee.toml" = ../../config/lychee.toml;
  };
in
{
  # Writes the copies into the current directory. `-m 644` makes each copy
  # writable, because the source is read-only in the Nix store. `-D` creates
  # the parent directories.
  mkSyncConfig =
    pkgs:
    pkgs.writeShellApplication {
      name = "sync-config";
      runtimeInputs = [ pkgs.coreutils ];
      text = lib.concatStringsSep "\n" (
        lib.mapAttrsToList (
          path: source: "install -D -m 644 ${source} ${lib.escapeShellArg path}"
        ) configFiles
      );
    };

  /**
    Builds a check that fails when a synced tool configuration file of a
    repository differs from the hub's file or is missing. The failure
    message names the `sync-config` command that repairs it: the pinned hub
    app of a calling repository, and the local app of the hub itself.

    # Inputs

    `pkgs`
    : The package set of one system.

    `src`
    : The source tree to compare, normally the `self` of the calling flake.

    # Type

    ```
    mkConfigCheck :: AttrSet -> (Path | AttrSet) -> Derivation
    ```
  */
  mkConfigCheck =
    pkgs: src:
    pkgs.runCommand "config-in-sync" { nativeBuildInputs = [ pkgs.diffutils ]; } ''
      status=0
      ${lib.concatStringsSep "\n" (
        lib.mapAttrsToList (path: source: "diff -u ${source} ${src}/${path} || status=1") configFiles
      )}
      if [ "$status" -ne 0 ]; then
        echo "A tool configuration differs from the hub." >&2
        echo "Run: nix run --inputs-from . hub#sync-config" >&2
        echo "In the hub repository itself, run: nix run .#sync-config" >&2
      fi
      touch "$out"
      exit "$status"
    '';
}
