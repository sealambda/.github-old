#!/usr/bin/env bash
# The text of the `git` command that the scanner of `secrets-scan` runs.
# `nix/lib/secrets-scan.nix` wraps it with `writeShellApplication`, names it
# `git`, and `secrets-scan` puts its folder first on PATH, so the scanner and
# the check before the scan both call this command and not Git itself. It sets
# one variable:
#
#   SECRETS_SCAN_REAL_GIT  The Git command that does the work.
#
# The command runs Git with the same arguments, and adds two options after the
# subcommand `diff` or `log`:
#
#   --text        Without it, Git prints "Binary files differ" in place of the
#                 diff of a file that is binary for Git, and a scanner finds
#                 nothing in such a file. Anyone who can commit makes a file
#                 binary, with a NUL byte in it or with a line `* -diff` in a
#                 `.gitattributes` file, so a scan that accepts Git's decision
#                 lets a secret pass. `--text` makes Git print the diff of
#                 every file.
#   --no-renames  With rename detection, Git prints a moved file that has no
#                 edit as `rename from` and `rename to` lines and no hunk, so a
#                 scanner reads no line of it. A secret in a file at a path that
#                 the scanner's default rules skip, such as `creds.png`, would
#                 pass after a `git mv` to a path that they read. Without
#                 detection, Git prints the file at the new path as an addition
#                 with its whole content. It overrides `diff.renames`.
#
# The scanners build the command line themselves (`git -C <path> diff -U0
# --no-ext-diff --staged .` for the staged changes, `git -C <path> log -p -U0
# <log options>` for the history) and offer no way to add an option to the
# `diff` command, so a command that rewrites the command line is the one way
# that works for both scans and both scanners.
#
# The loop below finds the subcommand: the first argument that isn't a global
# option. The global options of Git 2.56 that take the next argument as their
# value are `-C`, `-c`, `--git-dir`, `--work-tree`, `--namespace`,
# `--config-env` and `--attr-source`: the loop skips both words of each. Every
# other word that starts with `-` stands alone, as in `--git-dir=<path>`. If a
# later Git adds a global option with a separate value, it needs an entry in
# the first pattern: until then the loop takes the value for the subcommand,
# and the command passes `diff` and `log` to Git without the two options.

args=("$@")
index=0
while [ "$index" -lt "${#args[@]}" ]; do
  case ${args[$index]} in
  -C | -c | --git-dir | --work-tree | --namespace | --config-env | --attr-source)
    index=$((index + 2))
    ;;
  -*) index=$((index + 1)) ;;
  *) break ;;
  esac
done

case ${args[$index]:-} in
diff | log)
  exec "$SECRETS_SCAN_REAL_GIT" "${args[@]:0:index+1}" --text --no-renames \
    "${args[@]:index+1}"
  ;;
*)
  exec "$SECRETS_SCAN_REAL_GIT" "$@"
  ;;
esac
