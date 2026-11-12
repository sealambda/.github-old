# Change a toolchain version

Move a package of a hub dev shell to another version. The
[Toolchain versions](../reference/versions.md) page lists the attributes and the
rules.

## Steps

1. In `flake.nix`, change the attribute name, for example `pnpm_12` to
   `pnpm_13`. The attribute must exist in the locked nixpkgs. If it does not,
   run `nix flake update nixpkgs` first.
2. Run `nix develop .#node -c pnpm --version` to see the new version.
3. Run `nix flake check`.
4. Open a pull request. A consumer takes the change when its `hub` input moves
   to the merged revision.
