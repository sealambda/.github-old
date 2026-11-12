# The tests of the functions that the hub exports as `lib`. `flake.nix` calls
# this file for the flake check `lib-functions`. Each case file in this folder
# holds the cases of one function, and `harness.nix` holds what the cases
# share. `docs/how-to/test-a-hub-function.md` says how to add a case.
#
# The check builds every case, so one failed case fails the check. The failed
# derivation is named `lib-<case>`, which names the fixture.
{
  pkgs,
  hub,
  syncConfig,
  syncedPaths,
}:
let
  harness = import ./harness.nix { inherit pkgs syncConfig syncedPaths; };

  # The case files. Each one is a function from the arguments below to an
  # attribute set of cases, named `<function>-<situation>`.
  caseFiles = [
    ./config.nix
    ./decisions.nix
    ./docs.nix
    ./treefmt.nix
  ];

  cases = pkgs.lib.mergeAttrsList (map (file: import file { inherit pkgs hub harness; }) caseFiles);
in
pkgs.linkFarm "lib-functions" (harness.toTests cases)
