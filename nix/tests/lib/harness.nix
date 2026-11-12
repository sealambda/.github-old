# The helpers of the tests of the functions in `nix/lib`. `default.nix` in this
# folder calls them, and each case file (`docs.nix`, `decisions.nix`,
# `config.nix`, `treefmt.nix`) uses `mkTree` to write its fixtures. The case
# files that decide a case in the evaluation, `hooks.nix` and `standards.nix`,
# use `mustHold`.
{
  pkgs,
  syncConfig,
}:
let
  inherit (pkgs) lib;

  # Shell commands that write the text of each file of `files` below the
  # current directory. The file is writable and its folders are created.
  writeFiles =
    files:
    lib.concatStringsSep "\n" (
      lib.mapAttrsToList (
        path: text: "install -D -m 644 ${pkgs.writeText "fixture-file" text} ${lib.escapeShellArg path}"
      ) files
    );

  /**
    Turns one case into a derivation. The name of the derivation is the name
    of the case, so a failed build names the fixture that failed in its first
    line.

    A case that has `expectedLog` must fail: the derivation fails unless the
    check of the case fails with exit status 1 and its log holds each entry of
    `expectedLog`. The failure of the derivation then names the entry that the
    log lacks. A case without `expectedLog` must pass: the derivation is the
    check itself.

    # Inputs

    `name`
    : The name of the case, the attribute name in the case file.

    `case`
    : `{ check :: Derivation; expectedLog :: [String]; }`. `check` is the
      function under test, applied to a fixture. `expectedLog` is optional.
      An empty list is an error: the case would pass for any failure, so
      it could not tell the failure that the requirement names from another
      one.

    # Type

    ```
    toTest :: String -> { check :: Derivation; expectedLog :: [String]; } -> Derivation
    ```
  */
  toTest =
    name: case:
    let
      testName = "lib-${name}";
    in
    if case ? expectedLog then
      assert lib.assertMsg (
        case.expectedLog != [ ]
      ) "The case ${name} lists no expected log entry: any failure would pass it.";
      pkgs.testers.testBuildFailure' {
        name = testName;
        drv = case.check.overrideAttrs { name = "${testName}-subject"; };
        expectedBuilderExitCode = 1;
        expectedBuilderLogEntries = case.expectedLog;
      }
    else
      case.check.overrideAttrs { name = testName; };
in
{
  /**
    Builds a source tree from text, as a store path. Use it as the `src` of
    a function under test. The tree holds, in this order: the files of
    `sync-config` when `synced` is true, then the files of `files`, then the
    effects of `setup`.

    # Inputs

    `name`
    : The name of the fixture, for the store path.

    `synced`
    : Whether the tree starts with the tool configuration that
      `sync-config` writes. Default false.

    `files`
    : The text of each file, by its path in the tree. A file of `files`
      replaces a synced file with the same path.

    `setup`
    : Shell commands that run in the tree last, for a change that text
      cannot say, such as a removed file. Default empty.

    # Type

    ```
    mkTree :: { name :: String; synced :: Bool; files :: AttrSet; setup :: String; } -> Derivation
    ```
  */
  mkTree =
    {
      name,
      synced ? false,
      files ? { },
      setup ? "",
    }:
    pkgs.runCommand "fixture-${name}" { nativeBuildInputs = lib.optional synced syncConfig; } ''
      mkdir "$out"
      cd "$out"
      ${lib.optionalString synced "sync-config"}
      ${writeFiles files}
      ${setup}
    '';

  /**
    Builds a derivation for a case that the evaluation decides. The derivation
    builds when `condition` is true. When it is false, the evaluation fails
    with `message`, so a case that must fail with an evaluation error, which
    `expectedLog` can't read, still fails the check with a text that names the
    problem. Build `condition` from `builtins.tryEval` to ask whether an
    expression fails.

    # Inputs

    `message`
    : The text of the failure. It is evaluated only when `condition` is false.

    `condition`
    : A boolean.

    # Type

    ```
    mustHold :: String -> Bool -> Derivation
    ```
  */
  mustHold =
    message: condition:
    assert lib.assertMsg condition message;
    pkgs.runCommand "holds" { } ''
      touch "$out"
    '';

  /**
    Turns the cases of a case file into derivations, one for each case. See
    `toTest` for the shape of a case.

    # Type

    ```
    toTests :: AttrSet -> AttrSet
    ```
  */
  toTests = lib.mapAttrs toTest;
}
