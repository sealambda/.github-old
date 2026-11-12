# The workflow checks. `flake.nix` imports this file and exports
# `mkWorkflowsCheck` as `lib.mkWorkflowsCheck`, which a consumer calls. The
# tool that the check runs is `workflows` in `tools.nix`, and its code is
# `nix/scripts/workflows`.
{
  lib,
  hubPackagesFor,
  tools,
}:
{
  /**
    Builds a check that fails when a workflow of a source tree breaks one of
    two rules. Every job that does not call a reusable workflow needs
    `timeout-minutes`, a whole number from 1 to 360 or an expression. Every
    workflow that a `pull_request` or `pull_request_target` event triggers
    needs a `concurrency` group, at the top of the workflow or on every job.
    A workflow that only `workflow_call` triggers is exempt from the second
    rule. The files are the workflows in `.github/workflows` and the starter
    workflows in `workflow-templates`, as for the `versions` check. Each finding
    prints as `path:line: message`, and one run prints all of them. The rules
    are in `docs/reference/workflow-checks.md`. The check needs no network. The
    same command runs locally and in CI: `nix flake check`, or
    `nix build .#checks.<system>.workflows -L`.

    The tool comes from the hub's own nixpkgs, whatever nixpkgs the calling
    flake uses: the function takes only the system from `pkgs`. Every
    consumer then gets one version of the tool and of its Python library.
    `mkDecisionsCheck` does the same.

    Pass the whole `self` of the calling flake.

    # Inputs

    `pkgs`
    : The package set of one system. Only its system is used.

    `src`
    : The source tree to check, normally the `self` of the calling flake.

    # Type

    ```
    mkWorkflowsCheck :: AttrSet -> (Path | AttrSet) -> Derivation
    ```
  */
  mkWorkflowsCheck =
    pkgs: src:
    let
      hubPkgs = hubPackagesFor pkgs;
    in
    hubPkgs.runCommand "workflows" { } ''
      ${lib.getExe (tools.workflows.mkTool hubPkgs)} ${src}
      touch "$out"
    '';
}
