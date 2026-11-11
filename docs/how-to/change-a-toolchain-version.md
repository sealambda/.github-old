# Change a toolchain version

Move a package of a hub dev shell to another version. The
[Toolchain versions](../reference/versions.md) page lists the attributes and
the rules.

## Steps

1. In `flake.nix`, change the attribute name, for example `pnpm_12` to
   `pnpm_13`. The attribute must exist in the locked nixpkgs. If it doesn't,
   run `nix flake update nixpkgs` first.
2. Run `nix develop .#node -c pnpm --version` to see the new version.
3. Run `nix flake check`.
4. Open a pull request. A consumer takes the change when its `hub` input moves
   to the merged revision.

## Change the Nix version

The version of Nix isn't a nixpkgs attribute. `versions.json` holds it, and the
workflows pin it with `install_url`
([Nix](../reference/versions.md#nix)).

1. Pick a release that has an installer. This request answers 200 when it
   does:

   ```console
   curl -sI https://releases.nixos.org/nix/nix-<version>/install
   ```

2. In `versions.json`, set `nix` to the version as `MAJOR.MINOR.PATCH`.
3. In every step that uses `cachix/install-nix-action`, set `install_url` to
   `https://releases.nixos.org/nix/nix-<version>/install`. The hub has these
   steps in `.github/workflows/ci.yml` and `.github/workflows/secrets.yml`.
4. Run `nix flake check`. The check `versions` lists each step whose address
   differs from `versions.json`, with its file and line. It also lists a step
   that installs Nix another way, as the
   [check](../reference/versions.md#the-check) describes.
5. Open a pull request. A repository that calls `secrets.yml` runs the new
   version when its `hub` pin moves to the merged revision.
