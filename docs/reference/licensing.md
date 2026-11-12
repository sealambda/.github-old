# Licensing

The hub is licensed under the Mozilla Public License 2.0, SPDX identifier
`MPL-2.0`, except for the third-party content that this page lists. The flake
check `licenses` checks the licensing data of every file.

## License of the hub

| Item | Value |
| ---- | ----- |
| License | `MPL-2.0` |
| Copyright | 2026 Sealambda |
| Text | `LICENSES/MPL-2.0.txt`, copied from the SPDX License List |
| Copy for GitHub | `LICENSE`, the same text as `LICENSES/MPL-2.0.txt` |
| Declaration | `REUSE.toml`, in the format of [REUSE 3.3](https://reuse.software/spec-3.3/) |

GitHub reads `LICENSE` to show the license of the repository. `REUSE.toml`
declares the copyright and the license of each file, so no file has a license
header. `REUSE.toml` sets `precedence = "override"` in each table, so its data
wins over any text in a file. A contribution is under the license of the
repository that it changes
([CONTRIBUTING.md](../../CONTRIBUTING.md#pull-requests)).

## Third-party content

Third-party content is a file that the hub holds and that Sealambda didn't
write, or that Sealambda derived from another work. Its license is the license
of its source. `REUSE.toml` has one table for each row below, and `LICENSES/`
has the text of each license that a row names.

| File | Source | Version | License | Local changes |
| ---- | ------ | ------- | ------- | ------------- |
| `templates/adr.md.tmpl` | `template/adr-template.md` of [MADR](https://github.com/adr/madr) | `4.0.0` | `MIT OR CC0-1.0`, copyright 2017-2022 Oliver Kopp, Olaf Zimmermann | The comments and the `status` value in the front matter. The license applies to the changed file. |

The hub holds no other third-party content. These parts of the hub aren't
third-party content:

- The Vale styles Microsoft and Readability. Nix builds them from nixpkgs when
  a check runs, and the hub holds no copy of them.
- The tools and the GitHub Actions that the flake and the workflows name.
  They're references and not copies.
- The page structures of [Diátaxis](https://diataxis.fr/) and the format of
  [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/). The
  hub names them and holds none of their text.
- `flake.lock`, which holds data that Nix writes.

## What the check verifies

The check `licenses` runs in the Nix sandbox on the source tree, without
network access and without Git history. It fails when:

- A file has no copyright or no license.
- A license expression isn't valid SPDX, or it names a deprecated license.
- A license that a file names has no text in `LICENSES/`.
- `LICENSES/` holds a text that no file uses, or a file whose name isn't the
  SPDX identifier of a license followed by an extension.
- A file takes a copyright notice or a license expression from its own text
  and not from `REUSE.toml`. The tool reads the word `Copyright` followed by a
  space, anywhere in a line, as a notice, and a table without
  `precedence = "override"` then loses to it.
- `LICENSE` and `LICENSES/MPL-2.0.txt` differ, apart from a space or a tab at
  the end of a line.

`reuse lint` checks the first four rules, and its report in JSON, read by
`jq`, checks the fifth. The `diff` command checks the last.

## What the check can't verify

- That a new file is third-party content. `REUSE.toml` gives `MPL-2.0` to
  every file without a more specific table, so a copied file passes with the
  wrong license until someone adds its table. The author and the reviewer of
  a change that adds a file from another source decide. The how-to guide
  [Add third-party content](../how-to/add-third-party-content.md) gives the
  steps.
- That the copyright notice and the license expression of a third-party table
  match the source.
- That this page lists the same files as `REUSE.toml`.
- That a text in `LICENSES/` is the text of the SPDX License List. The check
  compares only `LICENSE` with `LICENSES/MPL-2.0.txt`. `reuse download`
  fetches a text from the list.

## Run it

`nix flake check` runs the check with the other checks. To run only this one,
replace `<system>` with your system, for example `x86_64-linux`:

```console
nix build .#checks.<system>.licenses -L
```

The command `reuse lint` in a shell with the `reuse` tool prints the same
report for the working tree.
