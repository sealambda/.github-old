{
  description = "Sealambda engineering standards: development shells, formatter and tool configuration";

  inputs = {
    # One nixpkgs revision for the whole organization. A consumer sets
    # `inputs.nixpkgs.follows = "hub/nixpkgs"` and so evaluates the same one.
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      treefmt-nix,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];

      # Applies `f` to the package set of each supported system.
      eachSystem = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});

      /**
        Evaluates the organization's treefmt module and returns the treefmt-nix
        evaluation. Use `.config.build.wrapper` as `formatter` and
        `.config.build.check self` as `checks.formatting`.

        # Inputs

        `pkgs`
        : The package set of one system.

        `extraModules`
        : A list of treefmt-nix modules that the calling repository adds, for
          example its own formatters and excludes.

        # Type

        ```
        mkTreefmt :: AttrSet -> [Module] -> AttrSet
        ```
      */
      mkTreefmt =
        pkgs: extraModules:
        treefmt-nix.lib.evalModule pkgs {
          imports = [ ./treefmt.nix ] ++ extraModules;
        };

      treefmtFor = eachSystem (pkgs: mkTreefmt pkgs [ ]);

      # The Vale tool of the `docs` dev shell.
      docsToolsFor = eachSystem (pkgs: {
        # Vale and the styles that `BasedOnStyles` in `config/vale.ini` names:
        # keep both lists the same. A difference fails loudly, because Vale
        # reports "Style isn't on StylesPath". The styles come from nixpkgs, so
        # `flake.lock` pins them and no run downloads them. `withStyles` sets
        # `VALE_STYLES_PATH` to its `share/vale/styles`, and Vale finds the
        # styles there. The project `StylesPath` holds only the vocabularies.
        # Vale ignores that variable when it runs with `--no-global`.
        valeWithStyles = pkgs.vale.withStyles (styles: [
          styles.microsoft
          styles.readability
        ]);
      });

      # Tool configuration that a tool reads only from a file in the
      # repository. Each name is the path in the consumer; each value is the
      # hub's copy. `sync-config` writes the copies and `mkConfigCheck`
      # compares them.
      configFiles = {
        ".editorconfig" = ./config/editorconfig;
        ".markdownlint-cli2.yaml" = ./config/markdownlint-cli2.yaml;
        ".vale.ini" = ./config/vale.ini;
        ".vale/styles/config/vocabularies/Sealambda/accept.txt" = ./config/vale-vocabulary.txt;
        "lychee.toml" = ./config/lychee.toml;
      };

      # Writes the copies into the current directory. `-m 644` makes each copy
      # writable, because the source is read-only in the Nix store. `-D` creates
      # the parent directories.
      mkSyncConfig =
        pkgs:
        pkgs.writeShellApplication {
          name = "sync-config";
          runtimeInputs = [ pkgs.coreutils ];
          text = nixpkgs.lib.concatStringsSep "\n" (
            nixpkgs.lib.mapAttrsToList (
              path: source: "install -D -m 644 ${source} ${nixpkgs.lib.escapeShellArg path}"
            ) configFiles
          );
        };

      /**
        Builds a check that fails when a synced tool configuration file of a
        repository differs from the hub's file or is missing. The failure
        message names the `sync-config` command that repairs it.

        # Inputs

        `pkgs`
        : The package set of one system.

        `src`
        : The source tree to compare, normally the `self` of the calling flake.

        # Type

        ```
        mkConfigCheck :: AttrSet -> (Path | AttrSet) -> Derivation
        ```
      */
      mkConfigCheck =
        pkgs: src:
        pkgs.runCommand "config-in-sync" { nativeBuildInputs = [ pkgs.diffutils ]; } ''
          status=0
          ${nixpkgs.lib.concatStringsSep "\n" (
            nixpkgs.lib.mapAttrsToList (
              path: source: "diff -u ${source} ${src}/${path} || status=1"
            ) configFiles
          )}
          if [ "$status" -ne 0 ]; then
            echo "A tool configuration differs from the hub. Run: nix run github:sealambda/.github#sync-config" >&2
          fi
          touch "$out"
          exit "$status"
        '';
    in
    {
      lib = { inherit mkTreefmt mkConfigCheck; };

      apps = eachSystem (pkgs: {
        sync-config = {
          type = "app";
          program = nixpkgs.lib.getExe (mkSyncConfig pkgs);
        };
      });

      # Version policy: a toolchain version is the name of a nixpkgs attribute
      # below. To move to a new major version, change the attribute name.
      devShells = eachSystem (pkgs: rec {
        # Included in every other shell: git and the workflow and secret linters.
        base = pkgs.mkShell {
          packages = with pkgs; [
            actionlint
            git
            gitleaks
            zizmor
          ];
        };
        default = base;

        elixir = pkgs.mkShell {
          inputsFrom = [ base ];
          packages = [
            pkgs.beam.packages.erlang_29.erlang
            pkgs.beam.packages.erlang_29.elixir_1_20
          ];
        };

        # `nodejs-slim` has no npm or npx: the organization uses pnpm only.
        node = pkgs.mkShell {
          inputsFrom = [ base ];
          packages = [
            pkgs.nodejs-slim_26
            pkgs.pnpm_12
          ];
        };

        tofu = pkgs.mkShell {
          inputsFrom = [ base ];
          packages = [ pkgs.opentofu ];
        };

        docs = pkgs.mkShell {
          inputsFrom = [ base ];
          packages = [
            pkgs.lychee
            pkgs.markdownlint-cli2
            docsToolsFor.${pkgs.stdenv.hostPlatform.system}.valeWithStyles
          ];
        };
      });

      formatter = eachSystem (pkgs: treefmtFor.${pkgs.stdenv.hostPlatform.system}.config.build.wrapper);

      checks = eachSystem (pkgs: {
        config-in-sync = mkConfigCheck pkgs self;
        formatting = treefmtFor.${pkgs.stdenv.hostPlatform.system}.config.build.check self;
      });
    };
}
