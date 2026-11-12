# The Git policy tool. `flake.nix` imports this file and exports
# `mkGitPolicyTool` as `lib.mkGitPolicyTool`, which a consumer calls. The tool
# is `gitpolicy` in `tools.nix`, and its code is `nix/scripts/gitpolicy`. There
# is no check function: a flake check sees no Git history and no branch name,
# so the rules run in Git hooks and in CI, and the checks of the hub only test
# the rules.
{
  hubPackagesFor,
  tools,
}:
{
  /**
    Builds the `gitpolicy` command: `gitpolicy commit-msg FILE`,
    `gitpolicy range A..B` and `gitpolicy branch [NAME]`. It checks commit
    messages against Conventional Commits with the hub's limits, and branch
    names against `<type>/<slug>`. The rules and the exit statuses are in
    `docs/reference/git-policy.md`.

    The command comes from the hub's own nixpkgs, whatever nixpkgs the calling
    flake uses: the function takes only the system from `pkgs`. Every consumer
    then gets one version of the tool. A Git hook or a CI step runs the result
    with `lib.getExe`. The hub's own CI runs `nix run .#gitpolicy`.

    # Inputs

    `pkgs`
    : The package set of one system. Only its system is used.

    # Type

    ```
    mkGitPolicyTool :: AttrSet -> Derivation
    ```

    The derivation has `meta.mainProgram`, so `lib.getExe` finds the command.
  */
  mkGitPolicyTool = pkgs: tools.gitpolicy.mkTool (hubPackagesFor pkgs);
}
