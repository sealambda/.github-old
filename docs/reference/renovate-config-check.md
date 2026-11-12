# Renovate configuration check

The flake check `renovate-config` validates the Renovate configuration files of
a repository with the validator of Renovate. It fails when a file has an option
that Renovate doesn't know, a value of the wrong type, a syntax error, or a
setting that Renovate would migrate. It also fails when `package.json` holds
the key `renovate`. It runs with `nix flake check`, locally and in CI, and it
needs no network.

## Files

The check reads the 13 files of this table at the root of the source tree, in
the order of the list that Renovate keeps in its package. Renovate reads the
first file that it finds. The check validates every file that exists, so a file
that Renovate would ignore is validated too.

| File | Renovate reads it |
| ---- | ----------------- |
| `renovate.json`, `renovate.jsonc`, `renovate.json5` | On every platform. |
| `.github/renovate.json`, `.github/renovate.jsonc`, `.github/renovate.json5` | On GitHub only. |
| `.gitlab/renovate.json`, `.gitlab/renovate.jsonc`, `.gitlab/renovate.json5` | On GitLab only. |
| `.renovaterc` | On every platform. |
| `.renovaterc.json`, `.renovaterc.jsonc`, `.renovaterc.json5` | On every platform. |

Renovate has a 14th name, `package.json`, which it reads for the key
`renovate`. The check fails when `package.json` holds that key, as
[Limits](#limits) says. A tree that holds none of these files passes, so a
repository that doesn't use Renovate keeps its checks. A function call can also
list shared presets, which are files that the repository publishes, such as
`default.json` of the hub. The check validates each listed file as it
validates `renovate.json`. A listed file that doesn't exist fails the check,
and so does a path that leaves the source: an absolute path or a path with a
`..` component.

## Rules

The check runs `renovate-config-validator --strict --no-global` on all the
files in one run.

| Option | Effect |
| ------ | ------ |
| `--strict` | A file that needs a migration fails. For example, `config:base` is a name that Renovate renames, so a file that extends it fails. |
| `--no-global` | The validator reads each file as the configuration of a repository. An option that only a server may set, such as `autodiscover`, fails. |

The validator reports these problems, among others:

- An unknown option, such as `Invalid configuration option: nope`.
- A value of the wrong type, such as
  ``Configuration option `enabled` should be boolean``.
- A file that isn't valid JSON or JSON5, as `File could not be parsed`.
- A setting that needs a migration, as `Config migration necessary`.
- A global option in a repository file.

## Limits

- The validator doesn't resolve `extends`. A preset name that doesn't exist
  passes, and so does a preset whose content has a problem. The check validates
  a preset only when the call lists its file.
- The check reads only the files in the table of the section Files and the
  listed presets. It doesn't read a `config.js`. A Renovate server can add file
  names with its option `configFileNames`, and for a platform other than
  GitHub, GitLab and local it also reads `.<platform>/renovate.json`,
  `.jsonc` and `.json5`, such as `.gitea/renovate.json`. The check reads none
  of those.
- The validator can't check the key `renovate` of `package.json`. It reads
  `package.json` as a configuration file and rejects the key as an unknown
  option. Renovate still reads the key, with a deprecation warning, so the check
  fails when the key has a value that JavaScript counts as true, and the message
  tells the reader to move the configuration to a file. A `package.json` without
  the key, with a false key or that isn't valid JSON passes, as Renovate
  ignores it.
- A JSON file may hold comments, trailing commas or a byte order mark, and the
  check passes it. Renovate reads such a file: its parser strips the comments
  and the commas, and it reads a file with a byte order mark as JSON5. The
  validator prints a warning for the byte order mark and says that a future
  release of Renovate will drop that support. The check doesn't fail on a warning.
- A configuration name that's a link to a file that doesn't exist ends the
  check with status 2, and the check follows a link that works. The check
  doesn't compare a link with the folder of the source: a link in a Nix source
  can point anywhere that the source allows.
- A preset path with a `..` component fails even when it stays inside the
  source, such as `a/../default.json`. Write the path without it.
- The check validates the syntax and the option names of Renovate of the hub's
  nixpkgs. It doesn't prove that a rule matches a package or that a schedule
  has the effect that its author intends.

The check `lib-functions` holds the case `renovate-config-names-match-renovate`.
It reads the names from the script and the names from the Renovate package of
the hub's nixpkgs, and it fails when the two lists differ. A Renovate upgrade
that adds a name fails the check until someone adds the name to the script.

## Output and exit status

The validator prints its findings and a summary. The script that runs it ends
with one of these statuses:

| Status | Meaning |
| ------ | ------- |
| 0 | Every file is valid, or the tree holds no file. |
| 1 | The validator reports a problem, or `package.json` holds the key `renovate`. |
| 2 | A listed preset file doesn't exist or its path leaves the source, or a configuration name is a link to nothing. |
| 3 | A wrong call, or the validator failed to run. |

## Run the check

```console
nix build .#checks.x86_64-linux.renovate-config -L
```

A repository adds the check with `lib.mkRenovateConfigCheck`, as
[Adopt the hub in a repository](../how-to/adopt-the-hub.md) shows. The function
takes the package set, the source tree and a set that lists the presets:

```nix
renovate-config = hub.lib.mkRenovateConfigCheck pkgs self { presets = [ "default.json" ]; };
```

The third argument holds `presets`, a list of file paths relative to the root,
and its default is the empty list. The hub passes `default.json`, which is the
preset that other repositories extend.

The validator comes from the hub's own nixpkgs, whatever nixpkgs the repository
follows, so every repository runs one version of Renovate. The check has no
other option and no exclusion. The tests of the check are the cases
`renovate-config-*` of the check `lib-functions`.
