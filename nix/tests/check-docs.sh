#!/usr/bin/env bash
# Tests for `nix/scripts/check-docs.sh` and for the wrapped tools of
# `nix/lib/docs.nix`.
#
# Usage: bash nix/tests/check-docs.sh
#
# The commands `check-docs`, `sync-config`, `vale`, `markdownlint-cli2` and
# `lychee` must be on PATH. They must be the packages that `nix/lib/docs.nix`
# and `nix/lib/config.nix` build, because they carry their own tools and the
# hub's base configuration: `vale` is the one that has the style `Sealambda`.
# The flake check `check-docs-tests` runs this file. The test cases of the
# style rules are in `vale/Sealambda/*.test.yml`, and the flake check
# `vale-style-tests` runs them.
#
# Each case generates a small project under a temporary directory. A bare
# project has no tool configuration file: it holds the rules of the hub alone.
# A legacy project gets the copies that `sync-config` writes, so the test needs
# no second list of config files. The bad documents exist only at run time:
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

# Set by `new_project` and `new_bare_project`: the project directory of the
# running case.
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

# Creates the legacy project directory $WORK/$1 and sets PROJECT to its path.
# The project has the copies of the tool configuration that `sync-config`
# writes, an empty `Repository` Vale vocabulary and a `README.md` that passes
# all three tools.
new_project() {
  PROJECT=$WORK/$1
  mkdir -p "$PROJECT/.vale/styles/config/vocabularies/Repository"
  (cd "$PROJECT" && sync-config)
  : >"$PROJECT/.vale/styles/config/vocabularies/Repository/accept.txt"
  printf '# Title\n\nThis page is short.\n' >"$PROJECT/README.md"
  rm -f "$OUT"
}

# Creates the bare project directory $WORK/$1 and sets PROJECT to its path. The
# project has a `README.md` that passes all three tools and no configuration
# file: the hub's base configuration is the only configuration.
new_bare_project() {
  PROJECT=$WORK/$1
  mkdir -p "$PROJECT"
  printf '# Title\n\nThis page is short.\n' >"$PROJECT/README.md"
  rm -f "$OUT"
}

# Writes the text $2 into the file $1 of the project, a path relative to the
# project. The function creates the parent directories.
write_file() {
  mkdir -p "$(dirname -- "$PROJECT/$1")"
  printf '%s\n' "$2" >"$PROJECT/$1"
}

# Runs `check-docs` with the arguments $1 and later. Sets STATUS to its exit
# status and writes its stdout and stderr to OUT.
run_check() {
  STATUS=0
  check-docs "$@" >"$OUT" 2>&1 || STATUS=$?
}

