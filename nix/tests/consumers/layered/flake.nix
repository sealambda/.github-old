{
  description = "A synthetic consumer of the hub that layers its own documentation configuration over the hub's base";

  # The hub tests itself against this flake: CI overrides the input `hub` with
  # the checked-out hub, and every check below must build. The consumer holds
  # no copy of the hub's tool configuration, so it has no `config-in-sync`
  # check. The documentation tools take the hub's rules from the Nix store, and
  # the files of this folder add to them. Copy the folder to try the hub in a
  # scratch repository: the input URL then names the hub on GitHub, and
  # `nix flake lock` pins it.
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
        docs = hub.lib.mkDocsCheck pkgs self;
        # The check `docs` alone passes without the hub's base: each tool then
        # lints less and finds nothing to report. This check builds the files
        # of this folder plus one page that breaks a rule of each tool, and it
        # passes only when the docs check fails on all three findings. Each
        # rule is a setting of the hub's base:
        # - Vale: the style `Sealambda`, which only the base lists.
        # - markdownlint-cli2: `noInlineConfig`. The comment tries to switch
        #   MD025 off, and the base ignores the comment.
        # - lychee: `include_fragments`. The link names a heading that
        #   doesn't exist.
        docs-hub-base = pkgs.testers.testBuildFailure' {
          name = "docs-hub-base";
          drv =
            (hub.lib.mkDocsCheck pkgs (
              pkgs.runCommand "layered-base-violations" { } ''
                cp -R --no-preserve=mode ${self} "$out"
                cat >"$out/violations.md" <<'EOF'
                # Violations

                The server currently runs NixOS.

                <!-- markdownlint-disable MD025 -->

                # Second title

                Read [the heading](guide.md#missing-heading).
                EOF
              ''
            )).overrideAttrs
              { name = "docs-hub-base-subject"; };
          expectedBuilderExitCode = 1;
          expectedBuilderLogEntries = [
            "Sealambda.CurrentState"
            "MD025"
            "guide.md#missing-heading"
          ];
        };
        decisions = hub.lib.mkDecisionsCheck pkgs self {
          repository = "sealambda/quints";
          exclude = [ ];
        };
        workflows = hub.lib.mkWorkflowsCheck pkgs self;
      });
    };
}
