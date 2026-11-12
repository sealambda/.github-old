# The documentation gate. `flake.nix` imports this file. It uses
# `mkDocsTools` for the `docs` dev shell and for the tests of
# `nix/scripts/check-docs.sh`, and it exports `mkDocsCheck` as
# `lib.mkDocsCheck`, which a consumer calls. The script that runs the tools is
# `nix/scripts/check-docs.sh`, and the Vale style of the hub is
# `vale/Sealambda`.
#
# The three tools are wrappers. Each wrapper starts the tool of the hub's
# nixpkgs with the hub's base configuration from the Nix store and lets the
# repository's own configuration file add to it. The files of `config/` are
# the one source of the hub's rules: the wrappers read them from the store, and
# `config.nix` copies the same files into a repository that still syncs them.
# `docs/reference/wrapped-tools.md` states what a repository can add to each
# tool and what it can't change.
{ lib, hubPackagesFor }:
let
  # The rule files of the Sealambda Vale style, without their test cases.
  # A change to a test case then doesn't rebuild the style.
  valeStyleRules = lib.fileset.toSource {
    root = ../../vale/Sealambda;
    fileset = lib.fileset.fileFilter (
      file: file.hasExt "yml" && !(lib.hasSuffix ".test.yml" file.name)
    ) ../../vale/Sealambda;
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

  # The base configuration of Vale, as a store path with two folders:
  #
  # - `config/vale/.vale.ini` is the hub's `config/vale.ini` with two changes.
  #   `StylesPath` names the folder `styles` of this store path, because a
  #   global configuration needs an absolute path. `Vocab` lists only the
  #   vocabulary of the hub: the vocabulary `Repository` belongs to a
  #   repository, and Vale stops with an error when a listed vocabulary is
  #   missing. `--replace-fail` fails the build when the hub's file stops
  #   holding one of the two lines.
  # - `styles/config/vocabularies/Sealambda/accept.txt` is the vocabulary of
  #   the hub.
  #
  # The folder `styles` holds only that vocabulary. It must not be the folder
  # that `VALE_STYLES_PATH` names: Vale then gives the rule names a hash
  # prefix, and a rule that a repository switches off no longer matches.
  mkValeBase =
    pkgs:
    pkgs.runCommand "vale-base-config" { } ''
      install -D -m 644 ${../../config/vale-vocabulary.txt} \
        "$out/styles/config/vocabularies/Sealambda/accept.txt"
      mkdir -p "$out/config/vale"
      substitute ${../../config/vale.ini} "$out/config/vale/.vale.ini" \
        --replace-fail 'StylesPath = .vale/styles' "StylesPath = $out/styles" \
        --replace-fail 'Vocab = Sealambda, Repository' 'Vocab = Sealambda'
    '';

  /**
    Builds the documentation tools from one package set: the three wrapped
    tools of the `docs` dev shell and of `mkDocsCheck`, and the `check-docs`
    command that runs them. The wrappers are commands named `vale`,
    `markdownlint-cli2` and `lychee`. Each one starts the tool of `pkgs` with
    the hub's base configuration and the repository's own file on top, as
    `docs/reference/wrapped-tools.md` states. The Vale of these tools has the
    styles Microsoft and Readability from nixpkgs and the hub's own style
    Sealambda.

    # Inputs

    `pkgs`
    : The package set of one system. The hub's `docs` shell and
      `mkDocsCheck` pass the hub's own package set.

    # Type

    ```
    mkDocsTools :: AttrSet -> { checkDocs :: Derivation; tools :: [Derivation]; }
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
      # its `share/vale/styles`, and Vale finds the styles there. Vale ignores
      # that variable when it runs with `--no-global`.
      valeWithStyles = pkgs.vale.withStyles (styles: [
        styles.microsoft
        styles.readability
        (mkValeStyleSealambda pkgs)
      ]);

      # Vale reads a global configuration from `$XDG_CONFIG_HOME/vale/.vale.ini`
      # and merges the `.vale.ini` of the repository over it: `Vocab` and
      # `BasedOnStyles` append, and each `[glob]` section applies. The
      # wrapper sets the variable, so the hub's base is the global file.
      # `--config` and `VALE_CONFIG_PATH` replace the project file that Vale
      # finds from the working directory upward, so a wrapper that sets either
      # one would drop the repository's layer unless it found that file
      # itself. The wrapper uses neither, and it unsets `VALE_CONFIG_PATH`
      # for the same reason. Two sources of configuration stay that the
      # wrapper can't remove: `docs/reference/wrapped-tools.md` states them.
      # The wrapper runs the Vale with the styles by its store path, so a
      # `vale` of the same name on `PATH` never starts a loop.
      vale = pkgs.writeShellApplication {
        name = "vale";
        runtimeEnv.XDG_CONFIG_HOME = "${mkValeBase pkgs}/config";
        text = ''
          unset VALE_CONFIG_PATH
          exec ${valeWithStyles}/bin/vale "$@"
        '';
      };

      # `--config` names the base file, and markdownlint-cli2 merges the
      # `.markdownlint-cli2.yaml` of the working directory and of each
      # directory of a Markdown file over it. A rule that a file lists
      # replaces the options of the base for that rule: the merge goes one
      # level deep. The base file is the hub's `config/markdownlint-cli2.yaml`
      # as it is.
      markdownlint-cli2 = pkgs.writeShellApplication {
        name = "markdownlint-cli2";
        text = ''
          exec ${lib.getExe pkgs.markdownlint-cli2} --config ${../../config/markdownlint-cli2.yaml} "$@"
        '';
      };

      # A `--config` option turns the automatic read of `lychee.toml` off, so
      # the wrapper passes that file itself, when it exists. lychee reads each
      # file in order: a list such as `exclude` or `exclude_path` grows with
      # the entries of each file, and a later value of a single option wins. The
      # hub's file comes last, so the hub's single options win over the
      # repository's. The base file is the hub's `config/lychee.toml` as it
      # is. lychee reads `.lycheeignore` from the working directory by itself.
      # lychee builds its HTTP client at startup, even when it runs offline,
      # and the client needs a trust store. The Nix sandbox has none, so the
      # wrapper sets `SSL_CERT_FILE` to the pinned `cacert` bundle. The hub's
      # file sets `offline`, so no request ever uses that bundle.
      lychee = pkgs.writeShellApplication {
        name = "lychee";
        runtimeEnv.SSL_CERT_FILE = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
        text = ''
          local_config=()
          if [ -f lychee.toml ]; then
            local_config=(--config lychee.toml)
          fi
          exec ${lib.getExe pkgs.lychee} "''${local_config[@]}" --config ${../../config/lychee.toml} "$@"
        '';
      };

      # The three documentation tools, listed once for `checkDocs` and for
      # the `docs` dev shell.
      tools = [
        lychee
        markdownlint-cli2
        vale
      ];

      # The `check-docs` command: the three tools with the flags in
      # `nix/scripts/check-docs.sh`. `writeShellApplication` lints the script
      # with shellcheck, and its header describes the script.
      checkDocs = pkgs.writeShellApplication {
        name = "check-docs";
        runtimeInputs = tools;
        text = builtins.readFile ../scripts/check-docs.sh;
      };
    in
    {
      inherit checkDocs tools;
    };
in
{
  inherit mkDocsTools;

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
    CI, the check reads the hub's base configuration from the Nix store, the
    configuration files that `src` holds, and no personal configuration of the
    user, and it needs no network: lychee runs offline, the Vale styles are in
    the Nix store, and the trust store that lychee loads at startup comes from
    Nix too. The same command runs locally and in CI: `nix flake check`, or
    `nix build .#checks.<system>.docs -L`. A local re-run on an unchanged
    `src` reuses the result by the hash of `src`.

    The hub's rules apply to a repository with no configuration file of its
    own. A repository adds to them with its own `.vale.ini`,
    `.markdownlint-cli2.yaml` and `lychee.toml`, and with the `.lycheeignore`
    file, and it can't change what `docs/reference/wrapped-tools.md` lists as
    fixed. A repository that still holds the copies that `sync-config` writes
    gets the same findings as before, because each copy equals the base.

    Pass the whole `self` of the calling flake, not a set of Markdown
    files, because lychee also checks links to files that are not
    Markdown.

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
      HOME="$TMPDIR" ${lib.getExe (mkDocsTools hubPkgs).checkDocs} ${src}
      touch "$out"
    '';
}
