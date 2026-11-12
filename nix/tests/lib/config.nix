# The cases of `lib.mkConfigCheck`. `default.nix` in this folder collects them.
# A case holds the check applied to a fixture and, for a case that must fail,
# the text that the log of the failure holds. Each fixture starts from the
# files of `sync-config`, so the cases need no second list of config files.
{
  pkgs,
  hub,
  harness,
}:
let
  inherit (pkgs) lib;

  # A tree with the synced files, then the commands of `setup`.
  tree =
    name: setup:
    harness.mkTree {
      name = "config-${name}";
      synced = true;
      inherit setup;
    };

  configCheck = hub.mkConfigCheck pkgs;

  # The message that tells a person how to repair the tree.
  repairHint = "Run: nix run --inputs-from . hub#sync-config";

  # A path as one word for the name of a case: no slash.
  sanitize = path: lib.replaceStrings [ "/" ] [ "-" ] path;

  # Requirement: the check compares these five files, no more and no less:
  # `.editorconfig`, `.markdownlint-cli2.yaml`, `.vale.ini`, the Sealambda Vale
  # vocabulary and `lychee.toml`. The list is written here from the requirement
  # (`docs/how-to/adopt-the-hub.md`), not taken from the function, so a file
  # that the function drops does not drop its case.
  comparedPaths = [
    ".editorconfig"
    ".markdownlint-cli2.yaml"
    ".vale.ini"
    ".vale/styles/config/vocabularies/Sealambda/accept.txt"
    "lychee.toml"
  ];

  # The paths as sorted lines of text, so a missing, an extra and a
  # misspelled path each show in a diff.
  asLines = paths: lib.concatMapStrings (path: "${path}\n") (lib.sort lib.lessThan paths);

  # Requirement: a synced file that differs from the hub's file fails the
  # check, whichever file it is. The log names the file, shows the difference
  # and gives the command that repairs it. There is one case for each path of
  # `comparedPaths`, so a file that the check drops from its comparison
  # leaves its case green, and the case fails the test.
  differingCases = lib.listToAttrs (
    map (path: {
      name = "config-differing-${sanitize path}-fails";
      value = {
        check = configCheck (
          tree "differing-${sanitize path}" "echo '# local edit' >> ${lib.escapeShellArg path}"
        );
        expectedLog = [
          path
          "+# local edit"
          "A tool configuration differs from the hub."
          repairHint
        ];
      };
    }) comparedPaths
  );
in
{
  # Requirement: a tree with the files that `sync-config` writes passes the
  # check.
  config-synced-passes = {
    check = configCheck (tree "synced" "");
  };

  # Requirement: the function lists the same five files as `comparedPaths`.
  # `sync-config` and the check both build on that list, so a dropped entry
  # leaves every other case consistent and green. This case fails when the
  # list lacks one of the five files or holds another one, and its log shows
  # the difference.
  config-synced-paths-are-the-five-files = {
    check =
      pkgs.runCommand "config-synced-paths"
        {
          nativeBuildInputs = [ pkgs.diffutils ];
          expected = asLines comparedPaths;
          actual = asLines harness.syncedPaths;
          passAsFile = [
            "expected"
            "actual"
          ];
        }
        ''
          if ! diff -u "$expectedPath" "$actualPath"; then
            echo "The synced paths differ from the five compared files." >&2
            exit 1
          fi
          touch "$out"
        '';
  };

  # Requirement: a synced file that is missing fails the check. The log names
  # the file and the command that repairs it.
  config-missing-file-fails = {
    check = configCheck (tree "missing-file" "rm lychee.toml");
    expectedLog = [
      "lychee.toml: No such file or directory"
      repairHint
    ];
  };
}
// differingCases
