# The standards of the hub in one call. `flake.nix` imports this file and
# exports `mkStandards` as `lib.mkStandards`, which a consumer calls. The
# function composes the functions that a consumer can also call one by one:
# `mkTreefmt`, `mkDocsCheck`, `mkDecisionsCheck`, `mkWorkflowsCheck`,
# `mkSecretsScan`, `mkGitPolicyTool` and `mkHooks`. It holds no rule and no
# tool of its own, so a rule changes in one place. The arguments, the result
# and the limits are in the reference page on the standards contract. The
# check of the arguments is `standards-arguments.nix`.
{
  lib,
  hubPackagesFor,
  mkTreefmt,
  mkDocsTools,
  mkDocsCheck,
  mkDecisionsCheck,
  mkWorkflowsCheck,
  mkGitPolicyTool,
  mkSecretsScan,
  defaultScanner,
  mkHooks,
  tools,
}:
let
  inherit ((import ./standards-arguments.nix { inherit lib; })) argumentProblems;

  # The standards of one repository on one system, for arguments that
  # `argumentProblems` accepted. `mkStandards` documents the arguments and the
  # result.
  build =
    {
      pkgs,
      src,
      name,
      treefmtModules ? [ ],
      decisions ? { },
      hooks ? { },
      scanner ? defaultScanner pkgs,
    }:
    let
      hubPkgs = hubPackagesFor pkgs;
      treefmt = mkTreefmt pkgs treefmtModules;
      docsTools = mkDocsTools hubPkgs;
      hooksResult = mkHooks {
        inherit
          pkgs
          src
          treefmt
          scanner
          ;
        extraHooks = hooks;
      };
    in
    {
      checks = {
        formatting = treefmt.config.build.check src;
        docs = mkDocsCheck pkgs src;
        decisions = mkDecisionsCheck pkgs src {
          repository = "sealambda/${name}";
          exclude = decisions.exclude or [ ];
        };
        workflows = mkWorkflowsCheck pkgs src;
        pre-commit = hooksResult;
      };

      hooks = hooksResult;

      formatter = treefmt.config.build.wrapper;

      packages = {
        inherit (docsTools) vale markdownlint-cli2 lychee;
        secrets-scan = mkSecretsScan { inherit pkgs scanner; };
        gitpolicy = mkGitPolicyTool pkgs;
        workflows = tools.workflows.mkTool hubPkgs;
      };
    };
in
{
  /**
    Builds the standards of the hub for one repository on one system: the
    checks, the formatter and the commands that the hub offers, from one call.
    A consumer calls it once for each system and puts the parts of the result
    into its outputs. The result is the same as the one that a call of each
    function by hand gives, and the reference page on the standards contract
    lists the parts and what each one does.

    The result has these attributes:

    - `checks` has `formatting`, `docs`, `decisions`, `workflows` and
      `pre-commit`. They are the checks of `lib.mkTreefmt`,
      `lib.mkDocsCheck`, `lib.mkDecisionsCheck`, `lib.mkWorkflowsCheck` and
      `lib.mkHooks`. There is no `config-in-sync`: a repository that calls
      this function holds no copy of the hub's tool configuration.
    - `formatter` is the treefmt wrapper, for the `formatter` output.
    - `packages` has `vale`, `markdownlint-cli2`, `lychee`, `secrets-scan`,
      `gitpolicy` and `workflows`. Each one has `meta.mainProgram`. The
      repository puts them in a dev shell, or runs them in CI.
    - `hooks` is the evaluation that `lib.mkHooks` returns. The function
      installs nothing. A repository opts in to the installation when it puts
      `hooks.shellHook` in the `shellHook` of one dev shell, as
      `docs/reference/hooks.md` shows. Without that line, the repository gets
      the check `pre-commit` and no hook.

    The tools of the documentation, decisions and workflow checks, the
    commands and the tools of the hooks come from the hub's own nixpkgs,
    whatever nixpkgs the calling flake uses. The formatter doesn't: treefmt-nix
    evaluates with `pkgs`, so the formatter programs follow the nixpkgs of the
    calling flake. The check `pre-commit` runs the hooks `treefmt`, `docs` and
    `workflows` again, and it scans no secret, because the check commits the
    source before the hook reads the staged changes. A wrong argument stops the
    evaluation with one message that lists every problem, and a name that a hub
    hook uses in `hooks` stops it with the message of `lib.mkHooks`.

    # Inputs

    `pkgs`
    : The package set of one system. Only its system is used for the tools. The
      formatter modules evaluate with it.

    `src`
    : The source tree of the repository, normally the `self` of the calling
      flake. The checks read all of it. It is a path, a set with `outPath`, or
      a string that holds an absolute path, such as `"${self}"`. A relative
      string is an error.

    `name`
    : The name of the repository on GitHub, without the owner, such as
      `quints`. The owner is `sealambda`, so the decisions check treats a
      citation of `sealambda/<name>` as a citation of this repository. GitHub
      allows 1 to 100 ASCII letters, digits, `.`, `-` and `_`, so the function
      accepts that and refuses the empty string, `.` and `..`. The name
      `.github` is valid.

    `treefmtModules`
    : A list of treefmt-nix modules of the repository. They add to the
      organization's formatter, in `formatter`, in `checks.formatting` and in
      the hook `treefmt`. Default empty.

    `decisions`
    : A set that holds `exclude`, a list of paths that the citation scan of the
      decisions check skips, as in `lib.mkDecisionsCheck`. Default
      `{ exclude = [ ]; }`.

    `hooks`
    : Hooks of the repository, in the format of git-hooks.nix. They add to the
      hub's hooks, as `extraHooks` does in `lib.mkHooks`. Default empty.

    `scanner`
    : The package of the secret scanner, with the requirements that
      `lib.mkSecretsScan` lists. It is the scanner of `packages.secrets-scan`
      and of the hook `secrets-scan`. The default is gitleaks of the hub's
      nixpkgs.

    # Type

    ```
    mkStandards :: {
      pkgs :: AttrSet;
      src :: Path | String | AttrSet;
      name :: String;
      treefmtModules :: [Module] ? [ ];
      decisions :: { exclude :: [String] ? [ ]; } ? { exclude = [ ]; };
      hooks :: AttrSet ? { };
      scanner :: Derivation ? <hub gitleaks>;
    } -> {
      checks :: { formatting; docs; decisions; workflows; pre-commit :: Derivation; };
      formatter :: Derivation;
      packages :: { vale; markdownlint-cli2; lychee; secrets-scan; gitpolicy; workflows :: Derivation; };
      hooks :: Derivation;
    }
    ```
  */
  mkStandards =
    args:
    let
      problems = argumentProblems args;
    in
    assert lib.assertMsg (
      problems == [ ]
    ) "mkStandards: the arguments are wrong.\n- ${lib.concatStringsSep "\n- " problems}";
    build args;
}
