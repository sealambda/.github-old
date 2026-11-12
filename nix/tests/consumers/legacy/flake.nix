{
  description = "A synthetic consumer of the hub: it adopts the hub as the adoption page documents";

  # The hub tests itself against this flake: CI overrides the input `hub` with
  # the checked-out hub, and every check below must build. The file uses only
  # what the page "Adopt the hub in a repository" documents. Copy the folder to
  # try the hub in a scratch repository: the input URL then names the hub on
  # GitHub, and `nix flake lock` pins it.
  inputs = {
    hub.url = "github:sealambda/.github";
    nixpkgs.follows = "hub/nixpkgs";
  };

  outputs =
    {
      self,
      nixpkgs,
      hub,
      ...
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
      treefmtFor = forAllSystems (pkgs: hub.lib.mkTreefmt pkgs [ ]);
    in
    {
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          inputsFrom = [ hub.devShells.${pkgs.stdenv.hostPlatform.system}.node ];
        };
      });
      formatter = forAllSystems (
        pkgs: treefmtFor.${pkgs.stdenv.hostPlatform.system}.config.build.wrapper
      );
      checks = forAllSystems (pkgs: {
        formatting = treefmtFor.${pkgs.stdenv.hostPlatform.system}.config.build.check self;
        config-in-sync = hub.lib.mkConfigCheck pkgs self;
        docs = hub.lib.mkDocsCheck pkgs self;
        # `repository` only has to be a valid `owner/name`. It names the hub
        # repository, which the leak list of the hub always holds, so a change
        # of that list does not touch this file.
        decisions = hub.lib.mkDecisionsCheck pkgs self {
          repository = "sealambda/.github";
          exclude = [ ];
        };
        workflows = hub.lib.mkWorkflowsCheck pkgs self;
      });
    };
}
