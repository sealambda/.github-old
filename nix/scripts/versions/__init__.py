"""Check that the workflows install the Nix version of `versions.json`.

`versions.json` at the root of the hub holds the version of Nix that the
organization standardizes on. A workflow pins that version with the `install_url`
input of `cachix/install-nix-action`. `versions.manifest` reads and validates
the file, `versions.workflows` checks the installer steps of a tree,
`versions.check` joins the two, and `versions.cli` is the command line.
"""
