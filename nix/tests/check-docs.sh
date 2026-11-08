#!/usr/bin/env bash
# Tests for `nix/scripts/check-docs.sh`.
#
# Usage: bash nix/tests/check-docs.sh
#
# The commands `check-docs` and `sync-config` must be on PATH. They must be
# the `writeShellApplication` wrappers that `flake.nix` builds, because they
# carry their own tools. The flake check `check-docs-tests` runs this file.
#
# Each case generates a small project under a temporary directory. The project
# gets the hub's tool configuration from `sync-config`, so the test needs no
# second list of config files. The bad documents exist only at run time:
# tracked bad Markdown files would fail the hub's own documentation check.
# A failing case also asserts the text that the failing tool prints, because a
# tool that can't start, for example Vale without its styles, exits non-zero
# too and must not pass as the expected failure. The first failed assertion
# prints its case name and stops the run with exit status 1.

set -euo pipefail

WORK=$(mktemp -d)
readonly WORK
trap 'rm -rf -- "$WORK"' EXIT

readonly OUT=$WORK/output

# Set by `new_project`: the project directory of the running case.
PROJECT=
# Set by `run_check`: the exit status of the last run.
STATUS=0

# --- Helpers ---------------------------------------------------------------

# Prints the failure message $1 with the name of the running case, then the
# output of the last run, and exits 1.
fail() {
  echo "FAIL: ${CURRENT_CASE:-setup}: $1" >&2
  if [ -f "$OUT" ]; then
    echo "--- output of the last run:" >&2
    cat "$OUT" >&2
  fi
  exit 1
}

# Fails unless the last run exited with the status $1.
assert_status() {
  [ "$STATUS" = "$1" ] || fail "exit status: expected $1, got $STATUS"
}

# Fails unless the output of the last run contains the text $1.
assert_output_contains() {
  grep -qF -- "$1" "$OUT" || fail "the output lacks '$1'"
}

# Fails if the output of the last run contains the text $1.
assert_output_lacks() {
  ! grep -qF -- "$1" "$OUT" || fail "the output has '$1'"
}

# Creates the project directory $WORK/$1 and sets PROJECT to its path. The
# project has the synced tool configuration, an empty `Repository` Vale
# vocabulary and a `README.md` that passes all three tools.
new_project() {
  PROJECT=$WORK/$1
  mkdir -p "$PROJECT/.vale/styles/config/vocabularies/Repository"
  (cd "$PROJECT" && sync-config)
  : >"$PROJECT/.vale/styles/config/vocabularies/Repository/accept.txt"
  printf '# Title\n\nThis page is short.\n' >"$PROJECT/README.md"
  rm -f "$OUT"
}

# Runs `check-docs` with the arguments $1 and later. Sets STATUS to its exit
# status and writes its stdout and stderr to OUT.
run_check() {
  STATUS=0
  check-docs "$@" >"$OUT" 2>&1 || STATUS=$?
}

# Writes a page with a Vale error into the project: Microsoft.Contractions has
# the level error.
add_vale_error() {
  printf '# Vale\n\nIt does not work.\n' >"$PROJECT/vale.md"
}

# Writes the page `lint.md` with a markdownlint error into the directory $1 of
# the project, or into the project root without an argument. MD001 forbids a
# heading level that skips a level. The function creates the directory.
add_markdownlint_error() {
  local dir=$PROJECT/${1:-.}
  mkdir -p "$dir"
  printf '# Lint\n\n### Skipped level\n' >"$dir/lint.md"
}

# Writes a page into the project that only Vale's spelling rule flags: the
# word `zorblax` is in no dictionary. `Vale.Spelling` has the level error.
add_unknown_term() {
  printf '# Term\n\nThe zorblax runs fast.\n' >"$PROJECT/term.md"
}

# Writes a page with a broken relative link into the project.
add_broken_link() {
  printf '# Link\n\nRead [the missing page](missing-page.md).\n' >"$PROJECT/link.md"
}

# --- Cases -----------------------------------------------------------------