# Runs `check-docs` like `run_check`, with one more environment variable. The
# argument $1 is the assignment `NAME=value`, and the later arguments go to
# `check-docs`.
run_check_with_env() {
  local assignment=$1
  shift
  STATUS=0
  env "$assignment" check-docs "$@" >"$OUT" 2>&1 || STATUS=$?
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

# Writes one page for each kind of finding that the hub's rules give: a
# markdownlint error, a broken link, a Vale error of a style of nixpkgs, an
# unknown term and a Vale error of the hub's own style `Sealambda`.
add_every_hub_finding() {
  add_markdownlint_error
  add_broken_link
  add_vale_error
  add_unknown_term
  write_page guide.md "The server currently runs NixOS."
}

# The rules of the style `Sealambda` that have the level warning. Each one has
# a finding in the page that `add_every_warning` writes.
readonly WARNING_RULES=(
  DefineAcronyms
  OneSpelling
  FillerWords
  HeadingCase
  HowToTitle
  SentenceLength
  ParagraphLength
  ListLength
  StepLength
)

# The page of `add_every_warning`, a path relative to the project. It is in
# `docs/how-to/`, because the hub's base turns HowToTitle and StepLength on only
# there.
readonly WARNINGS_PAGE=docs/how-to/warnings.md

# Writes the page WARNINGS_PAGE into the project. It has one finding for each
# rule in WARNING_RULES and no finding of the level error:
# - the title `Using the hub` starts with a gerund (HowToTitle);
# - the heading `Title Case Heading` is not in sentence case (HeadingCase);
# - `SBOM` has no definition (DefineAcronyms), `e-mail` is the unused spelling
#   (OneSpelling) and `Just` is a filler word (FillerWords);
# - the first paragraph has 7 sentences (ParagraphLength) and the second one is
#   a sentence of 30 words (SentenceLength);
# - the bulleted list has 1 item (ListLength);
# - the first numbered step has 27 words (StepLength).
add_every_warning() {
  mkdir -p "$PROJECT/$(dirname -- "$WARNINGS_PAGE")"
  cat >"$PROJECT/$WARNINGS_PAGE" <<'EOF'
# Using the hub

## Title Case Heading

The SBOM lists every part. Just send an e-mail. Read the page. Read the page.
Read the page. Read the page. Read the page.

This sentence has many words in it so that a reader must keep the whole thing
in mind before the full stop arrives at the end of the line here.

- One item

1. Open the file and read each line of the long text that follows, then write
   down every word that you find in it before you go on.
2. Stop.
EOF
}

# Writes the output of the last run into the file $1, with the parts that
# differ between two projects replaced: the path of the project, the time that
# lychee prints, and the order of the lines.
write_normalized_output() {
  sed -e "s|$PROJECT|PROJECT|g" -e 's/ (in [0-9.]*m\{0,1\}s)//' "$OUT" | sort >"$1"
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

# Runs `vale` without the level flag, as an editor does, on the files $1 and
# later, paths relative to the project. Sets STATUS to its exit status and
# writes its output to OUT, one finding per line.
run_vale_plain() {
  STATUS=0
  (cd "$PROJECT" && vale --output=line "$@") >"$OUT" 2>&1 || STATUS=$?
}

# Asserts, in the project that holds the page of `add_every_warning`, that the
# findings of level warning don't change the gate. The check passes and prints
# no finding of the style `Sealambda`. A Vale run without the level flag, which
# is what an editor runs, passes too and reports each rule of WARNING_RULES: the
# check passes because of the level, and not because a rule is missing.
assert_warnings_leave_the_gate_unchanged() {
  local rule

  run_check "$PROJECT"

  assert_status 0
  assert_output_lacks "Sealambda."

  run_vale_plain "$WARNINGS_PAGE"

  assert_status 0
  for rule in "${WARNING_RULES[@]}"; do
    assert_output_contains "Sealambda.$rule"
  done
}

# A page that breaks only rules of the level warning passes the check in a
# legacy project, and a plain Vale run reports every one of those rules. The
# hub's base file gives the rules their level, so a consumer that syncs the file
# sees no change of the gate when the hub adds a warning rule. Mutation: setting
# one of the rules to `error` in `vale/Sealambda` makes this case fail.
case_warning_rules_do_not_fail_a_legacy_project() {
  new_project warnings-legacy
  add_every_warning

  assert_warnings_leave_the_gate_unchanged
}

# The same page passes in a bare project, which has no configuration file: the
# wrapped tools carry the hub's base configuration and the style.
case_warning_rules_do_not_fail_a_bare_project() {
  new_bare_project warnings-bare
  add_every_warning

  assert_warnings_leave_the_gate_unchanged
}

# Writes the page $1, a path relative to the project, that has a finding of
# HowToTitle (the title `Using the hub`) and one of StepLength (a first step of
# 27 words) wherever the two rules are on. The list has two items, so
# ListLength has no finding. The long step is also a sentence of more than 25
# words, so SentenceLength has a finding on every page: it shows that Vale ran
# the style, and not only that two rules stayed silent.
write_how_to_findings_page() {
  mkdir -p "$(dirname -- "$PROJECT/$1")"
  cat >"$PROJECT/$1" <<'EOF'
# Using the hub

1. Open the file and read each line of the long text that follows, then write
   down every word that you find in it before you go on.
2. Stop.
EOF
}

# Asserts, in the project of the running case, that HowToTitle and StepLength
# are on for the pages of a `how-to` folder, also under another folder, and off
# for any other page. Each page runs alone, so a finding names its page.
assert_how_to_rules_follow_the_folder() {
  local page

  for page in docs/how-to/page.md services/api/docs/how-to/page.md; do
    write_how_to_findings_page "$page"
    run_vale_plain "$page"
    assert_status 0
    assert_output_contains "Sealambda.HowToTitle"
    assert_output_contains "Sealambda.StepLength"
  done

  for page in docs/reference/page.md docs/explanation/page.md page.md; do
    write_how_to_findings_page "$page"
    run_vale_plain "$page"
    assert_status 0
    assert_output_contains "Sealambda.SentenceLength"
    assert_output_lacks "Sealambda.HowToTitle"
    assert_output_lacks "Sealambda.StepLength"
  done
}

# The two rules that check how-to pages are on for a page in `docs/how-to/` and
# off for any other page, in a legacy project. The hub's base file has a
# section for the folder, so the two rules don't flag a reference page or an
# explanation page. Mutation: deleting the section `docs/how-to` from
# `config/vale.ini` makes this case fail.
case_how_to_rules_apply_only_in_how_to_pages_of_a_legacy_project() {
  new_project how-to-legacy

  assert_how_to_rules_follow_the_folder
}

# The same holds in a bare project, whose base comes from the wrapper.
case_how_to_rules_apply_only_in_how_to_pages_of_a_bare_project() {
  new_bare_project how-to-bare

  assert_how_to_rules_follow_the_folder
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

# A project with no configuration file passes when its pages are clean, and
# fails with the findings of every hub rule when they aren't. Only the Vale rule
# names prove that a tool loaded the hub's base: a Vale without the base lints no
# file, so a name of the styles of nixpkgs, of the hub's own style or of
# `Vale.Spelling` means that the base is in. The finding MD001 comes from a
# default of markdownlint, and the broken relative link is a default of lychee,
# so neither proves the base. The cases that read the options of the base prove
# it for those two tools: `case_inline_markdownlint_comments_follow_the_option`
# and `case_local_markdownlint_rule_replaces_the_options_of_the_base` for
# markdownlint-cli2, `case_hub_lychee_option_wins_over_a_local_one` for lychee.
# `case_hub_vocabulary_is_loaded` proves the hub's Vale vocabulary.
case_no_local_file_applies_the_hub_rules() {
  new_bare_project bare

  run_check "$PROJECT"
  assert_status 0
  assert_output_contains "==> markdownlint-cli2"
  assert_output_contains "==> lychee"
  assert_output_contains "==> vale"

  add_every_hub_finding

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "MD001"
  assert_output_contains "missing-page.md"
  assert_output_contains "Microsoft.Contractions"
  assert_output_contains "Vale.Spelling"
  assert_output_contains "Sealambda.CurrentState"
  assert_output_contains "check-docs: markdownlint-cli2 failed"
  assert_output_contains "check-docs: lychee failed"
  assert_output_contains "check-docs: vale failed"
}

# A bare project can use the terms of the hub's own vocabulary `Sealambda`,
# `treefmt` and `zizmor` here, with no vocabulary of its own. The three terms
# are entries of `config/vale-vocabulary.txt`: a case that fails on a missing
# term means that the file dropped it, and the case must name another entry.
# Vale's dictionary doesn't know the terms, so the page passes only when the
# base lists and loads the hub's vocabulary. The unknown term `zorblax` in a
# second page fails in the same project, and the output lacks two of the
# terms: the spelling rule is on, and the vocabulary is what lets the first page
# pass.
case_hub_vocabulary_is_loaded() {
  new_bare_project hub-vocabulary
  write_page terms.md "Run treefmt and zizmor for Sealambda."

  run_check "$PROJECT"
  assert_status 0

  add_unknown_term

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "Vale.Spelling"
  assert_output_contains "zorblax"
  assert_output_lacks "treefmt"
  assert_output_lacks "zizmor"
}

# A project that holds the copies that `sync-config` writes gets the findings
# of a bare project, line for line. The same pages run in both projects, and
# the output of each run is normalized. A copy that differs from the base of
# the hub, or a base that the wrapper layers in a way that changes a finding,
# shows as a difference.
case_legacy_copies_give_the_findings_of_a_bare_project() {
  new_bare_project same-bare
  add_every_hub_finding
  run_check "$PROJECT"
  assert_status 1
  write_normalized_output "$WORK/bare.out"

  new_project same-legacy
  add_every_hub_finding
  run_check "$PROJECT"
  assert_status 1
  write_normalized_output "$WORK/legacy.out"

  diff -u "$WORK/bare.out" "$WORK/legacy.out" >&2 ||
    fail "a legacy project reports other findings than a bare project"
}

# The project lists a term in its own `Repository` vocabulary. The term fails
# until the project's `.vale.ini` lists the vocabulary: the file with the terms
# alone changes nothing, and the `.vale.ini` makes Vale read it. A bare project
# needs no `Repository` vocabulary of the hub's making.
case_local_vale_vocabulary_is_accepted() {
  new_bare_project vale-vocabulary
  add_unknown_term
  write_file .vale/styles/config/vocabularies/Repository/accept.txt zorblax

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "Vale.Spelling"
  assert_output_contains "zorblax"

  write_file .vale.ini "StylesPath = .vale/styles
Vocab = Repository"

  run_check "$PROJECT"
  assert_status 0
}

# A `[glob]` section of the project's `.vale.ini` switches a rule off for one
# folder. The page in `docs/` passes, and the same text at the root still
# fails, so the section and not a global change decides.
case_local_vale_section_applies_to_its_folder() {
  new_bare_project vale-section
  write_page docs/guide.md "It does not work."

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "docs/guide.md"
  assert_output_contains "Microsoft.Contractions"

  write_file .vale.ini "[docs/**/*.md]
Microsoft.Contractions = NO"

  run_check "$PROJECT"
  assert_status 0

  add_vale_error

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "vale.md"
  assert_output_lacks "docs/guide.md"
}

# A project adds a Vale style of its own: the folder under its `StylesPath`
# and a `BasedOnStyles` entry for it. The rule fires next to the rules of the
# hub, which still apply.
case_local_vale_style_is_added() {
  new_bare_project vale-style
  write_page guide.md "The wobble is a word that this project forbids."
  write_file .vale/styles/Project/Wobble.yml "extends: existence
message: \"Don't use '%s'.\"
level: error
tokens:
  - wobble"
  write_file .vale.ini "StylesPath = .vale/styles

[*.md]
BasedOnStyles = Project"

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "Project.Wobble"

  add_vale_error

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "Microsoft.Contractions"
}

# A section for a folder that sets `BasedOnStyles` replaces the hub's list for
# that folder: Vale adds the entries only for a section with the same glob as
# the hub's `[*.md]`. The page in `docs/` gets the finding of the project's rule
# and none of the hub's rules, until the section repeats the hub's list. A page
# outside the folder keeps the hub's rules. The wrapped-tools page states this.
case_local_vale_style_in_a_folder_section_replaces_the_hub_styles() {
  new_bare_project vale-style-section
  write_page docs/guide.md "The wobble is a word that this project forbids. It does not work."
  write_file .vale/styles/Project/Wobble.yml "extends: existence
message: \"Don't use '%s'.\"
level: error
tokens:
  - wobble"
  write_file .vale.ini "StylesPath = .vale/styles

[docs/**/*.md]
BasedOnStyles = Project"

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "Project.Wobble"
  assert_output_lacks "Microsoft.Contractions"

  write_file .vale.ini "StylesPath = .vale/styles

[docs/**/*.md]
BasedOnStyles = Vale, Microsoft, Readability, Sealambda, Project"

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "Project.Wobble"
  assert_output_contains "Microsoft.Contractions"

  add_vale_error

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "vale.md"
  assert_output_contains "Microsoft.Contractions"
}

# The hub doesn't prevent a project from switching off a rule of the hub: a
# `[*.md]` section with `Sealambda.CurrentState = NO` makes the page pass. The
# wrapped-tools page states this, and the review of the file is the control.
case_local_vale_can_switch_a_hub_rule_off() {
  new_bare_project vale-off
  write_page guide.md "The server currently runs NixOS."

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "Sealambda.CurrentState"

  write_file .vale.ini "[*.md]
Sealambda.CurrentState = NO"

  run_check "$PROJECT"
  assert_status 0
}

# The wrapper unsets `VALE_CONFIG_PATH`. Vale reads the file that the variable
# names instead of the project's `.vale.ini`, so a set variable would drop the
# layer of the project and the base of the hub. The variable here names a file
# that switches a hub rule off: the error still fails the check. A project
# section that applies to `docs/` only still applies, and the same text at the
# root still fails, so the project's file is the one that Vale reads.
case_vale_config_path_variable_is_ignored() {
  new_bare_project vale-config-path
  add_vale_error
  printf '[*.md]\nMicrosoft.Contractions = NO\n' >"$WORK/outside.ini"

  run_check_with_env "VALE_CONFIG_PATH=$WORK/outside.ini" "$PROJECT"
  assert_status 1
  assert_output_contains "Microsoft.Contractions"

  write_page docs/guide.md "It does not work."
  write_file .vale.ini "[docs/**/*.md]
Microsoft.Contractions = NO"

  run_check_with_env "VALE_CONFIG_PATH=$WORK/outside.ini" "$PROJECT"
  assert_status 1
  assert_output_contains "vale.md"
  assert_output_lacks "docs/guide.md"
}

# A `MinAlertLevel` in the project's `.vale.ini` doesn't lower the alert level
# of the check, which the flag `--minAlertLevel=error` sets. The setting is
# `suggestion`, the lowest level. A Vale run without the flag reads the file and
# prints the suggestion `Sealambda.History`, and the check prints nothing and
# passes. The wrapped-tools page states this limit.
case_vale_min_alert_level_cannot_lower_the_check_level() {
  new_bare_project vale-level
  write_page guide.md "The service previously ran on Fly."
  write_file .vale.ini "MinAlertLevel = suggestion"

  STATUS=0
  (cd "$PROJECT" && vale --output=line guide.md) >"$OUT" 2>&1 || STATUS=$?
  assert_status 0
  assert_output_contains "Sealambda.History:'previously' may describe history"

  run_check "$PROJECT"
  assert_status 0
  assert_output_lacks "Sealambda.History"
}

# A `.vale.ini` in a folder above the project applies when the project has no
# `.vale.ini` of its own, because Vale takes the nearest file upward from the
# working directory. The wrapper can't prevent this, and the wrapped-tools page
# states it. A `.vale.ini` in the project takes over from the file above it.
case_vale_reads_a_file_above_a_project_without_one() {
  new_bare_project vale-above/project
  add_vale_error
  write_file ../.vale.ini "[*.md]
Microsoft.Contractions = NO"

  run_check "$PROJECT"
  assert_status 0

  write_file .vale.ini "[docs/**/*.md]
Microsoft.Passive = NO"

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "Microsoft.Contractions"
}

# A `.vale.ini` in the home folder applies when the project and the folders
# above it have none, for the same reason. The wrapped-tools page states this.
# The project's own `.vale.ini` takes over from the file in the home folder.
case_vale_reads_a_home_file_when_no_project_file_exists() {
  new_bare_project vale-home
  add_vale_error
  mkdir -p "$WORK/home"
  printf '[*.md]\nMicrosoft.Contractions = NO\n' >"$WORK/home/.vale.ini"

  run_check_with_env "HOME=$WORK/home" "$PROJECT"
  assert_status 0

  write_file .vale.ini "[docs/**/*.md]
Microsoft.Passive = NO"

  run_check_with_env "HOME=$WORK/home" "$PROJECT"
  assert_status 1
  assert_output_contains "Microsoft.Contractions"
}

# markdownlint-cli2 and lychee read no configuration file from the home folder
# or from a folder above the project. A `.markdownlint-cli2.yaml`, a
# `lychee.toml` and a `.lycheeignore` that would make every page pass sit in
# both places, and the findings stay. The wrapped-tools page states this.
case_markdownlint_and_lychee_ignore_files_above_the_project() {
  new_bare_project others-above/project
  add_markdownlint_error
  add_broken_link
  mkdir -p "$WORK/home"
  local dir
  for dir in "$WORK/others-above" "$WORK/home"; do
    printf 'ignores: ["**"]\n' >"$dir/.markdownlint-cli2.yaml"
    printf 'exclude = [".*"]\n' >"$dir/lychee.toml"
    printf '.*\n' >"$dir/.lycheeignore"
  done

  run_check_with_env "HOME=$WORK/home" "$PROJECT"

  assert_status 1
  assert_output_contains "MD001"
  assert_output_contains "missing-page.md"
}

# The hub doesn't prevent a project from switching a whole gate off. The page
# `lint.md` has a markdownlint error, and each file below makes the tool lint
# nothing or turn every rule off. The wrapped-tools page lists these settings
# and names the review of the file as the control.
case_a_local_file_can_switch_the_markdownlint_gate_off() {
  new_bare_project markdownlint-gate
  add_markdownlint_error

  run_check "$PROJECT"
  assert_status 1

  write_file .markdownlint-cli2.yaml 'ignores: ["**"]'
  run_check "$PROJECT"
  assert_status 0

  write_file .markdownlint-cli2.yaml "config:
  default: false"
  run_check "$PROJECT"
  assert_status 0

  rm "$PROJECT/.markdownlint-cli2.yaml"
  write_file .markdownlint.yaml "default: false"
  run_check "$PROJECT"
  assert_status 0
}

# A Vale section switches the whole gate off in three ways: a block or token
# pattern that matches all text, or each style set to `NO`. The page has a
# contraction, an unknown term and a word of a plan, so each style of the hub
# has a finding to hide.
case_a_local_file_can_switch_the_vale_gate_off() {
  new_bare_project vale-gate
  add_every_hub_finding
  rm "$PROJECT/lint.md" "$PROJECT/link.md"

  run_check "$PROJECT"
  assert_status 1

  write_file .vale.ini "[*.md]
BlockIgnores = (?s).*"
  run_check "$PROJECT"
  assert_status 0

  write_file .vale.ini "[*.md]
TokenIgnores = .+"
  run_check "$PROJECT"
  assert_status 0

  write_file .vale.ini "[*.md]
Vale = NO
Microsoft = NO
Readability = NO
Sealambda = NO"
  run_check "$PROJECT"
  assert_status 0
}

# A project's `lychee.toml` with an exclusion that matches every link makes
# lychee check no link. The hub's file adds to the list and doesn't remove it.
case_a_local_file_can_switch_the_lychee_gate_off() {
  new_bare_project lychee-gate
  add_broken_link

  run_check "$PROJECT"
  assert_status 1

  write_file lychee.toml 'exclude = [".*"]'
  run_check "$PROJECT"
  assert_status 0
}

# A root `.markdownlint-cli2.yaml` adds to the base of the hub. The rule that
# the file switches off passes, and the other rules of the base still fail.
case_local_markdownlint_file_adds_to_the_base() {
  new_bare_project markdownlint-root
  add_markdownlint_error

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "MD001"

  write_file .markdownlint-cli2.yaml "config:
  MD001: false"

  run_check "$PROJECT"
  assert_status 0

  write_file two-titles.md "# One

# Two"

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "MD025"
  assert_output_lacks "MD001"
}

# A rule that a local file lists replaces the options of the base for that
# rule. The base switches the line length off for tables. A file that only sets
# the line length of MD013 loses that option, so a long table row fails. The
# same row passes with no file, which proves that the file and not the row
# changes the result.
case_local_markdownlint_rule_replaces_the_options_of_the_base() {
  new_bare_project markdownlint-replace
  local words
  words=$(printf 'red blue %.0s' {1..14})
  write_file table.md "# Table

| Column | Text |
| --- | --- |
| row | $words|"

  run_check "$PROJECT"
  assert_status 0

  write_file .markdownlint-cli2.yaml "config:
  MD013:
    line_length: 100"

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "MD013"
  assert_output_contains "table.md"
}

# A project with no root file can still add a nested `.markdownlint-cli2.yaml`.
# The file applies to its own directory, and the base of the hub applies to the
# rest.
case_nested_markdownlint_file_needs_no_root_file() {
  new_bare_project markdownlint-nested
  add_markdownlint_error docs
  write_file docs/.markdownlint-cli2.yaml "config:
  MD001: false"

  run_check "$PROJECT"
  assert_status 0

  add_markdownlint_error

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "MD001"
  assert_output_lacks "docs/lint.md"
}

# A file named `.markdownlint.yaml`, without `cli2`, replaces the whole `config`
# map of the base for its directory, so the hub's table setting doesn't apply
# there. The same long table row passes in a directory with no such file. The
# wrapped-tools page states this limit.
case_markdownlint_file_without_cli2_replaces_the_base() {
  new_bare_project markdownlint-plain
  local words row
  words=$(printf 'red blue %.0s' {1..14})
  row="| row | $words|"
  write_file wide/table.md "# Table

| Column | Text |
| --- | --- |
$row"
  write_file plain/table.md "# Table

| Column | Text |
| --- | --- |
$row"
  write_file plain/.markdownlint.yaml "MD001: false"

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "plain/table.md"
  assert_output_contains "MD013"
  assert_output_lacks "wide/table.md"
}

# The base of the hub turns inline comments off, so a page can't switch a rule
# off for itself. A local file can set the option again: a file value
# overrides a value of the base in markdownlint-cli2. The wrapped-tools page
# states this limit.
case_inline_markdownlint_comments_follow_the_option() {
  new_bare_project markdownlint-inline
  write_file inline.md "# Title

<!-- markdownlint-disable MD001 -->

### Skipped level"

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "MD001"

  write_file .markdownlint-cli2.yaml "noInlineConfig: false"

  run_check "$PROJECT"
  assert_status 0
}

# The exclusions of a project's `lychee.toml` add to the exclusions of the hub.
# The broken link in `drafts/` fails until the file excludes the folder. The
# folder `node_modules`, which the hub's file excludes, stays excluded in the
# same run, so the lists are joined and not replaced.
case_local_lychee_exclusions_add_to_the_hub_exclusions() {
  new_bare_project lychee-exclude
  write_page drafts/note.md "Read [the missing page](missing-page.md)."
  write_page node_modules/pkg/README.md "Read [the missing page](missing-page.md)."

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "drafts/note.md"
  assert_output_lacks "node_modules"

  write_file lychee.toml 'exclude_path = ["drafts"]'

  run_check "$PROJECT"
  assert_status 0
}

# A `.lycheeignore` file in the project excludes the links that match one of
# its lines, a regular expression for each line.
case_lycheeignore_is_read() {
  new_bare_project lychee-ignore
  add_broken_link

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "missing-page.md"

  write_file .lycheeignore "missing-page"

  run_check "$PROJECT"
  assert_status 0
}

# A single option of the hub's `lychee.toml` wins over the same option of the
# project's file. The project asks for no fragment check, and the link to a
# missing anchor still fails, because the hub's `include_fragments` is read
# last.
case_hub_lychee_option_wins_over_a_local_one() {
  new_bare_project lychee-scalar
  add_anchor_pages
  printf '\nRead [no heading](other.md#missing-heading).\n' >>"$PROJECT/README.md"
  write_file lychee.toml 'include_fragments = "none"'

  run_check "$PROJECT"
  assert_status 1
  assert_output_contains "other.md#missing-heading"
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
    case_warning_rules_do_not_fail_a_legacy_project
    case_warning_rules_do_not_fail_a_bare_project
    case_how_to_rules_apply_only_in_how_to_pages_of_a_legacy_project
    case_how_to_rules_apply_only_in_how_to_pages_of_a_bare_project
    case_current_state_is_off_for_decisions_and_specs
    case_local_anchors_are_checked
    case_no_local_file_applies_the_hub_rules
    case_hub_vocabulary_is_loaded
    case_legacy_copies_give_the_findings_of_a_bare_project
    case_local_vale_vocabulary_is_accepted
    case_local_vale_section_applies_to_its_folder
    case_local_vale_style_is_added
    case_local_vale_style_in_a_folder_section_replaces_the_hub_styles
    case_local_vale_can_switch_a_hub_rule_off
    case_vale_config_path_variable_is_ignored
    case_vale_min_alert_level_cannot_lower_the_check_level
    case_vale_reads_a_file_above_a_project_without_one
    case_vale_reads_a_home_file_when_no_project_file_exists
    case_markdownlint_and_lychee_ignore_files_above_the_project
    case_a_local_file_can_switch_the_markdownlint_gate_off
    case_a_local_file_can_switch_the_vale_gate_off
    case_a_local_file_can_switch_the_lychee_gate_off
    case_local_markdownlint_file_adds_to_the_base
    case_local_markdownlint_rule_replaces_the_options_of_the_base
    case_nested_markdownlint_file_needs_no_root_file
    case_markdownlint_file_without_cli2_replaces_the_base
    case_inline_markdownlint_comments_follow_the_option
    case_local_lychee_exclusions_add_to_the_hub_exclusions
    case_lycheeignore_is_read
    case_hub_lychee_option_wins_over_a_local_one
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
