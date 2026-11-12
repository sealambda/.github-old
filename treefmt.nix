# The organization's treefmt module. `flake.nix` exports it through
# `lib.mkTreefmt`. Every program here either formats a file or fails the check.
{
  projectRootFile = "flake.nix";

  programs = {
    actionlint.enable = true;
    nixfmt.enable = true;

    # Prettier formats the Markdown files and wraps prose at 80 columns.
    # `includes` and `overrides` are lists, so a consumer that sets Prettier for
    # other files adds to them. The settings sit in an override, so they apply
    # only to Markdown and a consumer can set its own top-level settings.
    prettier = {
      enable = true;
      includes = [ "*.md" ];
      settings.overrides = [
        {
          files = [ "*.md" ];
          options = {
            proseWrap = "always";
            printWidth = 80;
            embeddedLanguageFormatting = "off";
          };
        }
      ];
    };

    shellcheck.enable = true;
    shfmt.enable = true;
    typos.enable = true;
    zizmor.enable = true;
  };

  # Run zizmor with its strictest persona.
  settings.formatter.zizmor.options = [ "--persona=pedantic" ];
}
