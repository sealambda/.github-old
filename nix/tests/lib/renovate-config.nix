# The cases of `lib.mkRenovateConfigCheck`. `default.nix` in this folder
# collects them. A case holds the check applied to a fixture and, for a case
# that must fail, the text that the log of the failure holds. The texts are the
# messages of the validator of the hub's nixpkgs.
{
  pkgs,
  hub,
  harness,
}:
let
  inherit (pkgs) lib;

  # A tree whose files are `files`, by path.
  tree =
    name: files:
    harness.mkTree {
      name = "renovate-config-${name}";
      inherit files;
    };

  # A tree whose files are `files`, by path, and then the effects of the shell
  # commands `setup`, such as a symbolic link.
  treeWith =
    name: files: setup:
    harness.mkTree {
      name = "renovate-config-${name}";
      inherit files setup;
    };

  # A valid configuration, and one with an option that Renovate doesn't know.
  valid = ''
    {
      "$schema": "https://docs.renovatebot.com/renovate-schema.json",
      "extends": ["github>sealambda/.github"]
    }
  '';
  unknownOption = ''
    { "nope": true }
  '';

  check = hub.mkRenovateConfigCheck pkgs;

  inherit (harness) mustHold;

  # Whether the evaluation of the check for the value `presets` succeeds. The
  # derivation path is forced, which runs the check of the argument.
  evaluatesWith =
    presets: (builtins.tryEval (check (tree "presets-type" { }) { inherit presets; }).drvPath).success;

  # The configuration files that Renovate reads, written out here and not taken
  # from the script, so a name that the script drops loses its case. The case
  # `renovate-config-names-match-renovate` compares the names of the script with
  # the list in the Renovate package, so this list can't fall behind either. The
  # key is the part of the name of the case, and the value is the path.
  configFiles = {
    root-json = "renovate.json";
    root-jsonc = "renovate.jsonc";
    root-json5 = "renovate.json5";
    github-json = ".github/renovate.json";
    github-jsonc = ".github/renovate.jsonc";
    github-json5 = ".github/renovate.json5";
    gitlab-json = ".gitlab/renovate.json";
    gitlab-jsonc = ".gitlab/renovate.jsonc";
    gitlab-json5 = ".gitlab/renovate.json5";
    renovaterc = ".renovaterc";
    renovaterc-json = ".renovaterc.json";
    renovaterc-jsonc = ".renovaterc.jsonc";
    renovaterc-json5 = ".renovaterc.json5";
  };

  # Valid configurations that a strict JSON parser rejects. Renovate reads
  # them: its own parser, `parseFileConfig` of Renovate 44, returns the same
  # object for each of them, and for the file with a byte order mark it logs a
  # warning that the file is JSON5 and not JSON.
  byteOrderMark = builtins.fromJSON ''"﻿"'';
  withComment = ''
    {
      // The comment that Renovate strips.
      "extends": ["github>sealambda/.github"]
    }
  '';
  withTrailingComma = ''
    { "extends": ["github>sealambda/.github"], }
  '';

  # A package that holds the key `renovate`, which the validator can't check.
  packageWith = renovate: ''{ "name": "fixture", "renovate": ${renovate} }'';

  # A tree that holds a preset outside the source. The source is the folder
  # `inner`, and `../outside.json` is a file that exists and is not valid.
  presetOutside = tree "preset-outside" {
    "inner/renovate.json" = valid;
    "outside.json" = unknownOption;
  };

  # The check that every name of Renovate has a place in the script. The
  # derivation takes the names from the lines of the array `config_files` of the
  # script, adds the file of the key `renovate`, and compares the sorted list
  # with the list of the Renovate package of the hub's nixpkgs, which Node reads
  # from the file that Renovate uses to find its configuration. It fails and
  # prints the difference when a Renovate upgrade adds or drops a name.
  namesMatchRenovate =
    pkgs.runCommand "renovate-config-names-match-renovate" { nativeBuildInputs = [ pkgs.nodejs ]; }
      ''
        script=${../../scripts/renovate-config.sh}
        awk '/^config_files=\(/ { inside = 1; next } /^\)/ { inside = 0 } inside { print $1 }' \
          "$script" > script-names
        awk -F= '/^package_file=/ { print $2 }' "$script" >> script-names
        sort script-names > script-sorted
        node --input-type=module -e '
          const names = await import("${pkgs.renovate}/lib/node_modules/renovate/dist/config/app-strings.js");
          console.log(names.getConfigFileNames().join("\n"));
        ' | sort > renovate-sorted
        test -s script-sorted
        diff -u script-sorted renovate-sorted
        touch "$out"
      '';

  # One case for each file: an invalid file at that path fails the check.
  invalidFileCases = lib.mapAttrs' (
    label: path:
    lib.nameValuePair "renovate-config-invalid-${label}-fails" {
      check = check (tree "invalid-${label}" { ${path} = unknownOption; }) { };
      expectedLog = [ "Invalid configuration option: nope" ];
    }
  ) configFiles;
