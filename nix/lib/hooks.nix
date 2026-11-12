# The Git hooks. `flake.nix` imports this file and exports `mkHooks` as
# `lib.mkHooks`, which a consumer calls, and builds the hub's own hooks and its
# `pre-commit` check with it. The hooks run the tools that the hub already
# gives a repository: the formatter, the documentation check, the workflow
# check, `secrets-scan` and `gitpolicy`. This file only wires them to the Git
# stages. The input `git-hooks` (git-hooks.nix) turns the wiring into a
# configuration file for `prek`, and the hub's `hooks` dev shell installs it.
# The stages and the limits are in `docs/reference/hooks.md`, and the choice
# is in `docs/decisions/0008-offer-git-hooks-through-git-hooks-nix.md`.
{
  lib,
  git-hooks,
  hubPackagesFor,
  mkTreefmt,
  mkDocsTools,
  mkSecretsScan,
  mkGitPolicyTool,
  tools,
}:
{
  /**
    Builds the Git hooks of a repository: the formatter, the documentation
    check, the workflow check and the secret scan at `pre-commit`, the commit
    message rule at `commit-msg`, and the branch name rule at `pre-push`. The
    result is the evaluation that `git-hooks.nix` returns for one system:

    - `config.configFile` is the `prek` configuration. Every hook runs a tool
      by its store path, so the file needs nothing else on `PATH`.
    - `shellHook` installs the configuration and the hooks in the current
      repository. It replaces the local `core.hooksPath` of the repository. A
      `core.hooksPath` from the system or the global configuration, and a Git
      that can't read its configuration, end the shell with status 1 and
      change nothing. A repository with no work tree gets no installation, and
      the shell goes on. `docs/reference/hooks.md` explains each case. Put it
      in the `shellHook` of one dev shell. A shell that other shells include
      through `inputsFrom` passes the hook on to all of them, so use it in a
      shell of the repository that nothing includes, and not in the shell that
      people enter today.
    - `config.installationScript` is the script of the `shellHook` without the
      `PATH` change, with the same check. The tests of the hub run it.
    - `enabledPackages` lists the tools that the hooks use.
    - The derivation itself is the check `pre-commit`: it commits the source
      in a scratch repository and runs the `pre-commit` stage on every file. It
      runs no `commit-msg` and no `pre-push` hook.

    The tools come from the hub's own nixpkgs, whatever nixpkgs the calling
    flake uses, as in `mkDocsCheck`. The formatter is the one of the
    repository: pass the `treefmt` evaluation that the repository uses for
    `formatter`, so that the hook and `nix fmt` format the same way. The hooks
    are local and a person can skip them, so the CI checks stay the gate.

    # Inputs

    `pkgs`
    : The package set of one system. Only its system is used.

    `src`
    : The source tree of the repository, normally the `self` of the calling
      flake.

    `treefmt`
    : The evaluation that `mkTreefmt` returns, with the modules of the
      repository. The default is `mkTreefmt pkgs [ ]`, the formatter of the
      organization alone.

    `extraHooks`
    : Hooks of the repository, in the format of `git-hooks.nix`. They add to
      the hooks of the hub. A name that a hub hook already uses is an error,
      so a repository can't replace or switch off a rule by accident.

    # Type

    ```
    mkHooks :: {
      pkgs :: AttrSet;
      src :: Path | AttrSet;
      treefmt :: AttrSet ? <mkTreefmt pkgs [ ]>;
      extraHooks :: AttrSet ? { };
    } -> Derivation
    ```
  */
  mkHooks =
    {
      pkgs,
      src,
      treefmt ? mkTreefmt pkgs [ ],
      extraHooks ? { },
    }:
    let
      hubPkgs = hubPackagesFor pkgs;

      hubHooks = {
        # The formatter of the repository, on the files that the commit
        # changes. The flag `--fail-on-change` of the hook makes it fail after
        # it formats a file, so the person stages the result and commits again.
        treefmt = {
          enable = true;
          package = treefmt.config.build.wrapper;
        };

        # The check of the Markdown files runs on the whole work tree, because
        # lychee also checks the links to files that a changed page names. It
        # also runs when a staged file is a configuration file of its tools:
        # the result for every page depends on those files. The pattern names
        # the files that `docs/reference/wrapped-tools.md` lists as the
        # configuration of a repository.
        docs = {
          enable = true;
          name = "docs";
          description = "Lints the Markdown files with the hub's rules.";
          entry = "${lib.getExe (mkDocsTools hubPkgs).checkDocs} .";
          files = "\\.md$|(^|/)\\.markdownlint-cli2\\.|^(\\.vale/|\\.vale\\.ini$|lychee\\.toml$|\\.lycheeignore$)";
          pass_filenames = false;
        };

        workflows = {
          enable = true;
          name = "workflows";
          description = "Checks the time limits and the concurrency groups of the workflows.";
          entry = "${lib.getExe (tools.workflows.mkTool hubPkgs)} .";
          files = "^(\\.github/workflows|workflow-templates)/";
          pass_filenames = false;
        };

        # Runs on every commit, even when the changes hold no file that a
        # pattern selects: a deletion or a rename adds no line, and the
        # scanner decides that.
        secrets-scan = {
          enable = true;
          name = "secrets-scan";
          description = "Scans the staged changes for secrets.";
          entry = "${
            lib.getExe (mkSecretsScan {
              pkgs = hubPkgs;
            })
          } staged";
          always_run = true;
          pass_filenames = false;
        };

        # `prek` gives the hook the file with the commit message. The option
        # lets a `git commit --fixup` pass: a rebase folds that commit, and
        # `gitpolicy range` in CI fails it if it stays in the history.
        gitpolicy-commit-msg = {
          enable = true;
          name = "gitpolicy-commit-msg";
          description = "Checks that the commit header is a Conventional Commit.";
          entry = "${lib.getExe (mkGitPolicyTool hubPkgs)} commit-msg --allow-autosquash";
          stages = [ "commit-msg" ];
          always_run = true;
        };

        gitpolicy-branch = {
          enable = true;
          name = "gitpolicy-branch";
          description = "Checks that the branch name is `<type>/<slug>`.";
          entry = "${lib.getExe (mkGitPolicyTool hubPkgs)} branch";
          stages = [ "pre-push" ];
          always_run = true;
          pass_filenames = false;
        };
      };

      collisions = builtins.attrNames (builtins.intersectAttrs hubHooks extraHooks);

      evaluation = git-hooks.lib.${pkgs.stdenv.hostPlatform.system}.run {
        inherit src;
        package = hubPkgs.prek;
        hooks = hubHooks // extraHooks;
      };

      # The check that decides whether the installer may run, because the
      # installer goes on where it should stop. `nix/scripts/hooks-guard.sh`
      # says when, and `docs/reference/hooks.md` says why. The command exits
      # with status 0 to let the installer run, with status 1 to refuse, and
      # with status 2 to skip the installation.
      guardCommand = lib.getExe (
        hubPkgs.writeShellApplication {
          name = "hooks-guard";
          runtimeInputs = [ hubPkgs.git ];
          text = builtins.readFile ../scripts/hooks-guard.sh;
        }
      );

      # Puts the text of the installer behind the check. The installer runs on
      # status 0 only. Status 2 skips it and the shell goes on. Any other
      # status ends the shell with status 1. The `if` form is safe under
      # `set -e`, which would end a shell at status 2 in a plain command.
      withGuard = installer: ''
        if ${guardCommand}; then
        ${installer}
        elif [ $? != 2 ]; then
          exit 1
        fi
      '';
    in
    assert lib.assertMsg (collisions == [ ])
      "mkHooks: extraHooks reuses the name of a hub hook: ${lib.concatStringsSep ", " collisions}. Choose another name.";
    evaluation
    // {
      shellHook = withGuard evaluation.shellHook;
      config = evaluation.config // {
        installationScript = withGuard evaluation.config.installationScript;
      };
    };
}
