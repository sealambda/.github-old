# The documentation gate. `flake.nix` imports this file. It uses
# `mkDocsTools` for the `docs` dev shell and for the tests of
# `nix/scripts/check-docs.sh`, and it exports `mkDocsCheck` as
# `lib.mkDocsCheck`, which a consumer calls. The script that runs the tools is
# `nix/scripts/check-docs.sh`, and the Vale style of the hub is
# `vale/Sealambda`.
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
        text = builtins.readFile ../scripts/check-docs.sh;
      };
    in
    {
      inherit valeWithStyles checkDocs tools;
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
      HOME="$TMPDIR" ${lib.getExe (mkDocsTools hubPkgs).checkDocs} ${src}
      touch "$out"
    '';
}