# A project with only clean pages passes, and each tool runs.
case_clean_project_passes() {
  new_project clean

  run_check "$PROJECT"

  assert_status 0
  assert_output_contains "==> markdownlint-cli2"
  assert_output_contains "==> lychee"
  assert_output_contains "==> vale"
}

# A Vale error fails the check and names the rule. The rule name also proves
# that Vale found the Microsoft style.
case_vale_error_fails() {
  new_project vale
  add_vale_error

  run_check "$PROJECT"

  assert_status 1
  assert_output_contains "Microsoft.Contractions"
  assert_output_contains "check-docs: vale failed"
}

# A markdownlint error fails the check and names the rule.
case_markdownlint_error_fails() {
  new_project markdownlint
  add_markdownlint_error

  run_check "$PROJECT"

  assert_status 1
  assert_output_contains "MD001"
  assert_output_contains "check-docs: markdownlint-cli2 failed"
}

# A broken relative link fails the check and names the target.
case_broken_link_fails() {
  new_project link
  add_broken_link

  run_check "$PROJECT"

  assert_status 1
  assert_output_contains "missing-page.md"
  assert_output_contains "check-docs: lychee failed"
}

# A failing tool does not stop the other tools: one run reports every problem.
case_every_tool_runs_after_a_failure() {
  new_project all
  add_markdownlint_error
  add_broken_link
  add_vale_error

  run_check "$PROJECT"

  assert_status 1
  assert_output_contains "check-docs: markdownlint-cli2 failed"
  assert_output_contains "check-docs: lychee failed"
  assert_output_contains "check-docs: vale failed"
}

# A term that Vale flags passes once the project lists it in its own `Repository`
# vocabulary. The run first fails and then passes with the same page, so the
# vocabulary in SRC is what changes the result: the script reads the project
# vocabulary from SRC and not from the hub or the working directory.
case_project_vocabulary_is_read() {
  new_project vocabulary
  add_unknown_term

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "Vale.Spelling"
  assert_output_contains "zorblax"
  assert_output_contains "check-docs: vale failed"

  echo zorblax >>"$PROJECT/.vale/styles/config/vocabularies/Repository/accept.txt"

  run_check "$PROJECT"
  assert_status 0
}

# A nested `.markdownlint-cli2.yaml` that disables MD001 makes the page in its
# directory pass. The same page at the root still fails, so the nested file
# applies to its own directory only, and the script reads it from SRC.
case_nested_markdownlint_config_applies_to_its_directory() {
  new_project nested
  add_markdownlint_error docs
  printf 'config:\n  MD001: false\n' >"$PROJECT/docs/.markdownlint-cli2.yaml"

  run_check "$PROJECT"
  assert_status 0

  add_markdownlint_error

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "MD001"
  assert_output_contains "check-docs: markdownlint-cli2 failed"
  assert_output_lacks "docs/lint.md"
}

# A wrong argument count or a missing directory prints a message and exits 2.
case_wrong_arguments_exit_2() {
  new_project arguments

  run_check
  assert_status 2
  assert_output_contains "usage: check-docs SRC"

  run_check "$PROJECT" extra
  assert_status 2

  run_check "$WORK/no-such-directory"
  assert_status 2
  assert_output_contains "is not a directory"
}

# --- Run -------------------------------------------------------------------

# Runs each case in the list below. The cases are independent: each one builds
# its own project. The list is explicit because the minimal Bash of the Nix
# sandbox has no `compgen`. Add each new case here.
main() {
  local -a cases=(
    case_clean_project_passes
    case_vale_error_fails
    case_markdownlint_error_fails
    case_broken_link_fails
    case_every_tool_runs_after_a_failure
    case_project_vocabulary_is_read
    case_nested_markdownlint_config_applies_to_its_directory
    case_wrong_arguments_exit_2
  )
  local name
  for name in "${cases[@]}"; do
    CURRENT_CASE=$name
    echo "run:  $name"
    "$name"
    echo "ok:   $name"
  done
  echo "All ${#cases[@]} cases passed."
}

main
