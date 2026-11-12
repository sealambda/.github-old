# The wiring that every Python tool of the hub shares. The tools are the
# packages below `nix/scripts`. `tools.nix` calls `mkPythonTool` once for each
# tool, and `flake.nix` uses the results in its apps and checks.
{ lib }:
{
  /**
    Builds the run-time environment and the command of one Python package
    below `nix/scripts`. The command is `python -P -m <name>`.

    The source of the tool holds the package and the packages that it imports,
    and nothing else of `nix/scripts`, so a change to another package, or to
    `check-docs.sh`, does not rebuild the tool. The environment holds what the
    package finds at run time: itself, and the JSON Schemas when the tool reads
    them. Python cannot write byte code into the Nix store, so the environment
    turns it off.

    # Inputs

    `name`
    : The name of the package, of the command and of the Python module.

    `uses`
    : The names of the other packages below `nix/scripts` that the package
      imports, default empty.

    `schemaDir`
    : The folder of the JSON Schemas that the package reads through
      `DECISIONS_SCHEMA_DIR`, default none.

    `runtimeInputs`
    : A function from a package set to the packages that the command needs on
      its `PATH`: the Python and the libraries of the tool, and the commands
      that it runs.

    # Type

    ```
    mkPythonTool :: { name :: String; uses :: [String]; schemaDir :: Path | Null; runtimeInputs :: AttrSet -> [Derivation]; } -> { env :: AttrSet; mkTool :: AttrSet -> Derivation; }
    ```

    `env` is the run-time environment, for a check that runs the tests of the
    package. `mkTool` takes a package set and returns the command.
  */
  mkPythonTool =
    {
      name,
      uses ? [ ],
      schemaDir ? null,
      runtimeInputs,
    }:
    let
      source = lib.fileset.toSource {
        root = ../scripts;
        fileset = lib.fileset.unions (map (package: ../scripts + "/${package}") ([ name ] ++ uses));
      };

      env = {
        PYTHONPATH = "${source}";
        PYTHONDONTWRITEBYTECODE = "1";
      }
      // lib.optionalAttrs (schemaDir != null) { DECISIONS_SCHEMA_DIR = "${schemaDir}"; };
    in
    {
      inherit env;
      mkTool =
        pkgs:
        pkgs.writeShellApplication {
          inherit name;
          runtimeInputs = runtimeInputs pkgs;
          runtimeEnv = env;
          # `-P` keeps the current directory off `sys.path`: the command runs in
          # the repository of the caller, and a file there must not replace a
          # module of the standard library or the package of the tool.
          text = ''exec python -P -m ${name} "$@"'';
        };
    };
}
