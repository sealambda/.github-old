#!/usr/bin/env bash
# Tests for `nix/scripts/check-docs.sh`.
#
# Usage: bash nix/tests/check-docs.sh
#
# The commands `check-docs`, `sync-config` and `vale` must be on PATH. They
# must be the packages that `nix/lib/docs.nix` and `nix/lib/config.nix` build,
# because they carry their own tools: `vale` is the one that has the style
# `Sealambda`. The flake check
# `check-docs-tests` runs this file. The test cases of the style rules are in
# `vale/Sealambda/*.test.yml`, and the flake check `vale-style-tests` runs them.
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

# Writes the page $1, a path relative to the project, with the title `Title`
# and the body text $2. The function creates the parent directories. Pass a
# body that only the rule under test flags, so that a failure names that rule.
write_page() {
  mkdir -p "$(dirname -- "$PROJECT/$1")"
  printf '# Title\n\n%s\n' "$2" >"$PROJECT/$1"
}

# Writes the pages `README.md` and `other.md`, which hold the cases of the
# anchor check. `other.md` has the heading `Real heading`, whose anchor is
# `real-heading`. `README.md` links to that anchor and to its own title, so
# both links are valid. The links to a missing anchor are added by the case.
add_anchor_pages() {
  printf '# Other\n\n## Real heading\n\nThe text.\n' >"$PROJECT/other.md"
  printf '# Title\n\nRead [the heading](other.md#real-heading) and [this title](#title).\n' \
    >"$PROJECT/README.md"
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

# A word of a plan fails the check and names the rule. The rule name also
# proves that Vale found the hub's own style `Sealambda`, which Nix adds to
# `VALE_STYLES_PATH`. The test cases of each listed word are in
# `vale/Sealambda/CurrentState.test.yml`.
case_current_state_term_fails() {
  new_project current-state
  write_page guide.md "The server currently runs NixOS."

  run_check "$PROJECT"

  assert_status 1
  assert_output_contains "Sealambda.CurrentState"
  assert_output_contains "'currently' describes a plan or a gap"
  assert_output_contains "check-docs: vale failed"
}

# Text in the present tense passes. So do the words that the rule leaves out on
# purpose, `planned` and `target`, and a listed word in a code span or a code
# block: these are the expected non-hits of the rule.
case_current_state_non_hits_pass() {
  new_project non-hits
  cat >"$PROJECT/guide.md" <<'EOF'
# Title

The planned window is part of the contract. The target group routes the
traffic. Run `tofu apply -target=aws_iam_role.this`.

```text
TODO is a word in a code block.
```
EOF

  run_check "$PROJECT"

  assert_status 0
  assert_output_lacks "Sealambda.CurrentState"
}

# A word of a history doesn't fail the check, because `Sealambda.History` has
# the level suggestion and the script runs Vale with `--minAlertLevel=error`.
# The same word in a Vale run without that flag proves that the rule is loaded:
# the check passes because of the level and not because the rule is missing.
case_history_term_does_not_fail() {
  new_project history
  write_page guide.md "The service previously ran on Fly."

  run_check "$PROJECT"

  assert_status 0
  assert_output_lacks "Sealambda.History"

  # Vale prints a suggestion when no level is set.
  STATUS=0
  (cd "$PROJECT" && vale --output=line guide.md) >"$OUT" 2>&1 || STATUS=$?

  assert_status 0
  assert_output_contains "Sealambda.History:'previously' may describe history"
}

# The rule `Sealambda.CurrentState` is off for the decision records and the
# specs, also under another folder, and on for any other page. The first run
# lists a page of each off folder, and passes. The second run adds a page with
# the same text in `docs/`, and fails for that page only: the off sections, and
# not the folder name `docs`, change the result.
case_current_state_is_off_for_decisions_and_specs() {
  new_project off-sections
  write_page docs/decisions/0001-record.md "The tool will be replaced."
  write_page docs/specs/0001-spec.md "The tool will be replaced."
  write_page services/api/docs/specs/0002-spec.md "The tool will be replaced."

  run_check "$PROJECT"
  assert_status 0

  write_page docs/guide.md "The tool will be replaced."

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "docs/guide.md"
  assert_output_contains "Sealambda.CurrentState"
  assert_output_lacks "decisions/"
  assert_output_lacks "specs/"
}

# The shipped lychee configuration checks the anchors of local links, also
# offline. A link to a heading that exists passes, in another page and in the
# same page. A link to a missing heading fails, in another page and in the same
# page. The project gets its `lychee.toml` from `sync-config`, so this case
# fails when the hub's file lacks `include_fragments`.
case_local_anchors_are_checked() {
  new_project anchors
  add_anchor_pages

  run_check "$PROJECT"
  assert_status 0

  printf '\nRead [no heading](other.md#missing-heading).\n' >>"$PROJECT/README.md"

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "other.md#missing-heading"
  assert_output_contains "check-docs: lychee failed"

  add_anchor_pages
  printf '\nRead [no title](#missing-title).\n' >>"$PROJECT/README.md"

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "README.md#missing-title"
  assert_output_contains "check-docs: lychee failed"
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
    case_current_state_term_fails
    case_current_state_non_hits_pass
    case_history_term_does_not_fail
    case_current_state_is_off_for_decisions_and_specs
    case_local_anchors_are_checked
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
