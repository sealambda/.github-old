#!/usr/bin/env bash
# The text of the `secrets-scan` command. `nix/lib/secrets-scan.nix` wraps it
# with `writeShellApplication`, which adds the shell options `errexit`,
# `nounset` and `pipefail` and runs ShellCheck on the text. It also puts `git`
# on PATH and sets three variables:
#
#   SECRETS_SCAN_SCANNER  The scanner command: gitleaks, or a scanner with the
#                         same `git` command and flags.
#   SECRETS_SCAN_CONFIG   The hub's base configuration, `config/gitleaks.toml`.
#   SECRETS_SCAN_GIT_DIR  The folder of a `git` command that adds `--text`:
#                         `nix/scripts/secrets-scan-git.sh`.
#
# Usage: secrets-scan history | staged
#
#   history  Scans every commit that Git history reaches, with all branches.
#            The CI job runs this.
#   staged   Scans the changes in the index. A pre-commit hook runs this.
#
# Both commands run at the top of the work tree, so the `.gitleaksignore` file
# at the root is found from any folder. The file content in a finding is
# redacted: a finding names the rule, the file, the line and the fingerprint,
# and never the secret in the file. The output can still show a secret that is
# in a file name, in a commit message or in an invalid `.gitleaksignore` entry;
# `docs/reference/secrets-scan.md` lists these cases.
#
# `history` refuses to scan a history that is incomplete, and both commands
# refuse to scan when Git can't produce the diff that the scanner reads. A
# scanner reports "no leaks" for a shallow clone, and gitleaks does so for a
# damaged object store or a failing `git diff` too, so the result would look
# clean and mean nothing.
#
# A scanner reads the output of `git diff` and `git log -p`, and it can't read
# a coloured diff or a diff that a filter has rewritten. Both commands pin the
# Git settings that change that output, whatever the user's configuration says:
# see `pin_diff_output`.
#
# Git prints "Binary files differ" and no lines for a file that it treats as
# binary: a file with a NUL byte, and a file that a `.gitattributes` line or
# `.git/info/attributes` marks with `-diff` or `binary`. A scanner finds nothing
# in such a file, and a person who can commit decides which file is binary. Both
# commands put a `git` first on PATH that adds `--text` to `git diff` and
# `git log`, so Git prints every file as text: see `use_text_git`. The same
# `git` adds `--no-renames`: a moved file that has no edit has no added line
# with rename detection, so a secret in a file that moved out of a path that the
# scanner skips would pass. Without detection, Git prints the file at the new
# path with its whole content.
#
# `history` shows the diff of a merge commit with `--diff-merges=remerge`: the
# changes that the person who merged made by hand, for example the resolution of
# a conflict. Without it `git log -p` prints no diff for a merge commit, and a
# secret that only the merge holds passes. Git has no such diff for a merge of
# three or more parents, so `history` refuses a history that has one: see
# `refuse_octopus_merges`.
#
# Exit status:
#   0  No finding.
#   1  A finding, or a failure of the scanner. The scanner uses 1 for both, so
#      the output says which.
#   2  A usage error.
#   3  `history` on a shallow clone. Nothing is scanned.
#   4  Git can't produce the diff that the scanner reads: a damaged history
#      for `history`, or a failing setting for either command. Also `history`
#      on a history that has a merge commit of three or more parents, which
#      has no diff to read. Nothing is scanned.
#   Other  A failure of `git`, for example 128 outside a work tree.

# The `git log` options of a scan of the history. `--log-opts` replaces the
# options that the scanners use otherwise: `--full-history --all
# --diff-filter=tuxdb`. The list differs from them in two places.
#   --diff-filter=uxdb  The scanners' filter has a `t` too, which leaves out the
#                       type changes. A commit that turns a symbolic link into a
#                       file would hide the content of the file. The filter
#                       leaves out only the changes that have no added lines:
#                       deletions, unmerged paths, unknown changes and broken
#                       pairs.
#   --diff-merges=remerge  Shows the diff of a merge commit.
# `refuse_unreadable_diff` reads with the same options, so the check reads what
# the scanner reads.
readonly -a HISTORY_LOG_OPTIONS=(
  --full-history --all --diff-filter=uxdb --diff-merges=remerge
)

