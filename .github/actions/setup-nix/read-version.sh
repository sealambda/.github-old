#!/usr/bin/env bash
# Write the Nix version of a manifest as the step output `nix`.
#
# Usage: read-version.sh MANIFEST
#
# MANIFEST is the path of `versions.json`. The script reads the string value of
# the key `nix` and appends `nix=<value>` to the file that `GITHUB_OUTPUT`
# names, once. The value must have the form MAJOR.MINOR.PATCH, with no leading
# zero in a part.
#
# Exit status: 0 on success. 1 when the file is missing, isn't valid JSON, has
# no string value for `nix`, or the value has another form. The script then
# writes a GitHub error annotation to standard output and no output value.
#
# The step `version` of `action.yml` runs this file, and the check
# `nix/scripts/versions/action_output.py` requires that step to be exactly the
# canonical one. The unit tests are in
# `nix/tests/versions/test_versions_read_script.py`. `jq` is on the images
# that GitHub hosts: see `docs/reference/setup-nix-action.md`.

set -euo pipefail

manifest="${1:?usage: read-version.sh MANIFEST}"

if [ ! -f "$manifest" ]; then
  echo "::error title=setup-nix::versions.json not found at $manifest. The action reads it three folders above its own folder."
  exit 1
fi
if ! version="$(jq -er '.nix | strings' "$manifest")"; then
  echo "::error title=setup-nix::versions.json has no string value for the key nix, or is not valid JSON."
  exit 1
fi
if ! [[ $version =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
  echo "::error title=setup-nix::the value of nix in versions.json is not a version of the form MAJOR.MINOR.PATCH."
  exit 1
fi
echo "nix=$version" >>"$GITHUB_OUTPUT"
