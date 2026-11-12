#!/usr/bin/env bash
# Validates the Renovate configuration files of a source tree.
#
# Usage: renovate-config ROOT [PRESET...]
#
# ROOT is a directory, normally the `self` source of a flake: a read-only path
# in the Nix store. The script validates each file that ROOT holds under one of
# the names that Renovate reads (the array `config_files` below), and each
# PRESET, a file path relative to ROOT that the repository publishes as a shared
# preset, such as `default.json`. A PRESET path may not leave ROOT: it may not
# be absolute and may not hold a `..` component.
#
# One run of `renovate-config-validator --strict --no-global` validates all the
# files. `--strict` makes a configuration that needs a migration fail, such as
# `config:base`, which Renovate renames. `--no-global` makes the validator read
# each file as the configuration of a repository. Without it the validator
# reads a file as the global configuration of a Renovate server, which accepts
# options that only a server may set, such as `autodiscover`.
#
# The script passes the files by absolute path and never runs the validator
# without a file. Called without a file, the validator reads the files of its
# working directory, which is not ROOT. So a tree with no file ends here with
# status 0, before the validator starts.
#
# The key `renovate` of `package.json` is a name that Renovate reads, but the
# validator can't take it: it reads `package.json` as a configuration file and
# rejects the key `renovate` as an unknown option. So the script fails when
# `package.json` holds the key, and the message tells the reader to move the
# configuration to a file.
#
# A configuration name that is a symbolic link to nothing fails the script. A
# test with `-f` alone would count it as no file, so the check would pass over a
# file that Renovate would try to read.
#
# The validator does not resolve `extends`: a preset name that doesn't exist
# passes. It needs no network. `nix/lib/renovate-config.nix` wraps this script
# with `writeShellApplication`, which also runs shellcheck on it, puts the
# validator of the hub's nixpkgs and `jq` on `PATH`, and builds the flake check
# `renovate-config` and the function `lib.mkRenovateConfigCheck` on it. The
# flake check `lib-functions` tests it with the cases `renovate-config-*`.
#
# Exit status: 0 when every file is valid or ROOT holds no file, 1 when the
# validator reports a problem or `package.json` holds the key `renovate`, 2 when
# a PRESET file doesn't exist or leaves ROOT or a configuration name is a
# dangling symbolic link, 3 for a wrong call or when the validator fails to
# run.
#
# Status 1 of the validator is not always a finding. The validator ends with
# status 1 for a problem in a file, and Node ends with status 1 for an uncaught
# error before the validator starts, such as a missing module. The script can't
# tell the two apart, so it maps both to status 1. The check still fails, and
# the log shows the error of Node and not a finding. The validator ends with
# status 99 for its own uncaught error, and that is status 3 here.

set -euo pipefail

# The files that Renovate reads as the configuration of a repository, relative
# to the root of the repository, in the order of Renovate's own list. The test
# `renovate-config-names-match-renovate` compares this list, and `package.json`
# below it, with the list in the Renovate package, so an upgrade of Renovate
# that adds a name fails the test. Keep one name on each line: the test reads
# the lines between `config_files=(` and the closing parenthesis.
config_files=(
  renovate.json
  renovate.jsonc
  renovate.json5
  .github/renovate.json
  .github/renovate.jsonc
  .github/renovate.json5
  .gitlab/renovate.json
  .gitlab/renovate.jsonc
  .gitlab/renovate.json5
  .renovaterc
  .renovaterc.json
  .renovaterc.jsonc
  .renovaterc.json5
)

# The file whose key `renovate` Renovate reads as configuration.
package_file=package.json

# Prints the usage and exits with status 3.
usage() {
  echo "usage: renovate-config ROOT [PRESET...]" >&2
  exit 3
}

# Prints the absolute path of each file that ROOT $1 holds from the list
# `config_files`, one per line, in the order of the list.
find_config_files() {
  local root=$1 file
  for file in "${config_files[@]}"; do
    if [ -f "$root/$file" ]; then
      echo "$root/$file"
    fi
  done
}

# Exits with status 2 and names each configuration name, `config_files` and
# `package_file`, that is a symbolic link to nothing in ROOT $1. Returns when
# there is none.
require_no_dangling_links() {
  local root=$1 file dangling=0
  for file in "${config_files[@]}" "$package_file"; do
    if [ -L "$root/$file" ] && [ ! -e "$root/$file" ]; then
      echo "renovate-config: dangling symbolic link: $file" >&2
      dangling=1
    fi
  done
  if [ "$dangling" -ne 0 ]; then
    exit 2
  fi
}

# Succeeds when the path $1 can leave the directory that it is relative to: it
# is absolute or has a `..` component.
leaves_root() {
  case "/$1/" in
  //* | */../*) return 0 ;;
  *) return 1 ;;
  esac
}

# Exits with status 2 and names each PRESET that leaves ROOT $1 or that ROOT
# doesn't hold. The presets are the later arguments. Returns when all of them
# are files inside ROOT.
require_presets() {
  local root=$1 preset missing=0
  shift
  for preset in "$@"; do
    if leaves_root "$preset"; then
      echo "renovate-config: preset path leaves the source: $preset" >&2
      missing=1
    elif [ ! -f "$root/$preset" ]; then
      echo "renovate-config: preset file not found: $preset" >&2
      missing=1
    fi
  done
  if [ "$missing" -ne 0 ]; then
    exit 2
  fi
}

# Succeeds when the file `package_file` of ROOT $1 is a JSON object whose key
# `renovate` is truthy in JavaScript, the test that Renovate applies. A file
# that isn't valid JSON counts as no key, as it does for Renovate.
uses_package_key() {
  local file=$1/$package_file
  [ -f "$file" ] &&
    jq -e '(type == "object") and ((.renovate // null) | . != null and . != 0 and . != "")' \
      "$file" >/dev/null 2>&1
}

main() {
  if [ "$#" -lt 1 ]; then
    usage
  fi
  local root=$1
  shift
  if [ ! -d "$root" ]; then
    echo "renovate-config: $root is not a directory" >&2
    exit 3
  fi
  root=$(cd "$root" && pwd)

  require_presets "$root" "$@"
  require_no_dangling_links "$root"

  local files=() file preset status=0
  while IFS= read -r file; do
    files+=("$file")
  done < <(find_config_files "$root")
  for preset in "$@"; do
    files+=("$root/$preset")
  done
  if uses_package_key "$root"; then
    echo "renovate-config: $package_file holds the key \"renovate\". Renovate still" \
      "reads it, but the validator can't check it. Move the configuration to a" \
      "file such as renovate.json." >&2
    status=1
  fi
  if [ "${#files[@]}" -eq 0 ]; then
    if [ "$status" -eq 0 ]; then
      echo "renovate-config: no Renovate configuration file in $root"
    fi
    exit "$status"
  fi

  local validator_status=0
  renovate-config-validator --strict --no-global "${files[@]}" || validator_status=$?
  case "$validator_status" in
  0) ;;
  1) status=1 ;;
  *)
    echo "renovate-config: the validator failed with status $validator_status" >&2
    exit 3
    ;;
  esac
  exit "$status"
}

main "$@"
