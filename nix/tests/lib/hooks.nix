# The cases of `lib.mkHooks` that need no Git: what `extraHooks` and `scanner`
# do. The stages and the refusals of the hooks run in real Git in
# `nix/tests/hooks.sh`. `default.nix` in this folder collects the cases below.
# A case that must fail with an evaluation error can't use `expectedLog`,
# because that only reads the log of a failed build, so these cases evaluate
# the function in Nix and build a derivation only when the outcome is right.
# Nix can't read the message of a failed evaluation: `builtins.tryEval` returns
# only whether it failed. A case of that kind pins the cause by the pair of
# calls instead: the call that must fail and the same call without the fault
# must differ in one name, and both force the same value.
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

  # Whether `mkHooks` with `extraHooks` evaluates. It forces the result of the
  # function and no part of the configuration that git-hooks.nix builds, so the
  # answer doesn't depend on the structure of that configuration: only the
  # check of the names in `mkHooks` can make it false.
  accepts =
    extraHooks:
    (builtins.tryEval (builtins.seq (hub.mkHooks { inherit pkgs src extraHooks; }) true)).success;

  # The command of the hook `secrets-scan` in the configuration of `mkHooks`
  # with the arguments `args` added to the call.
  secretsHookEntry =
    args:
    let
      hooks = hub.mkHooks ({ inherit pkgs src; } // args);
      hook = builtins.head (
        builtins.filter (hook: hook.id == "secrets-scan") (builtins.head hooks.config.rawConfig.repos).hooks
      );
    in
    hook.entry;

  # The command that a hook of the scanner `scanner` must run: the command of
  # `mkSecretsScan` with that scanner, and the subcommand for the index.
  secretsScanCommand =
    scanner: "${pkgs.lib.getExe (hub.mkSecretsScan { inherit pkgs scanner; })} staged";

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
  # The same call with another name for the hook works, so the failure comes
  # from the name, and the test doesn't read the configuration of
  # git-hooks.nix.
  hooks-extra-hook-with-a-hub-name-is-refused = {
    check = mustHold "extraHooks with the name docs was accepted, or the name my-hook was refused." (
      accepts { my-hook = extraHook; }
      && builtins.all (name: !(accepts { ${name} = extraHook; })) [
        "treefmt"
        "docs"
        "workflows"
        "secrets-scan"
        "gitpolicy-commit-msg"
        "gitpolicy-branch"
      ]
    );
  };

  # Requirement: without `scanner`, the hook `secrets-scan` runs the command
  # with gitleaks, the default of `mkSecretsScan`.
  hooks-default-scanner-is-gitleaks = {
    check =
      mustHold "The hook secrets-scan runs ${secretsHookEntry { }}, not the command with gitleaks."
        (secretsHookEntry { } == secretsScanCommand pkgs.gitleaks);
  };

  # Requirement: the `scanner` of the call is the scanner of the hook
  # `secrets-scan`. The command with betterleaks differs from the command with
  # gitleaks, so the case can tell the two apart.
  hooks-scanner-reaches-the-secrets-hook = {
    check =
      mustHold
        "The hook secrets-scan runs ${
          secretsHookEntry { scanner = pkgs.betterleaks; }
        }, not the command with betterleaks."
        (
          secretsHookEntry { scanner = pkgs.betterleaks; } == secretsScanCommand pkgs.betterleaks
          && secretsScanCommand pkgs.betterleaks != secretsScanCommand pkgs.gitleaks
        );
  };
}
