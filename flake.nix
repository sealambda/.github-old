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

      # The hub's own package set for the system of the caller's `pkgs`. A check
      # that builds its tools from this set, and not from the caller's `pkgs`,
      # runs the same tool versions in every consumer, whatever nixpkgs the
      # consumer follows. `mkDocsCheck` uses it. Only the system is taken from
      # `pkgs`, so the call of a consumer keeps working.
      hubPackagesFor = pkgs: nixpkgs.legacyPackages.${pkgs.stdenv.hostPlatform.system};

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

      # The Sealambda Vale style as a package with the layout of the styles in
      # nixpkgs: `share/vale/styles/Sealambda`. `vale.withStyles` links it next
      # to the styles of nixpkgs. The source is `vale/Sealambda`, because
      # `.gitignore` hides the style directories under `.vale/styles`.
      mkValeStyleSealambda =
        pkgs:
        pkgs.runCommand "vale-style-sealambda" { } ''
          install -D -m 644 -t "$out/share/vale/styles/Sealambda" ${./vale/Sealambda}/*.yml
        '';

      /**
        Builds the documentation tools from one package set: the three tools of
        the `docs` dev shell and of `mkDocsCheck`. The Vale of these tools has
        the style Google from nixpkgs and the hub's own style Sealambda.

        # Inputs

        `pkgs`
        : The package set of one system. The hub's `docs` shell and
          `mkDocsCheck` pass the hub's own package set.

        # Type

        ```
        mkDocsTools :: AttrSet -> [Derivation]
        ```
      */
      mkDocsTools =
        pkgs:
        let
          # Vale and the styles that `BasedOnStyles` in `config/vale.ini` names:
          # keep both lists the same. A difference fails loudly, because Vale
          # reports "Style isn't on StylesPath". The styles of nixpkgs are
          # pinned by `flake.lock`, the style Sealambda is in this repository,
          # and no run downloads a style. `withStyles` sets `VALE_STYLES_PATH` to
          # its `share/vale/styles`, and Vale finds the styles there. The
          # project `StylesPath` holds only the vocabularies. Vale ignores that
          # variable when it runs with `--no-global`.
          valeWithStyles = pkgs.vale.withStyles (styles: [
            styles.google
            (mkValeStyleSealambda pkgs)
          ]);
        in
        [
          pkgs.lychee
          pkgs.markdownlint-cli2
          valeWithStyles
        ];

      docsToolsFor = eachSystem mkDocsTools;

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
        message names the `sync-config` command that repairs it: the pinned hub
        app of a calling repository, and the local app of the hub itself.

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
            echo "A tool configuration differs from the hub." >&2
            echo "Run: nix run --inputs-from . hub#sync-config" >&2
            echo "In the hub repository itself, run: nix run .#sync-config" >&2
          fi
          touch "$out"
          exit "$status"
        '';

      /**
        Builds a check that lints the Markdown files of a source tree with
        markdownlint-cli2, lychee and Vale, and fails when a tool reports a
        problem. The tools come from the hub's own nixpkgs, whatever nixpkgs the
        calling flake uses: the function takes only the system from `pkgs`.
        Every consumer then runs one version of each tool and of each Vale
        style, so the same page gets the same result in every repository, and a
        consumer needs no `nixpkgs.follows = "hub/nixpkgs"` for this check. A
        bump of the hub in `flake.lock` updates the tools. Where the Nix sandbox
        is enabled, which it always is on Linux CI, the check reads each tool's
        configuration from `src` and no personal configuration of the user, and
        it needs no network: lychee runs offline, the Vale styles are in the Nix
        store, and the trust store that lychee loads at startup comes from Nix
        too. The same command runs locally and in CI: `nix flake check`, or
        `nix build .#checks.<system>.docs -L`. A local re-run on an unchanged
        `src` reuses the result by the hash of `src`.

        Pass the whole `self` of the calling flake, not a set of Markdown
        files, because lychee also checks links to files that are not
        Markdown. The calling repository needs the files that `sync-config`
        writes, and the `Repository` Vale vocabulary.

        # Inputs

        `pkgs`
        : The package set of one system. Only its system is used.

        `src`
        : The source tree to check, normally the `self` of the calling flake.

        # Type

        ```
        mkDocsCheck :: AttrSet -> (Path | AttrSet) -> Derivation
        ```
      */
      mkDocsCheck =
        pkgs: src:
        let
          hubPkgs = hubPackagesFor pkgs;
        in
        hubPkgs.runCommand "docs"
          {
            nativeBuildInputs = mkDocsTools hubPkgs;
            # The trust store that lychee needs at startup.
            SSL_CERT_FILE = "${hubPkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
          }
          ''
            export HOME="$TMPDIR"
            cd ${src}
            markdownlint-cli2 "**/*.md"
            lychee --no-progress "**/*.md"
            vale --minAlertLevel=error .
            touch "$out"
          '';
    in
    {
      lib = {
        inherit
          mkTreefmt
          mkConfigCheck
          mkDocsCheck
          ;
      };

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
          packages = docsToolsFor.${pkgs.stdenv.hostPlatform.system};
        };
      });

      formatter = eachSystem (pkgs: treefmtFor.${pkgs.stdenv.hostPlatform.system}.config.build.wrapper);

      checks = eachSystem (pkgs: {
        config-in-sync = mkConfigCheck pkgs self;
        docs = mkDocsCheck pkgs self;
        formatting = treefmtFor.${pkgs.stdenv.hostPlatform.system}.config.build.check self;
      });
    };
}
