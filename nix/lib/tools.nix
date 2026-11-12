# The Python tools of the hub: `decisions`, `leaks`, `versions`, `workflows`,
# `presetcompat`, `gitpolicy` and `release`, each the package of the same name
# below `nix/scripts`. `flake.nix` imports this file for the apps and the
# checks, and `decisions.nix`, `workflows.nix` and `git-policy.nix` build
# `mkDecisionsCheck`, `mkWorkflowsCheck` and `mkGitPolicyTool` on their tools.
#
# The set holds one entry for each tool: the result of `mkPythonTool`
# (`python-tool.nix`), with `env`, the run-time environment for the tests of
# the package, and `mkTool`, which returns the command for one package set.
# The entry `decisions` also holds `python`, a function from a package set to
# the Python of `decisions` with its two libraries, for the checks that need it.
#
# A new tool needs more than an entry here. `python-quality` in `flake.nix`
# type-checks only the packages that its `mypy` command names, and it reads
# only the files in its `pythonQualitySource` fileset. `src` in `pyproject.toml`
# tells the import order check of ruff where the first-party code is. Add the
# package and its tests to all three places.
{ lib }:
let
  inherit ((import ./python-tool.nix { inherit lib; })) mkPythonTool;

  # The JSON Schemas of the hub, at the root of the repository.
  schemaDir = ../../schemas;

  # The Python with the two libraries that `decisions` imports. The quality
  # check adds mypy and the type stubs of both libraries.
  decisionsPython =
    pkgs:
    pkgs.python3.withPackages (ps: [
      ps.pyyaml
      ps.jsonschema
    ]);
in
{
  # The `decisions` command: `python -P -m decisions`, the code in
  # `nix/scripts/decisions`, with the schemas in `schemas`. `git` lists the
  # files of a work tree, so the check skips the ignored ones, and it is
  # for the `retire` subcommand. `python` is the Python of the command.
  decisions =
    mkPythonTool {
      name = "decisions";
      inherit schemaDir;
      runtimeInputs = pkgs: [
        (decisionsPython pkgs)
        pkgs.git
      ];
    }
    // {
      python = decisionsPython;
    };

  # The `leaks` command: `python -P -m leaks`, the code in `nix/scripts/leaks`.
  # It reports the private facts of an organization in a source tree. The
  # package imports only `decisions.walk` and `decisions.findings`, which use
  # only the standard library: this environment has no `pyyaml` or
  # `jsonschema`, which the other modules of `decisions` need.
  leaks = mkPythonTool {
    name = "leaks";
    uses = [ "decisions" ];
    runtimeInputs = pkgs: [ pkgs.python3 ];
  };

  # The `versions` command: `python -P -m versions`, the code in
  # `nix/scripts/versions`. The package imports the findings, the schema
  # loading and the file listing of the package `decisions`, so it needs the
  # two libraries of `decisions` and its schemas.
  versions = mkPythonTool {
    name = "versions";
    uses = [ "decisions" ];
    inherit schemaDir;
    runtimeInputs = pkgs: [ (decisionsPython pkgs) ];
  };

  # The `workflows` command: `python -P -m workflows`, the code in
  # `nix/scripts/workflows`. It checks the time limits and the concurrency
  # groups of the workflows. The package imports the findings, the YAML reader
  # and the file selection of the package `decisions`, so it needs the library
  # of `decisions` that reads YAML.
  workflows = mkPythonTool {
    name = "workflows";
    uses = [ "decisions" ];
    runtimeInputs = pkgs: [ (decisionsPython pkgs) ];
  };

  # The `presetcompat` command: `python -P -m presetcompat`, the code in
  # `nix/scripts/presetcompat`. It checks that `v2.json` keeps the guarantees of
  # `default.json`. The package imports the findings of the package `decisions`,
  # and both use only the standard library.
  presetcompat = mkPythonTool {
    name = "presetcompat";
    uses = [ "decisions" ];
    runtimeInputs = pkgs: [ pkgs.python3 ];
  };

  # The `gitpolicy` command: `python -P -m gitpolicy`, the code in
  # `nix/scripts/gitpolicy`. It checks commit messages and branch names. The
  # package imports the runner of `git` of the package `release`, and `git`
  # reads the history. The package uses only the standard library.
  gitpolicy = mkPythonTool {
    name = "gitpolicy";
    uses = [ "release" ];
    runtimeInputs = pkgs: [
      pkgs.python3
      pkgs.git
    ];
  };

  # The `release` command: `python -P -m release`, the code in
  # `nix/scripts/release`. It plans and creates the release of a commit of
  # the hub. `git` answers the questions about the history, and `gh`
  # creates the release. The package uses only the standard library.
  release = mkPythonTool {
    name = "release";
    runtimeInputs = pkgs: [
      pkgs.python3
      pkgs.git
      pkgs.gh
    ];
  };
}
