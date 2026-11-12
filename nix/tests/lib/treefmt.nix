# The cases of `lib.mkTreefmt`. `default.nix` in this folder collects them. A
# case holds the check of the formatter applied to a fixture and, for a case
# that must fail, the text that the log of the failure holds.
{
  pkgs,
  hub,
  harness,
}:
let
  # The check of the formatter of the organization with the modules of
  # `extraModules` added, as a repository uses it for `checks.formatting`.
  formatCheckWith = extraModules: (hub.mkTreefmt pkgs extraModules).config.build.check;

  # The check of the organization's formatter without a module of its own.
  formatCheck = formatCheckWith [ ];

  # A tree for the formatter. It has the root file `flake.nix` that the
  # formatter looks for, and the file `example.nix` with the text `example`.
  tree =
    name: example:
    harness.mkTree {
      name = "treefmt-${name}";
      files = {
        "flake.nix" = "{ }\n";
        "example.nix" = example;
      };
    };

  # The text of a Nix file that the formatter changes.
  unformatted = "{a=1;}\n";

  # A module that a repository adds: it keeps `example.nix` out of every
  # formatter.
  excludeExample = {
    settings.global.excludes = [ "example.nix" ];
  };
in
{
  # Requirement: a tree whose Nix files the formatter would leave unchanged
  # passes the check.
  treefmt-formatted-passes = {
    check = formatCheck (tree "formatted" "{\n  a = 1;\n}\n");
  };

  # Requirement: a Nix file that the formatter would change fails the check,
  # and the log names the file and shows the change. This is also the case
  # without the module of `treefmt-extra-module-passes`.
  treefmt-unformatted-nix-fails = {
    check = formatCheck (tree "unformatted-nix" unformatted);
    expectedLog = [
      "example.nix"
      "+{ a = 1; }"
    ];
  };

  # Requirement: a module in `extraModules` changes the outcome. A module that
  # excludes the unformatted file makes the check pass, and the same file
  # fails the check without the module, in `treefmt-unformatted-nix-fails`.
  treefmt-extra-module-passes = {
    check = formatCheckWith [ excludeExample ] (tree "extra-module" unformatted);
  };
}
