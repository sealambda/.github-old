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
      # consumer follows. `mkDocsCheck` and `mkDecisionsCheck` use it. Only the
      # system is taken from `pkgs`, so the call of a consumer keeps working.
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

      # The rule files of the Sealambda Vale style, without their test cases.
      # A change to a test case then doesn't rebuild the style.
      valeStyleRules = nixpkgs.lib.fileset.toSource {
        root = ./vale/Sealambda;
        fileset = nixpkgs.lib.fileset.fileFilter (
          file: file.hasExt "yml" && !(nixpkgs.lib.hasSuffix ".test.yml" file.name)
        ) ./vale/Sealambda;
      };

      # The Sealambda Vale style as a package with the layout of the styles in
      # nixpkgs: `share/vale/styles/Sealambda`. `vale.withStyles` links it next
      # to the styles of nixpkgs. The source is `vale/Sealambda`, because
      # `.gitignore` hides the style directories under `.vale/styles`.
      mkValeStyleSealambda =
        pkgs:
        pkgs.runCommand "vale-style-sealambda" { } ''
          install -D -m 644 -t "$out/share/vale/styles/Sealambda" ${valeStyleRules}/*.yml
        '';

      /**
        Builds the documentation tools from one package set: the three tools of
        the `docs` dev shell and of `mkDocsCheck`, and the `check-docs` command
        that runs them. The Vale of these tools has the styles Microsoft and
        Readability from nixpkgs and the hub's own style Sealambda.

        # Inputs

        `pkgs`
        : The package set of one system. The hub's `docs` shell and
          `mkDocsCheck` pass the hub's own package set.

        # Type

        ```
        mkDocsTools :: AttrSet -> { valeWithStyles :: Derivation; checkDocs :: Derivation; tools :: [Derivation]; }
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
            styles.microsoft
            styles.readability
            (mkValeStyleSealambda pkgs)
          ]);

          # The three documentation tools, listed once for `checkDocs` and for
          # the `docs` dev shell.
          tools = [
            pkgs.lychee
            pkgs.markdownlint-cli2
            valeWithStyles
          ];

          # The `check-docs` command: the three tools with the flags in
          # `nix/scripts/check-docs.sh`. `writeShellApplication` lints the script
          # with shellcheck, and its header describes the script.
          checkDocs = pkgs.writeShellApplication {
            name = "check-docs";
            runtimeInputs = tools;
            # The trust store that lychee needs at startup. The reason is in the
            # header of `nix/scripts/check-docs.sh`.
            runtimeEnv.SSL_CERT_FILE = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
            text = builtins.readFile ./nix/scripts/check-docs.sh;
          };
        in
        {
          inherit valeWithStyles checkDocs tools;
        };

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
        calling flake uses: the function takes only the system from `pkgs`, the
        same as `mkDecisionsCheck`. Every consumer then runs one version of each
        tool and of each Vale style, so the same page gets the same result in
        every repository, and a consumer needs no `nixpkgs.follows =
        "hub/nixpkgs"` for this check. A bump of the hub in `flake.lock` updates
        the tools. Where the Nix sandbox is enabled, which it always is on Linux
        CI, the check reads each tool's configuration from `src` and no personal
        configuration of the user, and it needs no network: lychee runs offline,
        the Vale styles are in the Nix store, and the trust store that lychee
        loads at startup comes from Nix too. The same command runs locally and
        in CI: `nix flake check`, or `nix build .#checks.<system>.docs -L`. A
        local re-run on an unchanged `src` reuses the result by the hash of
        `src`.

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
        hubPkgs.runCommand "docs" { } ''
          HOME="$TMPDIR" ${nixpkgs.lib.getExe (mkDocsTools hubPkgs).checkDocs} ${src}
          touch "$out"
        '';

      # The Python package `decisions` without the rest of `nix/scripts`, so a
      # change to `check-docs.sh` does not rebuild the decisions tool.
      decisionsSource = nixpkgs.lib.fileset.toSource {
        root = ./nix/scripts;
        fileset = ./nix/scripts/decisions;
      };

      # What `python-quality` reads: the package, its tests and the ruff and mypy
      # settings. A change to any other file of the hub does not rerun the check.
      pythonQualitySource = nixpkgs.lib.fileset.toSource {
        root = ./.;
        fileset = nixpkgs.lib.fileset.unions [
          ./nix/scripts/decisions
          ./nix/scripts/leaks
          ./nix/scripts/release
          ./nix/scripts/versions
          ./nix/tests/decisions
          ./nix/tests/leaks
          ./nix/tests/release
          ./nix/tests/versions
          ./pyproject.toml
        ];
      };

      # The Python package `release`. It uses only the standard library.
      releaseSource = nixpkgs.lib.fileset.toSource {
        root = ./nix/scripts;
        fileset = ./nix/scripts/release;
      };

      # What `release` finds at run time: itself. Python cannot write byte code
      # into the Nix store.
      releaseEnv = {
        PYTHONPATH = "${releaseSource}";
        PYTHONDONTWRITEBYTECODE = "1";
      };

      # The `release` command: `python -m release`, the code in
      # `nix/scripts/release`. It plans and creates the release of a commit of
      # the hub. `git` answers the questions about the history, and `gh`
      # creates the release.
      mkReleaseTool =
        pkgs:
        pkgs.writeShellApplication {
          name = "release";
          runtimeInputs = [
            pkgs.python3
            pkgs.git
            pkgs.gh
          ];
          runtimeEnv = releaseEnv;
          text = ''exec python -m release "$@"'';
        };

      # The Python package `leaks`, and the package `decisions`. `leaks`
      # imports only `decisions.walk` and `decisions.findings`, which use only
      # the standard library: this environment has no `pyyaml` or
      # `jsonschema`, which the other modules of `decisions` need.
      leaksSource = nixpkgs.lib.fileset.toSource {
        root = ./nix/scripts;
        fileset = nixpkgs.lib.fileset.unions [
          ./nix/scripts/decisions
          ./nix/scripts/leaks
        ];
      };

      # What `leaks` finds at run time: itself. Python cannot write byte code
      # into the Nix store.
      leaksEnv = {
        PYTHONPATH = "${leaksSource}";
        PYTHONDONTWRITEBYTECODE = "1";
      };

      # The `leaks` command: `python -m leaks`, the code in `nix/scripts/leaks`.
      # It reports the private facts of an organization in a source tree.
      mkLeaksTool =
        pkgs:
        pkgs.writeShellApplication {
          name = "leaks";
          runtimeInputs = [ pkgs.python3 ];
          runtimeEnv = leaksEnv;
          text = ''exec python -m leaks "$@"'';
        };

      # What the hub, a public repository, may name: the organization's public
      # repositories and the team of `.github/CODEOWNERS`. Every other
      # repository or team name fails the `leaks` check. The list holds public
      # names only, so the hub never holds the list of the private ones.
      publicNames = {
        organization = "sealambda";
        repositories = [
          ".github"
          "chironium"
          "quints"
        ];
        teams = [ "maintainers" ];
      };

      # What the package finds at run time: itself, and the JSON Schemas. Python
      # cannot write byte code into the Nix store.
      decisionsEnv = {
        PYTHONPATH = "${decisionsSource}";
        DECISIONS_SCHEMA_DIR = "${./schemas}";
        PYTHONDONTWRITEBYTECODE = "1";
      };

      # The Python with the two libraries that `decisions` imports. The quality
      # check adds mypy and the type stubs of both libraries.
      decisionsPython =
        pkgs:
        pkgs.python3.withPackages (ps: [
          ps.pyyaml
          ps.jsonschema
        ]);

      # The Python package `versions`, and the package `decisions` whose
      # findings, schema loading and file listing it imports.
      versionsSource = nixpkgs.lib.fileset.toSource {
        root = ./nix/scripts;
        fileset = nixpkgs.lib.fileset.unions [
          ./nix/scripts/decisions
          ./nix/scripts/versions
        ];
      };

      # What `versions` finds at run time: itself, and the JSON Schemas, which
      # `decisions.schemas` reads from `DECISIONS_SCHEMA_DIR`. Python cannot
      # write byte code into the Nix store.
      versionsEnv = {
        PYTHONPATH = "${versionsSource}";
        DECISIONS_SCHEMA_DIR = "${./schemas}";
        PYTHONDONTWRITEBYTECODE = "1";
      };

      # The `versions` command: `python -m versions`, the code in
      # `nix/scripts/versions`. It needs the two libraries of `decisions`.
      mkVersionsTool =
        pkgs:
        pkgs.writeShellApplication {
          name = "versions";
          runtimeInputs = [ (decisionsPython pkgs) ];
          runtimeEnv = versionsEnv;
          text = ''exec python -m versions "$@"'';
        };

      # The `decisions` command: `python -m decisions`, the code in
      # `nix/scripts/decisions`, with the schemas in `schemas`. `git` lists the
      # files of a work tree, so the check skips the ignored ones, and it is
      # for the `retire` subcommand.
      mkDecisionsTool =
        pkgs:
        pkgs.writeShellApplication {
          name = "decisions";
          runtimeInputs = [
            (decisionsPython pkgs)
            pkgs.git
          ];
          runtimeEnv = decisionsEnv;
          text = ''exec python -m decisions "$@"'';
        };

      /**
        Builds a check that fails when the decision records, the specs or the
        citations of a source tree are wrong. It reads the records in
        `docs/decisions/` and the ledger `docs/decisions/superseded.yaml`, and it
        reads every text file for citations of records, specs and `docs/` pages.
        Each finding prints as `path:line: message`, and one run prints all of
        them. The checks and the citation forms are in
        `docs/reference/decision-records.md`. The check needs no network. The
        same command runs locally and in CI: `nix flake check`, or
        `nix build .#checks.<system>.decisions -L`.

        The tool comes from the hub's own nixpkgs, whatever nixpkgs the calling
        flake uses: the function takes only the system from `pkgs`. Every
        consumer then gets one version of the tool and of its Python libraries.
        `mkDocsCheck` does the same.

        Pass the whole `self` of the calling flake.

        # Inputs

        `pkgs`
        : The package set of one system. Only its system is used.

        `src`
        : The source tree to check, normally the `self` of the calling flake.

        `repository`
        : The `owner/name` of the repository that holds `src`, for example
          `sealambda/.github`. A citation that another repository qualifies, as
          in `sealambda/<repo> ADR NNNN`, is about that repository, and the
          check skips it.

        `exclude`
        : A list of paths relative to the root of `src`, default empty. The
          citation scan skips each path and the files below it. A path matches
          whole components, so `a/b` skips `a/b/c.py` and not `a/bc.py`. Use it
          for files that hold citations on purpose, such as test fixtures.

        # Type

        ```
        mkDecisionsCheck :: AttrSet -> (Path | AttrSet) -> { repository :: String; exclude :: [String]; } -> Derivation
        ```
      */
      mkDecisionsCheck =
        pkgs: src:
        {
          repository,
          exclude ? [ ],
        }:
        let
          hubPkgs = hubPackagesFor pkgs;
          excludeFlags = nixpkgs.lib.concatMapStringsSep " " (
            path: "--exclude ${nixpkgs.lib.escapeShellArg path}"
          ) exclude;
        in
        hubPkgs.runCommand "decisions" { } ''
          ${nixpkgs.lib.getExe (mkDecisionsTool hubPkgs)} check \
            --repository ${nixpkgs.lib.escapeShellArg repository} \
            ${excludeFlags} ${src}
          touch "$out"
        '';
    in
    {
      lib = {
        inherit
          mkTreefmt
          mkConfigCheck
          mkDocsCheck
          mkDecisionsCheck
          ;
      };

      apps = eachSystem (pkgs: {
        sync-config = {
          type = "app";
          program = nixpkgs.lib.getExe (mkSyncConfig pkgs);
        };

        # `decisions check` and `decisions retire` in the current repository.
        # The tool comes from the hub's nixpkgs, like `mkDecisionsCheck`.
        decisions = {
          type = "app";
          program = nixpkgs.lib.getExe (mkDecisionsTool pkgs);
        };

        # `release plan` and `release publish` in the current repository. The
        # tools come from the hub's nixpkgs. The CI runs `publish` for each
        # merge to `main`.
        release = {
          type = "app";
          program = nixpkgs.lib.getExe (mkReleaseTool pkgs);
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
          packages = docsToolsFor.${pkgs.stdenv.hostPlatform.system}.tools;
        };
      });

      formatter = eachSystem (pkgs: treefmtFor.${pkgs.stdenv.hostPlatform.system}.config.build.wrapper);

      checks = eachSystem (pkgs: {
        config-in-sync = mkConfigCheck pkgs self;
        docs = mkDocsCheck pkgs self;
        formatting = treefmtFor.${pkgs.stdenv.hostPlatform.system}.config.build.check self;

        # Runs the tests of `nix/scripts/check-docs.sh`. The tests need a
        # writable HOME and the commands `check-docs`, `sync-config` and `vale`
        # on PATH. `vale` is the Vale with the hub's styles.
        check-docs-tests =
          pkgs.runCommand "check-docs-tests"
            {
              nativeBuildInputs = [
                docsToolsFor.${pkgs.stdenv.hostPlatform.system}.checkDocs
                docsToolsFor.${pkgs.stdenv.hostPlatform.system}.valeWithStyles
                (mkSyncConfig pkgs)
              ];
            }
            ''
              HOME="$TMPDIR" bash ${./nix/tests/check-docs.sh}
              touch "$out"
            '';

        # Runs the test cases of the Sealambda Vale style,
        # `vale/Sealambda/*.test.yml`. `--coverage` makes a rule without a test
        # case fail. The cases hold the words of the rules in a YAML file, so the
        # hub's own `docs` check never lints them.
        vale-style-tests =
          pkgs.runCommand "vale-style-tests"
            {
              nativeBuildInputs = [ pkgs.vale ];
            }
            ''
              HOME="$TMPDIR" vale test --coverage --no-wrap ${./vale/Sealambda}
              touch "$out"
            '';

        # The hub checks its own records and citations. The fixtures of the
        # decisions tests cite records on purpose, and `check-docs.sh` names a
        # page that its test creates at run time.
        decisions = mkDecisionsCheck pkgs self {
          repository = "sealambda/.github";
          exclude = [
            "nix/tests/decisions"
            "nix/tests/check-docs.sh"
          ];
        };

        # Runs the unit tests of `nix/scripts/decisions`. Some tests make a Git
        # work tree, so they need `git` and a writable HOME.
        check-decisions-tests =
          pkgs.runCommand "check-decisions-tests"
            {
              nativeBuildInputs = [
                (decisionsPython pkgs)
                pkgs.git
              ];
              env = decisionsEnv;
            }
            ''
              export HOME="$TMPDIR"
              python -m unittest discover -v -s ${./nix/tests/decisions}
              touch "$out"
            '';

        # Fails when a file of the hub holds a private fact of the
        # organization: an AWS account identifier or resource, a bucket, a
        # label of a self-hosted runner, an internal host, a GitHub App
        # identifier, or the name of a repository or team that `publicNames`
        # does not list. The rules are in `nix/scripts/leaks/rules.py` and the
        # reference is `docs/reference/leak-check.md`. The `--exclude` flags
        # below are the only list of the paths that are not scanned, and the
        # reference points here for it: the rules, whose patterns hold the
        # prefixes that they search for, and the two test files, whose
        # fixtures are leaks on purpose with false identifiers. A new file
        # in the test folder is scanned.
        leaks =
          pkgs.runCommand "leaks"
            {
              nativeBuildInputs = [ (mkLeaksTool pkgs) ];
            }
            ''
              leaks \
                --organization ${nixpkgs.lib.escapeShellArg publicNames.organization} \
                ${
                  nixpkgs.lib.concatMapStringsSep " " (
                    name: "--public-repository ${nixpkgs.lib.escapeShellArg name}"
                  ) publicNames.repositories
                } \
                ${
                  nixpkgs.lib.concatMapStringsSep " " (
                    name: "--public-team ${nixpkgs.lib.escapeShellArg name}"
                  ) publicNames.teams
                } \
                --exclude nix/scripts/leaks/rules.py \
                --exclude nix/tests/leaks/test_leak_rules.py \
                --exclude nix/tests/leaks/test_leak_scan.py \
                ${self}
              touch "$out"
            '';

        # Runs the unit tests of `nix/scripts/leaks`: each rule with texts that
        # it finds and texts that it leaves alone, and the scan of a tree.
        check-leaks-tests =
          pkgs.runCommand "check-leaks-tests"
            {
              nativeBuildInputs = [ pkgs.python3 ];
              env = leaksEnv;
            }
            ''
              export HOME="$TMPDIR"
              python -m unittest discover -v -s ${./nix/tests/leaks}
              touch "$out"
            '';

        # Fails when a file of the hub has no copyright and license, when a
        # license that `REUSE.toml` names has no text in `LICENSES/`, or when
        # `LICENSES/` holds a text that nothing uses: `reuse lint` checks the
        # tree against the REUSE specification. It also fails when the root
        # `LICENSE`, which GitHub reads, differs from `LICENSES/MPL-2.0.txt`
        # apart from the space at the end of a line, which an editor may trim
        # (`.editorconfig`), or when a file takes a notice or an expression from its own text and
        # not from `REUSE.toml`: the tool reads any `Copyright` followed by a
        # space as a notice, and then it drops the data of `REUSE.toml`. The
        # check needs no network and no Git history: the tool reads the
        # source tree in the Nix store. It cannot tell that a new file is
        # third-party content (`docs/reference/licensing.md`).
        licenses =
          pkgs.runCommand "licenses"
            {
              nativeBuildInputs = [
                pkgs.reuse
                pkgs.jq
              ];
            }
            ''
              export HOME="$TMPDIR"
              cd ${self}
              reuse lint
              if ! reuse lint --json | jq -e '
                [.files[] | (.copyrights[], .spdx_expressions[]) | .source_type]
                | all(. == "reuse-toml")' > /dev/null; then
                echo "licenses: a file takes its notice or license from its own text" >&2
                echo "licenses: set precedence = \"override\" in its table of REUSE.toml" >&2
                exit 1
              fi
              if ! diff -Z LICENSE LICENSES/MPL-2.0.txt; then
                echo "licenses: LICENSE differs from LICENSES/MPL-2.0.txt" >&2
                exit 1
              fi
              touch "$out"
            '';

        # Fails when `versions.json` is missing or invalid, or when a workflow
        # or action of the hub installs Nix with another version than the one
        # in `versions.json`, or with an installer whose version the check
        # cannot read. The rules are in `nix/scripts/versions` and the
        # reference is `docs/reference/versions.md`. The check needs no
        # network: it reads files.
        versions =
          pkgs.runCommand "versions"
            {
              nativeBuildInputs = [ (mkVersionsTool pkgs) ];
            }
            ''
              versions ${self}
              touch "$out"
            '';

        # Runs the unit tests of `nix/scripts/versions`: the manifest with
        # valid and invalid files, and the rules for the installer steps with
        # trees that the tests write.
        check-versions-tests =
          pkgs.runCommand "check-versions-tests"
            {
              nativeBuildInputs = [ (decisionsPython pkgs) ];
              env = versionsEnv;
            }
            ''
              export HOME="$TMPDIR"
              python -m unittest discover -v -s ${./nix/tests/versions}
              touch "$out"
            '';

        # Runs the unit tests of `nix/scripts/release`: the rules for the tag
        # series and the changed paths, and the plan of a release against
        # temporary Git repositories with a fake `gh`. The tests need `git` and
        # a writable HOME, and they reach no network.
        check-release-tests =
          pkgs.runCommand "check-release-tests"
            {
              nativeBuildInputs = [
                pkgs.python3
                pkgs.git
              ];
              env = releaseEnv;
            }
            ''
              export HOME="$TMPDIR"
              python -m unittest discover -v -s ${./nix/tests/release}
              touch "$out"
            '';

        # Formats, lints and type-checks the hub's Python with ruff and mypy,
        # configured in `pyproject.toml`. Only the hub runs this check: it is
        # not part of `mkTreefmt`.
        python-quality =
          pkgs.runCommand "python-quality"
            {
              nativeBuildInputs = [
                pkgs.ruff
                (pkgs.python3.withPackages (ps: [
                  ps.jsonschema
                  ps.mypy
                  ps.pyyaml
                  ps.types-jsonschema
                  ps.types-pyyaml
                ]))
              ];
            }
            ''
              cd ${pythonQualitySource}
              ruff format --check --no-cache nix
              ruff check --no-cache nix
              mypy --cache-dir "$TMPDIR/mypy" \
                nix/scripts/decisions nix/tests/decisions \
                nix/scripts/leaks nix/tests/leaks \
                nix/scripts/release nix/tests/release \
                nix/scripts/versions nix/tests/versions
              touch "$out"
            '';
      });
    };
}
