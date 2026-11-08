#!/usr/bin/env bash
# Checks the Markdown files of a source tree with markdownlint-cli2, lychee
# and Vale.
#
# Usage: check-docs SRC
#
# SRC is a directory, normally the `self` source of a flake: a read-only path
# in the Nix store with no Git history. The script changes into SRC and runs
# each tool there, so every tool reads its configuration from SRC and never
# from the hub: the synced `.markdownlint-cli2.yaml`, `lychee.toml` and
# `.vale.ini`, the repository's own `Repository` Vale vocabulary, and the
# nested `.markdownlint-cli2.yaml` files. The flake check `config-in-sync`
# guarantees that the synced files match the hub. This script is the only
# place that holds the flags of the three tools. `flake.nix` wraps it with
# `writeShellApplication`, which also runs shellcheck on it, and builds the
# flake check `docs` and the function `lib.mkDocsCheck` on it. The flake
# check `check-docs-tests` runs `nix/tests/check-docs.sh` against it.
#
# The script runs all three tools even when an earlier one fails, so that one
# run reports every problem. Vale finds its styles through `VALE_STYLES_PATH`,
# which the hub's `vale.withStyles` package sets. The script must not pass
# `--no-global` to Vale, because that flag makes Vale ignore the variable.
#
# No tool writes into SRC: lychee runs offline without its cache, and the
# other two tools only read. This matters because SRC can be read-only.
#
# lychee builds its HTTP client at startup, even when it runs offline, and the
# client needs a trust store. The Nix sandbox has none, so `flake.nix` sets
# `SSL_CERT_FILE` to the pinned `cacert` bundle when it wraps this script. No
# request ever uses that bundle.
#
# Exit status: 0 when every tool passes, 1 when at least one tool fails, 2
# when the arguments are wrong or SRC is not a directory.

set -euo pipefail

# Set to 1 by `run_tool` when a tool fails.
failed=0

# Prints a header with the tool name $1, then runs the command $2 and later
# arguments. A failing command prints the name to stderr and sets `failed`.
# The script goes on, so that the later tools still run.
run_tool() {
  local name=$1
  shift

  echo "==> $name"
  if ! "$@"; then
    echo "check-docs: $name failed" >&2
    failed=1
  fi
}

main() {
  if [ "$#" -ne 1 ]; then
    echo "usage: check-docs SRC" >&2
    exit 2
  fi
  local src=$1
  if [ ! -d "$src" ]; then
    echo "check-docs: $src is not a directory" >&2
    exit 2
  fi

  cd "$src"
  run_tool markdownlint-cli2 markdownlint-cli2 "**/*.md"
  run_tool lychee lychee --no-progress "**/*.md"
  run_tool vale vale --minAlertLevel=error .
  exit "$failed"
}

main "$@"
