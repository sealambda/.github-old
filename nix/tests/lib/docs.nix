# The cases of `lib.mkDocsCheck`. `default.nix` in this folder collects them.
# A case holds the check applied to a fixture and, for a case that must fail,
# the text that the log of the failure holds.
{
  pkgs,
  hub,
  harness,
}:
let
  # A project that the docs check can run on: the synced tool configuration,
  # the empty `Repository` Vale vocabulary that `.vale.ini` lists, and the
  # pages of `pages`.
  project =
    name: pages:
    harness.mkTree {
      name = "docs-${name}";
      synced = true;
      files = {
        ".vale/styles/config/vocabularies/Repository/accept.txt" = "";
      }
      // pages;
    };

  # A project with no tool configuration of its own: the pages of `pages` and
  # nothing else. The check then holds the hub's base configuration alone.
  bareProject =
    name: pages:
    harness.mkTree {
      name = "docs-bare-${name}";
      files = pages;
    };

  docsCheck = hub.mkDocsCheck pkgs;
in
{
  # Requirement: a project with no configuration file of its own passes the
  # check when its pages are clean. The hub's base configuration is the only
  # configuration, and the project needs no `Repository` Vale vocabulary.
  docs-no-local-file-passes = {
    check = docsCheck (bareProject "clean" { "README.md" = "# Title\n\nThis page is short.\n"; });
  };

  # Requirement: a project with no configuration file of its own still gets
  # the rules of the hub. The rule name in the log proves that Vale found the
  # hub's style from the base configuration.
  docs-no-local-file-applies-hub-rules = {
    check = docsCheck (
      bareProject "own-style-error" {
        "README.md" = "# Title\n\nThe server currently runs NixOS.\n";
      }
    );
    expectedLog = [
      "Sealambda.CurrentState"
      "check-docs: vale failed"
    ];
  };

  # Requirement: a project with no configuration file of its own can use the
  # terms of the hub's Vale vocabulary. Vale's dictionary doesn't know `treefmt`
  # and `zizmor`, so the page passes only when the base loads the vocabulary.
  docs-hub-vocabulary-is-loaded = {
    check = docsCheck (
      bareProject "hub-vocabulary" {
        "README.md" = "# Title\n\nRun treefmt and zizmor for Sealambda.\n";
      }
    );
  };

  # Requirement: a term in the project's own Vale vocabulary passes when the
  # project's `.vale.ini` lists the vocabulary, with no copy of the hub's
  # configuration in the project.
  docs-local-vocabulary-is-accepted = {
    check = docsCheck (
      bareProject "vocabulary" {
        "README.md" = "# Title\n\nThe zorblax runs fast.\n";
        ".vale.ini" = "StylesPath = .vale/styles\nVocab = Repository\n";
        ".vale/styles/config/vocabularies/Repository/accept.txt" = "zorblax\n";
      }
    );
  };

  # Requirement: a markdownlint-cli2 file of the project adds to the hub's
  # base. The page skips a heading level, which the project's file allows, and
  # the page passes.
  docs-local-markdownlint-file-is-layered = {
    check = docsCheck (
      bareProject "markdownlint-file" {
        "README.md" = "# Title\n\n### Skipped level\n";
        ".markdownlint-cli2.yaml" = "config:\n  MD001: false\n";
      }
    );
  };

  # Requirement: a project whose pages pass markdownlint-cli2, lychee and Vale
  # passes the check. This case proves that the failing cases below fail for
  # their page and not for the project. The project holds the files that
  # `sync-config` writes, so the case also proves that the legacy layout still
  # passes.
  docs-clean-passes = {
    check = docsCheck (project "clean" { "README.md" = "# Title\n\nThis page is short.\n"; });
  };

  # Requirement: a markdownlint-cli2 error fails the check. A page with two
  # top-level headings breaks rule MD025, and the log names the rule and the
  # tool that failed.
  docs-markdownlint-error-fails = {
    check = docsCheck (
      project "markdownlint-error" {
        "README.md" = "# Title\n\nThis page is short.\n\n# Second title\n\nThis page is short too.\n";
      }
    );
    expectedLog = [
      "MD025"
      "check-docs: markdownlint-cli2 failed"
    ];
  };

  # Requirement: a relative link to a page that does not exist fails the check,
  # and the log names the target of the link.
  docs-broken-link-fails = {
    check = docsCheck (
      project "broken-link" {
        "README.md" = "# Title\n\nRead [the missing page](missing-page.md).\n";
      }
    );
    expectedLog = [
      "missing-page.md"
      "check-docs: lychee failed"
    ];
  };

  # Requirement: a Vale error of the hub's own style `Sealambda` fails the
  # check. The rule name in the log proves that Vale found the style, because
  # a Vale that fails to start does not print it.
  docs-own-style-error-fails = {
    check = docsCheck (
      project "own-style-error" {
        "README.md" = "# Title\n\nThe server currently runs NixOS.\n";
      }
    );
    expectedLog = [
      "Sealambda.CurrentState"
      "check-docs: vale failed"
    ];
  };
}
