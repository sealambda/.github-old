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

      # The functions of `lib` and the tools that the apps and the checks run
      # are in `nix/lib`. Each file starts with a comment that says what it
      # holds and who calls it. This file composes them into the outputs.
      inherit (import ./nix/lib/hub-packages.nix { inherit nixpkgs; }) hubPackagesFor;
      inherit (import ./nix/lib/treefmt.nix { inherit treefmt-nix; }) mkTreefmt;
      inherit (import ./nix/lib/config.nix { inherit (nixpkgs) lib; }) mkSyncConfig mkConfigCheck;
      inherit
        (import ./nix/lib/docs.nix {
          inherit (nixpkgs) lib;
          inherit hubPackagesFor;
        })
        mkDocsTools
        mkDocsCheck
        ;
      tools = import ./nix/lib/tools.nix { inherit (nixpkgs) lib; };
      inherit
        (import ./nix/lib/decisions.nix {
          inherit (nixpkgs) lib;
          inherit hubPackagesFor tools;
        })
        mkDecisionsCheck
        ;

      treefmtFor = eachSystem (pkgs: mkTreefmt pkgs [ ]);

      docsToolsFor = eachSystem mkDocsTools;

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
          program = nixpkgs.lib.getExe (tools.decisions.mkTool pkgs);
        };
      });

      # The `release` command for the releases of this repository. It is not a
      # tool for consumers: it reads the changed paths against the rules of the
      # hub (`nix/scripts/release/paths.py`). `nix run .#release -- plan` runs
      # it in the current repository. The CI builds it first and runs the
      # result in a later step, so that Nix runs without the token that
      # `publish` needs. The tool comes from the hub's nixpkgs.
      packages = eachSystem (pkgs: {
        release = tools.release.mkTool pkgs;
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
                (tools.decisions.python pkgs)
                pkgs.git
              ];
              env = tools.decisions.env;
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
              nativeBuildInputs = [ (tools.leaks.mkTool pkgs) ];
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
              env = tools.leaks.env;
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
              nativeBuildInputs = [ (tools.versions.mkTool pkgs) ];
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
              nativeBuildInputs = [ (tools.decisions.python pkgs) ];
              env = tools.versions.env;
            }
            ''
              export HOME="$TMPDIR"
              python -m unittest discover -v -s ${./nix/tests/versions}
              touch "$out"
            '';

        # Runs the unit tests of `nix/scripts/release`: the rules for the tag
        # series and the changed paths, and the plan of a release against
        # temporary Git repositories with a fake `gh`. The tests need `git` and
        # a writable HOME, and they reach no network. They compare the list of
        # patterns with the table of the reference page, which the variable
        # `HUB_RELEASES_DOC` names, because the test folder holds no page.
        #
        # The unit tests import the package and inject their runners, so they
        # do not run the `release` command that CI runs. The second part does:
        # it runs the built command in a temporary repository with one commit,
        # which covers the wrapper, its run-time inputs and the default runners.
        # A directory with a package `release` in it must not shadow the real
        # one, because the command runs in the repository of the caller.
        check-release-tests =
          pkgs.runCommand "check-release-tests"
            {
              nativeBuildInputs = [
                pkgs.python3
                pkgs.git
              ];
              env = tools.release.env // {
                HUB_RELEASES_DOC = "${./docs/reference/hub-releases.md}";
              };
            }
            ''
              export HOME="$TMPDIR"
              python -m unittest discover -v -s ${./nix/tests/release}

              release=${tools.release.mkTool pkgs}/bin/release
              mkdir "$TMPDIR/smoke"
              cd "$TMPDIR/smoke"
              git init --quiet --initial-branch=main
              git -c user.name=smoke -c user.email=smoke@example.com \
                -c commit.gpgsign=false \
                commit --quiet --allow-empty --message "feat: first commit"
              "$release" --help > /dev/null
              "$release" plan | grep --line-regexp "tag: v1.0.0"
              mkdir release
              echo "raise SystemExit('shadowed by the current directory')" \
                > release/__main__.py
              : > release/__init__.py
              "$release" plan | grep --line-regexp "tag: v1.0.0"

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
