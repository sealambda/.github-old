# The formatter of the organization. `flake.nix` imports this file for the
# hub's own formatter and `formatting` check and exports `mkTreefmt` as
# `lib.mkTreefmt`, which a consumer calls. The module that it evaluates is
# `treefmt.nix` at the root of the hub.
{ treefmt-nix }:
{
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
      imports = [ ../../treefmt.nix ] ++ extraModules;
    };
}
