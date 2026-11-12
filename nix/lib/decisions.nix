# The decision records gate. `flake.nix` imports this file and exports
# `mkDecisionsCheck` as `lib.mkDecisionsCheck`, which a consumer calls. The
# tool that the check runs is `decisions` in `tools.nix`, and its code is
# `nix/scripts/decisions`.
{
  lib,
  hubPackagesFor,
  tools,
}:
{
  /**
    Builds a check that fails when the decision records, the specs or the
    citations of a source tree are wrong. It reads the records in
    `docs/decisions/` and the ledger `docs/decisions/superseded.yaml`, and it
    reads every text file for citations of records, specs and `docs/` pages.
    Each finding prints as `path:line: message`, and one run prints all of
    them. The checks and the citation forms are in
    `docs/reference/decision-records.md`. The check needs no network. The
    same command runs locally and in CI: `nix flake check`, or
    `nix build .#checks.<system>.decisions -L`.

    The tool comes from the hub's own nixpkgs, whatever nixpkgs the calling
    flake uses: the function takes only the system from `pkgs`. Every
    consumer then gets one version of the tool and of its Python libraries.
    `mkDocsCheck` does the same.

    Pass the whole `self` of the calling flake.

    # Inputs

    `pkgs`
    : The package set of one system. Only its system is used.

    `src`
    : The source tree to check, normally the `self` of the calling flake.

    `repository`
    : The `owner/name` of the repository that holds `src`, for example
      `sealambda/.github`. A citation that another repository qualifies, as
      in `sealambda/<repo> ADR NNNN`, is about that repository, and the
      check skips it.

    `exclude`
    : A list of paths relative to the root of `src`, default empty. The
      citation scan skips each path and the files below it. A path matches
      whole components, so `a/b` skips `a/b/c.py` and not `a/bc.py`. Use it
      for files that hold citations on purpose, such as test fixtures.

    # Type

    ```
    mkDecisionsCheck :: AttrSet -> (Path | AttrSet) -> { repository :: String; exclude :: [String]; } -> Derivation
    ```
  */
  mkDecisionsCheck =
    pkgs: src:
    {
      repository,
      exclude ? [ ],
    }:
    let
      hubPkgs = hubPackagesFor pkgs;
      excludeFlags = lib.concatMapStringsSep " " (path: "--exclude ${lib.escapeShellArg path}") exclude;
    in
    hubPkgs.runCommand "decisions" { } ''
      ${lib.getExe (tools.decisions.mkTool hubPkgs)} check \
        --repository ${lib.escapeShellArg repository} \
        ${excludeFlags} ${src}
      touch "$out"
    '';
}
