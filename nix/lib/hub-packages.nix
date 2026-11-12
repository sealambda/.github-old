# The hub's own package set. `flake.nix` imports this file and passes
# `hubPackagesFor` to `docs.nix` and `decisions.nix`: their checks build their
# tools from this set and not from the package set of the calling flake.
{ nixpkgs }:
{
  # The hub's own package set for the system of the caller's `pkgs`. A check
  # that builds its tools from this set, and not from the caller's `pkgs`,
  # runs the same tool versions in every consumer, whatever nixpkgs the
  # consumer follows. `mkDocsCheck` and `mkDecisionsCheck` use it. Only the
  # system is taken from `pkgs`, so the call of a consumer keeps working.
  hubPackagesFor = pkgs: nixpkgs.legacyPackages.${pkgs.stdenv.hostPlatform.system};
}
