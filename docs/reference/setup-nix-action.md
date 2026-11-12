# Setup Nix action

The composite action `.github/actions/setup-nix` installs the Nix version that
`versions.json` at the root of the hub pins. A job that calls it never repeats
the number: a change of `versions.json` changes every caller. The
[Toolchain versions](versions.md#nix) page says what the version is and why the
hub pins it.

## Use

In the hub's own workflows, check out the repository first, then call the
action by its path:

```yaml
- uses: actions/checkout@<revision>
- uses: ./.github/actions/setup-nix
```

The step has no inputs. After it, `nix` is on the path of the later steps of
the job. The action runs on a runner that has `jq` and `bash`: see
[Requirements](#requirements).

Only the hub's own workflows call the action. The use from another repository
isn't verified: see [Not verified](#not-verified).

## Inputs and outputs

| Name | Kind | Meaning |
| ---- | ---- | ------- |
| none | Input | The action has no input. The version comes from `versions.json` only. |
| `version` | Output | The installed version, as `MAJOR.MINOR.PATCH`. |

## What the action does

1. The step `version` runs the script `read-version.sh` of the action folder
   on `versions.json`. The path is `$ACTION_DIR/../../../versions.json`, where
   `ACTION_DIR` is `${{ github.action_path }}`, the folder of the action: the
   file is three folders above it, at the root of the repository that holds
   the action. The folder reaches the shell through the environment variable
   `ACTION_DIR`, not through the script text. The script reads the key `nix`
   with `jq` and writes the value to the step output `nix`.
2. The step that follows runs `cachix/install-nix-action`, pinned by revision,
   with `install_url` set to
   `https://releases.nixos.org/nix/nix-<version>/install`, where `<version>`
   is the output of step 1.

The action reads the file of the checkout that holds the action. It doesn't
download the manifest, so it needs no network beyond the installer.

## Failure modes

Every failure stops the job at the step `version`, before any installer runs,
and prints an error annotation that starts with `setup-nix`.

| Cause | Message says |
| ----- | ------------ |
| The file isn't at the path above. | `versions.json not found at <path>`, and that the action reads it three folders above its own folder. |
| The file isn't valid JSON, has no key `nix`, or the value isn't a string. | `versions.json has no string value for the key nix, or is not valid JSON`. |
| The value isn't `MAJOR.MINOR.PATCH`, each number `0` or without a leading zero. | `the value of nix in versions.json is not a version of the form MAJOR.MINOR.PATCH`. |

A version that has the right form but no installer at `releases.nixos.org`
fails later, in the installer step, with its own error. The flake check
[`versions`](versions.md#the-check) validates the file against the schema in
every pull request, so a bad manifest rarely reaches a run.

## Requirements

The action needs `bash` and `jq`. The Ubuntu images that GitHub hosts have
both, and the [software list][runner-list] of the image names `jq`. The hub's
jobs use the label `ubuntu-latest`, which GitHub moves to newer images, so this
page names no image or package version. A self-hosted runner needs its own
`jq`.

## The `versions` check

The flake check `versions` reads this file like any other `action.yml`. Its
`install_url` is the expression
`https://releases.nixos.org/nix/nix-${{ steps.version.outputs.nix }}/install`.
Only this file may use the expression. The check accepts it when both of these
hold:

- The file is `.github/actions/setup-nix/action.yml`, at that path from the
  root of the checked tree.
- Exactly one earlier step has the `id` `version`, and that step equals the
  constant `READ_VERSION_STEP` in
  `nix/scripts/versions/action_output.py`, key for key. The step has an `id`, a
  `shell`, the one `env` variable `ACTION_DIR` and the `run` line that starts
  `read-version.sh` on the root `versions.json`. It has no other key, so no
  condition, working directory or ignored failure can change it.

The check holds only that step. It doesn't read the other steps of the action
or the keys of the installer step other than `install_url`: review covers
them.

A finding names the keys in which the step differs. A workflow never gets the
expression form: its `install_url` must be the exact address.

The check proves only that the action runs `read-version.sh` on the root
`versions.json` and passes the output to the installer. It doesn't read the
script and doesn't run the action. The script has unit tests of its own, in the
flake check `check-versions-tests`: they run it with `jq` on manifests that
are valid and invalid. At run time, the job `flake-check` of `ci.yml` asserts
that `nix --version` and the output `version` both equal the value in
`versions.json`. No other job asserts it. The rules are in
[Toolchain versions](versions.md#the-check).

## Not verified

- The folder layout of a cross-repository call. The path of the action assumes
  that `github.action_path` is the folder of the action inside a checkout of
  its repository at the pinned revision, so `versions.json` is three folders
  up. GitHub's documentation describes `github.action_path` as the path where
  an action is located, for composite actions. The hub hasn't run the action
  from another repository, and its own jobs use the local form, where the
  layout is the workspace.
- The fallback, if the layout differs. A workflow in a consumer checks out the
  hub at the pinned revision into a folder of the workspace, then calls the
  copy by its local path. The copy has the layout of a checkout, and the
  action reads the `versions.json` of the same revision. The hub's reusable
  workflow `standards.yml` is the place for this step. The hub has no such
  file, so this page describes no call of it.

[runner-list]: https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md