# Prints the usage line to standard error.
usage() {
  echo "usage: secrets-scan history | staged" >&2
}

# Prints the text $1 in the quotes that Git uses for a word of
# `GIT_CONFIG_PARAMETERS`, the function `sq_quote_buf` of Git: single quotes
# around the text, and `'\''` for a single quote and `'\!'` for an exclamation
# mark inside it.
quote_for_git() {
  local text=${1//\'/\'\\\'\'}
  text=${text//!/\'\\!\'}
  printf "'%s'" "$text"
}

# Adds the Git setting with the key $1 and the value $2 to the variable
# `GIT_CONFIG_PARAMETERS`, in the form `'key'='value'` that `git -c` writes. Git
# reads this variable after every configuration file and after the variables
# `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_<n>` and `GIT_CONFIG_VALUE_<n>`, so it is
# the last source of configuration, and an entry at the end wins over every
# other setting of the same key. That includes the `git -c` options of the
# caller, which are in the same variable when a Git alias or hook runs this
# command. The settings of the caller for other keys stay.
add_git_setting() {
  local entry
  entry="$(quote_for_git "$1")=$(quote_for_git "$2")"
  export GIT_CONFIG_PARAMETERS="${GIT_CONFIG_PARAMETERS:+$GIT_CONFIG_PARAMETERS }$entry"
}

# Pins the Git settings that change the output of `git diff` and `git log -p`,
# for this process and the commands that it starts:
#   color.ui, color.diff  gitleaks parses a coloured diff without an error and
#                         finds nothing in it. The user's `color.ui=always`
#                         would make the scan pass a secret.
#   diff.<driver>.textconv  A textconv filter replaces the file content in the
#                         diff, and gitleaks scans the replacement. A
#                         `.gitattributes` line names a driver, and the user's
#                         configuration defines it. The setting `cat` leaves
#                         the content as it is, for every driver that any
#                         configuration file or the environment defines.
#   GIT_NO_REPLACE_OBJECTS  A `refs/replace` reference makes Git show another
#                         object in place of a commit, so a scan that honours
#                         it reads the replacement and not the commit. A
#                         mirror clone brings these references. betterleaks
#                         sets the variable itself, and gitleaks doesn't.
# The command `git diff` of the scanners already has `--no-ext-diff`, and
# `git log -p` runs no external diff program, so `diff.external` has no effect.
pin_diff_output() {
  add_git_setting color.ui never
  add_git_setting color.diff never
  export GIT_NO_REPLACE_OBJECTS=1
  local key
  # The status of `git config` is 1 when no driver has the setting. The process
  # substitution hides it from `errexit`, on purpose.
  while IFS= read -r key; do
    add_git_setting "$key" cat
  done < <(git config --name-only --get-regexp '^diff\..*\.textconv$')
}

# Puts the `git` command of `nix/scripts/secrets-scan-git.sh` first on PATH, for
# this process and the commands that it starts. The scanner and
# `refuse_unreadable_diff` both run `git`, so both get `--text` and
# `--no-renames`, and the check reads what the scanner reads. The flag `--text`
# overrides every other reason for a binary diff: the setting
# `diff.<driver>.binary` of a driver, and a file above `core.bigFileThreshold`.
# So `pin_diff_output` has no pin for either. The flag `--no-renames` overrides
# `diff.renames`, so it has no pin either.
use_text_git() {
  export PATH="$SECRETS_SCAN_GIT_DIR:$PATH"
}

# Exits with status 3 when the clone is shallow. A shallow clone lacks the older
# commits, and a scan of it passes whatever those commits hold.
refuse_shallow_clone() {
  if [ "$(git rev-parse --is-shallow-repository)" = true ]; then
    {
      echo "secrets-scan: this clone is shallow, so the history is incomplete."
      echo "Fetch the full history and scan again: set 'fetch-depth: 0' on"
      echo "actions/checkout, or run 'git fetch --unshallow'."
    } >&2
    exit 3
  fi
}

# Exits with status 4 when Git can't produce the output that the scanner reads.
# The function runs the Git command $2 and later, the same command that the
# scanner runs, and discards its output. The text $1 names what the command
# reads, for the message. The command fails when it exits with a status other
# than 0, or when it writes any message to standard error. The `git` of the
# command turns rename detection off, so Git has no warning about
# `diff.renameLimit` to print, and the check has no message to tolerate.
#
# The scanners don't notice such a failure. gitleaks exits 0 with "no leaks
# found" for a missing or a damaged object, for a `git diff` that fails and for
# a warning of Git on standard error, for example one about a value in a
# configuration file that Git can't parse. betterleaks exits 1 with a log
# line, the same status as a finding. `git log -p` fails with status 128 for a
# missing or a damaged object, so a walk with `git rev-list --objects --all` is
# not enough: it only checks that each object exists, and it passes a blob that
# holds garbage. `git cat-file --batch` and `git rev-list --verify-objects` read
# the content, but they exit 0 for some damaged objects. The message of Git on
# standard error names the object or the setting, and the function prints it.
refuse_unreadable_diff() {
  local reads=$1
  shift
  local messages status=0
  messages=$(git "$@" 2>&1 >/dev/null) || status=$?
  if [ "$status" -ne 0 ] || [ -n "$messages" ]; then
    echo "secrets-scan: Git can't produce the diff of $reads, so nothing was" \
      "scanned." >&2
    printf '%s\n' "$messages" >&2
    exit 4
  fi
}

# Exits with status 4 when a commit of the history has three or more parents, an
# octopus merge. Git has no `remerge` diff for such a merge: it prints the line
# "Skipping remerge-diff for octopus merges" in place of a diff, so the scanner
# reads nothing of what the author of the merge changed by hand, and a secret
# that only the merge holds passes with "no leaks found". The function lists the
# merge commits with the same refs as the scan (`--all`), and it exits with
# status 4 as well when Git can't list them.
refuse_octopus_merges() {
  local commits
  commits=$(git rev-list --min-parents=3 --all) || exit 4
  if [ -n "$commits" ]; then
    {
      echo "secrets-scan: the history has a merge commit of three or more" \
        "parents, and Git can't show what such a merge changed by hand, so" \
        "nothing was scanned. The commits:"
      echo "$commits"
    } >&2
    exit 4
  fi
}

# Runs the scanner with the arguments $1 and later after `git`, with the hub's
# base configuration. The flags are the same in gitleaks and in its forks:
#   --config    Use this file and no other configuration file.
#   --redact    Replace each secret with REDACTED in the output.
#   --verbose   Print each finding.
#   --no-banner and --no-color keep the output plain for a log or a hook.
scan() {
  exec "$SECRETS_SCAN_SCANNER" git "$@" \
    --config "$SECRETS_SCAN_CONFIG" \
    --redact \
    --verbose \
    --no-banner \
    --no-color
}

# Selects the scan from the one argument and runs it at the top of the work
# tree. Any other argument list is a usage error.
main() {
  if [ "$#" -ne 1 ]; then
    usage
    exit 2
  fi
  local -a mode
  case $1 in
  history) mode=("--log-opts=${HISTORY_LOG_OPTIONS[*]}") ;;
  staged) mode=(--staged) ;;
  *)
    usage
    exit 2
    ;;
  esac
  # A separate assignment keeps the status of `git`: `cd -- "$(git ...)"`
  # would hide a failure of the command substitution from `errexit`.
  local top
  top=$(git rev-parse --show-toplevel)
  cd -- "$top" || exit
  pin_diff_output
  use_text_git
  case $1 in
  history)
    refuse_shallow_clone
    refuse_unreadable_diff "the history" log --patch -U0 "${HISTORY_LOG_OPTIONS[@]}"
    refuse_octopus_merges
    ;;
  staged)
    refuse_unreadable_diff "the staged changes" diff -U0 --no-ext-diff --staged .
    ;;
  esac
  scan "${mode[@]}"
}

main "$@"
