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

  docsCheck = hub.mkDocsCheck pkgs;
in
{
  # Requirement: a project whose pages pass markdownlint-cli2, lychee and Vale
  # passes the check. This case proves that the failing cases below fail for
  # their page and not for the project.
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