in
{
  # Requirement: a valid file passes the check.
  renovate-config-valid-file-passes = {
    check = check (tree "valid" { "renovate.json" = valid; }) { };
  };

  # Requirement: a tree with no Renovate file passes, so a repository that
  # doesn't use Renovate keeps its checks.
  renovate-config-no-file-passes = {
    check = check (tree "no-file" { "README.md" = "# Title\n"; }) { };
  };

  # Requirement: the file in `.github` is read, and a valid one passes. The
  # case `renovate-config-invalid-github-json-fails` shows that it is read.
  renovate-config-github-folder-file-passes = {
    check = check (tree "github-folder" { ".github/renovate.json" = valid; }) { };
  };

  # Requirement: a listed preset that is valid passes.
  renovate-config-valid-preset-passes = {
    check = check (tree "valid-preset" { "default.json" = valid; }) {
      presets = [ "default.json" ];
    };
  };

  # Requirement: an option that Renovate doesn't know fails the check, and the
  # log names the option.
  renovate-config-unknown-option-fails = {
    check = check (tree "unknown-option" { "renovate.json" = unknownOption; }) { };
    expectedLog = [ "Invalid configuration option: nope" ];
  };

  # Requirement: a value of the wrong type fails the check, and the log names
  # the option and the type.
  renovate-config-wrong-type-fails = {
    check = check (tree "wrong-type" { "renovate.json" = ''{ "enabled": "yes" }''; }) { };
    expectedLog = [ "Configuration option `enabled` should be boolean" ];
  };

  # Requirement: a file that is not valid JSON fails the check.
  renovate-config-invalid-json-fails = {
    check = check (tree "invalid-json" { "renovate.json" = ''{ "extends": [''; }) { };
    expectedLog = [ "File could not be parsed" ];
  };

  # Requirement: a configuration that needs a migration fails the check, as
  # `config:base` does, because Renovate renames it. This is the effect of
  # `--strict`: without it the same file passes.
  renovate-config-needed-migration-fails = {
    check = check (tree "needed-migration" {
      "renovate.json" = ''{ "extends": ["config:base"] }'';
    }) { };
    expectedLog = [ "Config migration necessary" ];
  };

  # Requirement: a file is read as the configuration of a repository, so an
  # option that only a server may set fails the check. This is the effect of
  # `--no-global`: as global configuration the same file passes.
  renovate-config-global-option-fails = {
    check = check (tree "global-option" { "renovate.json" = ''{ "autodiscover": true }''; }) { };
    expectedLog = [ "reserved only for Renovate's global configuration" ];
  };

  # Requirement: a listed preset is validated, wherever it lies. The same file
  # passes when nothing lists it, because its name is not one that Renovate
  # reads.
  renovate-config-invalid-preset-fails = {
    check = check (tree "invalid-preset" { "v2.json" = unknownOption; }) {
      presets = [ "v2.json" ];
    };
    expectedLog = [ "Invalid configuration option: nope" ];
  };

  renovate-config-unlisted-preset-is-not-read = {
    check = check (tree "unlisted-preset" { "v2.json" = unknownOption; }) { };
  };

  # Requirement: a listed preset that doesn't exist ends with status 2, and the
  # log names the file.
  renovate-config-missing-preset-fails = {
    check = check (tree "missing-preset" { "renovate.json" = valid; }) {
      presets = [ "v2.json" ];
    };
    expectedLog = [ "preset file not found: v2.json" ];
    expectedExitCode = 2;
  };

  # Requirement: `presets` must be a list of strings. A string fails the
  # evaluation, and so does a list that holds a path: without the check the
  # path becomes a store path in the command, and the check reads a file that
  # is not in the source. Each case holds a list of strings as its control, so
  # a fixture that never evaluates can't pass it.
  renovate-config-presets-string-is-refused = {
    check = mustHold "The call with a string for presets evaluates, or the control fails." (
      evaluatesWith [ "default.json" ] && !evaluatesWith "default.json"
    );
  };

  renovate-config-presets-path-item-is-refused = {
    check = mustHold "The call with a path in presets evaluates, or the control fails." (
      evaluatesWith [ "default.json" ] && !evaluatesWith [ ./renovate-config.nix ]
    );
  };

  # Requirement: the script reads every name that the installed Renovate reads.
  renovate-config-names-match-renovate = {
    check = namesMatchRenovate;
  };

  # Requirement: the key `renovate` of `package.json` fails the check, and the
  # log names the key and says to move the configuration to a file. Renovate
  # reads the key, and the validator can't check it.
  renovate-config-package-json-key-fails = {
    check = check (tree "package-json-key" {
      "package.json" = packageWith ''{ "extends": ["github>sealambda/.github"] }'';
    }) { };
    expectedLog = [
      ''package.json holds the key "renovate"''
      "Move the configuration to a file"
    ];
  };

  # Requirement: Renovate reads a string in the key as a preset to extend, so
  # that form fails the check too.
  renovate-config-package-json-string-key-fails = {
    check = check (tree "package-json-string-key" {
      "package.json" = packageWith ''"github>sealambda/.github"'';
    }) { };
    expectedLog = [ ''package.json holds the key "renovate"'' ];
  };

  # Requirement: the key fails the check next to a valid file, and the validator
  # still reads the file.
  renovate-config-package-json-key-with-invalid-file-fails = {
    check = check (tree "package-json-key-and-file" {
      "package.json" = packageWith ''{ "extends": ["github>sealambda/.github"] }'';
      "renovate.json" = unknownOption;
    }) { };
    expectedLog = [
      ''package.json holds the key "renovate"''
      "Invalid configuration option: nope"
    ];
  };

  # Requirement: a `package.json` that Renovate doesn't read as configuration
  # passes: one without the key, one whose key is false, and one that isn't
  # JSON.
  renovate-config-package-json-without-key-passes = {
    check = check (tree "package-json-no-key" { "package.json" = ''{ "name": "fixture" }''; }) { };
  };

  renovate-config-package-json-false-key-passes = {
    check = check (tree "package-json-false-key" { "package.json" = packageWith "false"; }) { };
  };

  renovate-config-package-json-not-json-passes = {
    check = check (tree "package-json-not-json" { "package.json" = "not json"; }) { };
  };

  # Requirement: a configuration name that is a link to nothing ends with status
  # 2, and the log names the file. Without this rule the tree counts as having
  # no file.
  renovate-config-dangling-link-fails = {
    check = check (treeWith "dangling-link" { } ''
      mkdir .github
      ln -s missing.json .github/renovate.json
    '') { };
    expectedLog = [ "dangling symbolic link: .github/renovate.json" ];
    expectedExitCode = 2;
  };

  # Requirement: a link to a file that exists is read like the file.
  renovate-config-link-to-invalid-file-fails = {
    check = check (treeWith "link-to-file" { "real.json" = unknownOption; } ''
      ln -s real.json renovate.json
    '') { };
    expectedLog = [ "Invalid configuration option: nope" ];
  };

  # Requirement: a preset path that leaves the source ends with status 2, even
  # when the file exists. Without this rule the check reads `../outside.json`,
  # a file outside the source.
  renovate-config-preset-outside-source-fails = {
    check = check "${presetOutside}/inner" { presets = [ "../outside.json" ]; };
    expectedLog = [ "preset path leaves the source: ../outside.json" ];
    expectedExitCode = 2;
  };

  renovate-config-absolute-preset-fails = {
    check = check (tree "absolute-preset" { "renovate.json" = valid; }) {
      presets = [ "/etc/hosts" ];
    };
    expectedLog = [ "preset path leaves the source: /etc/hosts" ];
    expectedExitCode = 2;
  };

  # Requirement: a JSON file with a byte order mark, a comment or a trailing
  # comma passes, as Renovate reads each of them.
  renovate-config-json-with-byte-order-mark-passes = {
    check = check (tree "byte-order-mark" { "renovate.json" = byteOrderMark + valid; }) { };
  };

  renovate-config-json-with-comment-passes = {
    check = check (tree "comment" { "renovate.json" = withComment; }) { };
  };

  renovate-config-json-with-trailing-comma-passes = {
    check = check (tree "trailing-comma" { "renovate.json" = withTrailingComma; }) { };
  };
}
// invalidFileCases
