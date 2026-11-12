{
  description = "A synthetic consumer of the hub that takes all the standards with one call of lib.mkStandards";

  # The hub tests itself against this flake: CI overrides the input `hub` with
  # the checked-out hub, and every check below must build. The consumer calls
  # only `hub.lib.mkStandards`, with the three required arguments, and holds no
  # tool configuration of its own. The checks that start with `variant-` call
  # it again, one for each optional argument, on a copy of this folder with one
  # more file. Copy the folder to try the hub in a scratch repository: the
  # input URL then names the hub on GitHub, and `nix flake lock` pins it.
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
      inherit (nixpkgs) lib;
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];
      forAllSystems = f: lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});

      # The name of this repository on GitHub, without the owner.
      name = "quints";

      # The standards with the required arguments alone.
      standardsFor = forAllSystems (
        pkgs:
        hub.lib.mkStandards {
          inherit pkgs name;
          src = self;
        }
      );

      # A copy of this folder with the files of `files` added, for a variant
      # that needs a file which the checks of the hub itself would reject in a
      # tracked folder. `files` maps each path to its text.
      withFiles =
        pkgs: label: files:
        pkgs.runCommand "standards-consumer-${label}" { } ''
          cp -R --no-preserve=mode ${self} "$out"
          ${lib.concatStrings (
            lib.mapAttrsToList (
              path: text:
              "install -D -m 644 ${pkgs.writeText "variant-file" text} \"$out\"/${lib.escapeShellArg path}\n"
            ) files
          )}
        '';

      # The text of a Nix file that the formatter changes, and of a page that
      # cites a decision record that doesn't exist.
      unformatted = "{a=1;}\n";
      missingNumber = "0042";
      citingPage = "# Fixture\n\nSee ADR ${missingNumber}.\n";

      # A check that must fail: `drv` is built, and the check passes only when
      # the build fails with exit status 1 and its log holds each entry of
      # `expectedLog`. It shows that a variant passes because of its argument.
      mustFail =
        pkgs: label: drv: expectedLog:
        pkgs.testers.testBuildFailure' {
          name = "variant-${label}";
          drv = drv.overrideAttrs { name = "variant-${label}-subject"; };
          expectedBuilderExitCode = 1;
          expectedBuilderLogEntries = expectedLog;
        };

      # One check for each optional argument of `mkStandards`.
      variantsFor =
        pkgs:
        let
          # `treefmtModules`: a module that keeps `example.nix` out of the formatter.
          excludeExample = {
            settings.global.excludes = [ "example.nix" ];
          };
          formatterSrc = withFiles pkgs "formatter" { "example.nix" = unformatted; };
          withModule = hub.lib.mkStandards {
            inherit pkgs name;
            src = formatterSrc;
            treefmtModules = [ excludeExample ];
          };
          withoutModule = hub.lib.mkStandards {
            inherit pkgs name;
            src = formatterSrc;
          };

          # `decisions`: the folder `fixtures` is out of the citation scan.
          citationSrc = withFiles pkgs "citation" { "fixtures/cites.md" = citingPage; };
          withExclude = hub.lib.mkStandards {
            inherit pkgs name;
            src = citationSrc;
            decisions.exclude = [ "fixtures" ];
          };
          withoutExclude = hub.lib.mkStandards {
            inherit pkgs name;
            src = citationSrc;
          };

          # `hooks`: a hook of the repository runs in the check `pre-commit`.
          withHook = hub.lib.mkStandards {
            inherit pkgs name;
            src = self;
            hooks.my-hook = {
              enable = true;
              entry = "${pkgs.coreutils}/bin/false";
            };
          };

          # `scanner`: the command `secrets-scan` runs the scanner that the
          # repository gives. The wrapper script holds the store path of its
          # scanner, so the check reads which scanner it runs.
          withScanner = hub.lib.mkStandards {
            inherit pkgs name;
            src = self;
            scanner = pkgs.betterleaks;
          };
        in
        {
          variant-treefmt-modules = withModule.checks.formatting;
          variant-treefmt-modules-needed =
            mustFail pkgs "treefmt-modules-needed" withoutModule.checks.formatting
              [
                "example.nix"
              ];
          variant-decisions-exclude = withExclude.checks.decisions;
          variant-decisions-exclude-needed =
            mustFail pkgs "decisions-exclude-needed" withoutExclude.checks.decisions
              [ "fixtures/cites.md:3: decision record ${missingNumber} does not exist" ];
          variant-hooks = mustFail pkgs "hooks" withHook.checks.pre-commit [ "my-hook" ];
          variant-scanner = pkgs.runCommand "variant-scanner" { } ''
            grep -q ${pkgs.betterleaks} ${lib.getExe withScanner.packages.secrets-scan}
            touch "$out"
          '';
        };
    in
    {
      # The shell `default` puts the commands of the hub on `PATH`. The shell
      # `hooks` opts in to the Git hooks with the line `shellHook`: without it,
      # the repository gets the check `pre-commit` and no installed hook.
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          packages = lib.attrValues standardsFor.${pkgs.stdenv.hostPlatform.system}.packages;
        };
        hooks = pkgs.mkShell {
          inherit (standardsFor.${pkgs.stdenv.hostPlatform.system}.hooks) shellHook;
        };
      });
      formatter = forAllSystems (pkgs: standardsFor.${pkgs.stdenv.hostPlatform.system}.formatter);
      packages = forAllSystems (pkgs: standardsFor.${pkgs.stdenv.hostPlatform.system}.packages);
      checks = forAllSystems (
        pkgs: standardsFor.${pkgs.stdenv.hostPlatform.system}.checks // variantsFor pkgs
      );
    };
}
