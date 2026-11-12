# The cases of `lib.mkHooks` that need no Git: what `extraHooks` does. The
# stages and the refusals of the hooks run in real Git in
# `nix/tests/hooks.sh`. `default.nix` in this folder collects the cases below.
# A case that must fail with an evaluation error can't use `expectedLog`,
# because that only reads the log of a failed build, so these cases evaluate
# the function in Nix and build a derivation only when the outcome is right.
{
  pkgs,
  hub,
  harness,
}:
let
  # A source tree that holds the root file of the formatter. The cases never
  # run the hooks, so the content doesn't matter.
  src = harness.mkTree {
    name = "hooks";
    files."flake.nix" = "{ }\n";
  };

  # A hook of a repository, with the fields that every hook needs.
  extraHook = {
    enable = true;
    entry = "true";
  };

  # The ids of the hooks in the configuration of `mkHooks` with `extraHooks`.
  hookIds =
    extraHooks:
    let
      hooks = hub.mkHooks { inherit pkgs src extraHooks; };
    in
    map (hook: hook.id) (builtins.head hooks.config.rawConfig.repos).hooks;

  # A derivation that builds when `condition` is true and fails the evaluation
  # with `message` when it is false.
  mustHold =
    message: condition:
    assert pkgs.lib.assertMsg condition message;
    pkgs.runCommand "holds" { } ''
      touch "$out"
    '';
in
{
  # Requirement: a hook in `extraHooks` runs in addition to the hooks of the
  # hub, and it doesn't replace any of them.
  hooks-extra-hook-is-added = {
    check =
      let
        ids = hookIds { my-hook = extraHook; };
      in
      mustHold "The hooks are ${builtins.toJSON ids}, and my-hook or a hub hook is missing." (
        builtins.all (id: builtins.elem id ids) [
          "my-hook"
          "treefmt"
          "docs"
          "workflows"
          "secrets-scan"
          "gitpolicy-commit-msg"
          "gitpolicy-branch"
        ]
      );
  };

  # Requirement: a hook in `extraHooks` that has the name of a hub hook is an
  # error, so a repository can't replace a rule or switch it off by accident.
  # The case before this one shows that the same call without the name works,
  # so the failure here comes from the name.
  hooks-extra-hook-with-a-hub-name-is-refused = {
    check = mustHold "extraHooks with the name docs was accepted." (
      !(builtins.tryEval (builtins.deepSeq (hookIds { docs = extraHook; }) true)).success
    );
  };
}
