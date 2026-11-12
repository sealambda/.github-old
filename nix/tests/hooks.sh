#!/usr/bin/env bash
# Tests for the Git hooks that `nix/lib/hooks.nix` builds: the `commit-msg`,
# `pre-commit` and `pre-push` stages of the hub's own configuration, run by
# real Git against temporary repositories.
#
# Usage: HOOKS_INSTALL=<file> bash nix/tests/hooks.sh [case_name ...]
#
# With case names, the file runs only those cases.
#
# HOOKS_INSTALL is the installation script of `lib.mkHooks` as a file: the
# script that the dev shell runs when a person enters it. Each case runs it in
# a new repository, so the cases test the hooks that a person gets, not a
# configuration that the test wrote itself. `git` and `prek` must be on PATH.
# The script calls `nix-store` to add a garbage-collector root for the
# configuration. The sandbox has no `nix-store`, so the tests put a stand-in on
# PATH that links the configuration, which is all the root does for a hook.
#
# The flake check `pre-commit` runs the `pre-commit` stage on the source of the
# hub, but the scratch repository of that check never runs the `commit-msg` and
# `pre-push` stages. These cases cover those two stages and the refusals of
# the `pre-commit` stage, one refusal for each hook, so a hook that stops
# running fails a case.
#
# Some cases pin behavior of prek and of the installation script that the
# reference page on the Git hooks states: what the hooks read when a file is
# staged in part, which pushes run `pre-push`, what the installer does to an
# earlier `core.hooksPath`, and what it does in linked work trees. An update of
# the inputs that changes one of them fails a case. Then update the page.
#
# Each case builds a Git repository under a temporary directory. The secret
# that the cases stage has the shape of a GitHub token, and the file assembles
# it from parts when it runs, as `nix/tests/secrets-scan.sh` does. No file of
# the hub holds the whole string, so the hub's scan of its history and the
# `leaks` check never find it. The token isn't valid for any account. The cases
# use no network: the remote of a push is a bare repository in the same
# directory.
#
# Git reads no configuration file of the user: a setting such as commit
# signing can't change a case. A failing case prints its name and the output of
# the last Git command, then stops the run with exit status 1.

set -euo pipefail

readonly INSTALL=${HOOKS_INSTALL:?set it to the installation script of mkHooks}

export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME=Test
export GIT_AUTHOR_EMAIL=test@example.test
export GIT_COMMITTER_NAME=Test
export GIT_COMMITTER_EMAIL=test@example.test
# A person's skip list must not switch off a hook of the cases.
unset SKIP

WORK=$(mktemp -d)
readonly WORK
trap 'rm -rf -- "$WORK"' EXIT

readonly OUT=$WORK/output

# A directory with the stand-in for `nix-store`.
readonly STAND_IN=$WORK/bin

# Set by `new_repository`: the work tree of the running case.
REPO=
# Set by `run_git`: the exit status of the last Git command.
STATUS=0

# --- Helpers ---------------------------------------------------------------

# Prints the secret of the cases: a GitHub-token-shaped string that the
# function assembles from parts.
secret() {
  printf '%s%s%s%s%s' gh p_ 7Kq2Zx9LmN4v B8tRw3YhD5sF g1JcUo6EaP0i
}

# Prints the failure message $1 with the name of the running case, then the
# output of the last Git command, and exits 1.
fail() {
  echo "FAIL: ${CURRENT_CASE:-setup}: $1" >&2
  if [ -f "$OUT" ]; then
    echo "--- output of the last command:" >&2
    cat "$OUT" >&2
  fi
  exit 1
}

# Fails unless the last Git command exited with status 0.
assert_accepted() {
  [ "$STATUS" = 0 ] || fail "expected the hooks to accept it, got status $STATUS"
}

# Fails unless the last Git command exited with a status other than 0.
assert_refused() {
  [ "$STATUS" != 0 ] || fail "expected the hooks to refuse it, got status 0"
}

# Fails unless the output of the last Git command contains the text $1.
assert_output_contains() {
  grep -qF -- "$1" "$OUT" || fail "the output lacks '$1'"
}

# Fails if the output of the last Git command contains the text $1.
assert_output_lacks() {
  ! grep -qF -- "$1" "$OUT" || fail "the output has '$1'"
}

# Fails unless a line of the output of the last Git command matches the
# extended regular expression $1. The result line of a hook, such as
# `treefmt....Failed`, has a variable number of dots, so a case matches it.
assert_output_matches() {
  grep -qE -- "$1" "$OUT" || fail "no line of the output matches '$1'"
}

# Fails unless the text of the file $1 of REPO is exactly $2.
assert_file_text() {
  [ "$(cat "$REPO/$1")" = "$2" ] || fail "the file $1 doesn't hold the expected text"
}

# Fails unless the staged text of the file $1 of REPO is exactly $2.
assert_staged_text() {
  [ "$(git -C "$REPO" show ":$1")" = "$2" ] || fail "the staged text of $1 isn't the expected text"
}

# Fails unless REPO holds $1 commits on its checked-out branch.
assert_commit_count() {
  local count
  count=$(git -C "$REPO" rev-list --count HEAD)
  [ "$count" = "$1" ] || fail "expected $1 commits, found $count"
}

# Writes the stand-in `nix-store`. The installation script calls
# `nix-store --add-root LINK --indirect --realise TARGET`, and the stand-in
# makes the link and nothing else.
write_nix_store_stand_in() {
  mkdir -p "$STAND_IN"
  cat >"$STAND_IN/nix-store" <<'EOF'
#!/bin/sh
ln -s "$5" "$2"
EOF
  chmod +x "$STAND_IN/nix-store"
}

# Creates the repository $WORK/$1 with one commit that holds the files that
# the formatter and the documentation check need, and sets REPO to its path.
# The repository is the working directory afterwards. No hook exists yet, so
# the first commit runs none.
init_repository() {
  REPO=$WORK/$1
  mkdir -p "$REPO"
  cd "$REPO"
  git init --quiet --initial-branch=main .
  printf '{ }\n' >flake.nix
  printf '# Title\n\nThis page is short.\n' >README.md
  git add flake.nix README.md
  git commit --quiet --message "chore: add the first files"
  rm -f "$OUT"
}

# Runs the installation script in the directory $1, as a person does when they
# enter the dev shell. Sets STATUS to its exit status and writes its stdout and
# stderr to OUT. Never fails: the cases that expect a refusal call it directly.
try_install_in() {
  STATUS=0
  (cd "$1" && PATH="$STAND_IN:$PATH" bash "$INSTALL") >"$OUT" 2>&1 || STATUS=$?
}

# Runs the installation script in REPO. Fails when the script fails.
install_hooks() {
  try_install_in "$REPO"
  [ "$STATUS" = 0 ] || fail "the installation script failed"
}

# Creates a repository with the hooks installed.
new_repository() {
  init_repository "$1"
  install_hooks
}

# Runs `git` with the arguments $1 and later in REPO. Sets STATUS to its exit
# status and writes its stdout and stderr to OUT. Fails when the output holds
# the secret, whatever the status is: a hook must never print it.
run_git() {
  STATUS=0
  (cd "$REPO" && git "$@") >"$OUT" 2>&1 || STATUS=$?
  assert_output_lacks "$(secret)"
}

# Writes the text $2 into the file $1 of REPO and stages it.
stage_file() {
  printf '%s\n' "$2" >"$REPO/$1"
  git -C "$REPO" add -- "$1"
}

# Stages a file that holds the secret, in the shape `ref: <secret>`. The key
# `ref` is no word that a generic rule looks for, so only the rule of the token
# shape matches.
stage_secret() {
  stage_file notes.txt "ref: $(secret)"
}

# --- Cases -----------------------------------------------------------------

# The installation script makes the three hooks and the configuration link,
# and it points Git at the hooks directory.
case_install_writes_the_three_hooks() {
  new_repository install

  local hook
  for hook in pre-commit commit-msg pre-push; do
    [ -x "$REPO/.git/hooks/$hook" ] || fail "the hook $hook isn't installed"
  done
  [ -L "$REPO/.pre-commit-config.yaml" ] || fail "the configuration isn't linked"
  [ "$(git -C "$REPO" config --local core.hooksPath)" = ".git/hooks" ] ||
    fail "core.hooksPath doesn't name the hooks directory"
}

# A hook that another tool wrote isn't deleted. The installer moves it to
# `<name>.legacy`, and `prek` runs it after its own hooks.
case_install_keeps_a_foreign_hook() {
  init_repository foreign
  printf '#!/bin/sh\ntouch "%s/foreign-ran"\n' "$WORK" >"$REPO/.git/hooks/pre-commit"
  chmod +x "$REPO/.git/hooks/pre-commit"
  install_hooks
  [ -x "$REPO/.git/hooks/pre-commit.legacy" ] || fail "the foreign hook was lost"

  stage_file notes.txt "plain text"
  run_git commit --quiet --message "docs: add the notes"
  assert_accepted
  [ -f "$WORK/foreign-ran" ] || fail "the foreign hook didn't run"
}

# A foreign hook that exits with a status other than 0 stops the commit, and a
# refused commit leaves no commit behind: the installer keeps the old hook, and
# `prek` runs it and passes its status on.
case_failing_foreign_hook_stops_the_commit() {
  init_repository foreign-failing
  printf '#!/bin/sh\necho old-hook-failed\nexit 1\n' >"$REPO/.git/hooks/pre-commit"
  chmod +x "$REPO/.git/hooks/pre-commit"
  install_hooks

  stage_file notes.txt "plain text"
  run_git commit --quiet --message "docs: add the notes"
  assert_refused
  assert_output_contains "old-hook-failed"
  assert_commit_count 1
}

# The installer replaces the local `core.hooksPath` of the repository with the
# hooks folder of prek. The hooks of the old folder, such as a husky script,
# stop running, and the hooks of prek run in their place. The installer moves
# nothing out of the old folder.
case_install_replaces_an_earlier_core_hooks_path() {
  init_repository earlier-path
  mkdir "$REPO/.husky"
  printf '#!/bin/sh\ntouch "%s/husky-ran"\n' "$WORK" >"$REPO/.husky/pre-commit"
  chmod +x "$REPO/.husky/pre-commit"
  git -C "$REPO" config --local core.hooksPath .husky

  stage_file notes.txt "plain text"
  run_git commit --quiet --message "docs: add the notes"
  assert_accepted
  [ -f "$WORK/husky-ran" ] || fail "the old hook didn't run before the install"
  rm -f "$WORK/husky-ran"

  install_hooks
  [ "$(git -C "$REPO" config --local core.hooksPath)" = ".git/hooks" ] ||
    fail "core.hooksPath doesn't name the hooks directory of prek"
  [ -x "$REPO/.husky/pre-commit" ] || fail "the installer removed the old hook"

  stage_file other.txt "plain text"
  run_git commit --quiet --message "added some notes"
  assert_refused
  assert_output_contains "gitpolicy-commit-msg"
  run_git commit --quiet --message "docs: add other notes"
  assert_accepted
  [ ! -e "$WORK/husky-ran" ] || fail "the old hook ran after the install"
}

# Writes a global configuration file that sets `core.hooksPath` to a folder
# with a `pre-commit` hook that creates the file `$WORK/global-hook-ran`, and
# prints the path of the configuration file.
write_global_hooks_path_config() {
  local config=$WORK/global-config
  mkdir -p "$WORK/global-hooks"
  printf '#!/bin/sh\ntouch "%s/global-hook-ran"\n' "$WORK" >"$WORK/global-hooks/pre-commit"
  chmod +x "$WORK/global-hooks/pre-commit"
  printf '[core]\n\thooksPath = %s/global-hooks\n' "$WORK" >"$config"
  printf '%s\n' "$config"
}

# A `core.hooksPath` in the global configuration stops `prek` from installing
# hooks. The installer of git-hooks.nix would still set the local
# `core.hooksPath` to the empty hooks folder of the repository, which hides the
# global hooks and leaves no hook at all. The check that `lib.mkHooks` runs
# first refuses: the installation script exits with status 1, names the value
# and the repair, and changes nothing. The global hook keeps running. This case
# pins the behavior that the reference page on the Git hooks states.
case_global_core_hooks_path_makes_the_install_fail_and_changes_nothing() {
  init_repository global-path
  local global_config
  global_config=$(write_global_hooks_path_config)

  GIT_CONFIG_GLOBAL=$global_config try_install_in "$REPO"
  [ "$STATUS" = 1 ] || fail "expected status 1 from the installation script, got $STATUS"
  assert_output_contains "core.hooksPath comes from outside this repository"
  assert_output_contains "$(printf 'global\t%s' "$WORK/global-hooks")"
  assert_output_contains "The repository is unchanged"
  assert_output_lacks "Refusing to install hooks because"
  ! git -C "$REPO" config --local --get core.hooksPath >/dev/null ||
    fail "the installer set the local core.hooksPath"
  [ ! -e "$REPO/.git/hooks/pre-commit" ] || fail "the installer wrote a hook"
  [ ! -e "$REPO/.pre-commit-config.yaml" ] || fail "the installer linked the configuration"

  stage_file notes.txt "plain text"
  GIT_CONFIG_GLOBAL=$global_config run_git commit --quiet --message "added some notes"
  assert_accepted
  [ -f "$WORK/global-hook-ran" ] || fail "the global hook stopped running"
}

# The check refuses for every scope other than the local one, not only for the
# global one: a value in the system configuration, in the worktree
# configuration or on the command line (a `GIT_CONFIG_COUNT` variable) stops
# prek or wins over the value that the installer would write.
case_core_hooks_path_of_another_scope_makes_the_install_fail() {
  init_repository other-scope
  local system_config=$WORK/system-config
  printf '[core]\n\thooksPath = %s/system-hooks\n' "$WORK" >"$system_config"

  GIT_CONFIG_NOSYSTEM=0 GIT_CONFIG_SYSTEM=$system_config try_install_in "$REPO"
  [ "$STATUS" = 1 ] || fail "system scope: expected status 1, got $STATUS"
  assert_output_contains "$(printf 'system\t%s' "$WORK/system-hooks")"

  GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=$WORK/command-hooks \
    try_install_in "$REPO"
  [ "$STATUS" = 1 ] || fail "command scope: expected status 1, got $STATUS"
  assert_output_contains "$(printf 'command\t%s' "$WORK/command-hooks")"

  git -C "$REPO" config --local extensions.worktreeConfig true
  git -C "$REPO" config --worktree core.hooksPath "$WORK/worktree-hooks"
  try_install_in "$REPO"
  [ "$STATUS" = 1 ] || fail "worktree scope: expected status 1, got $STATUS"
  assert_output_contains "$(printf 'worktree\t%s' "$WORK/worktree-hooks")"

  ! git -C "$REPO" config --local --get core.hooksPath >/dev/null ||
    fail "the installer set the local core.hooksPath"
  [ ! -e "$REPO/.pre-commit-config.yaml" ] || fail "the installer linked the configuration"
}

# The check reads Git's own answer, so it asks nothing of a directory that is
# no work tree: there the installer prints its warning and the script succeeds.
# A global `core.hooksPath` must not turn that into a failure.
case_global_core_hooks_path_outside_a_work_tree_is_no_failure() {
  local global_config
  global_config=$(write_global_hooks_path_config)
  mkdir "$WORK/no-work-tree"

  GIT_CONFIG_GLOBAL=$global_config try_install_in "$WORK/no-work-tree"
  [ "$STATUS" = 0 ] || fail "expected status 0 outside a work tree, got $STATUS"
  assert_output_lacks "comes from outside"
}

# Fails unless the installation script, run in the directory $1 of a repository
# with no work tree, exits with status 0, prints the one line that says so, and
# leaves the repository as it was: no `core.hooksPath`, no hook, and no output
# line of the installer. The installer of git-hooks.nix runs `git rev-parse
# --show-toplevel` there, gets nothing, links the configuration at
# `/.pre-commit-config.yaml` and writes a `core.hooksPath` without a work tree.
assert_install_skipped_in() {
  try_install_in "$1"
  [ "$STATUS" = 0 ] || fail "expected status 0 in $1, got $STATUS"
  assert_output_contains "this directory is in a repository but not in a work tree"
  assert_output_lacks "git-hooks.nix: updating"
  ! git -C "$1" config --local --get core.hooksPath >/dev/null ||
    fail "the installer set core.hooksPath in $1"
  [ ! -e "$1/hooks/pre-commit" ] || fail "the installer wrote a hook in $1"
}

# A bare repository and the `.git` folder of a work tree are inside a Git
# repository but not inside a work tree. The installer of git-hooks.nix goes on
# there and writes a malformed `core.hooksPath`, so the check that `lib.mkHooks`
# runs first skips the installation, also when a global `core.hooksPath` exists:
# nothing can be installed, so nothing is refused.
case_install_skips_a_repository_without_a_work_tree() {
  git init --quiet --bare "$WORK/bare.git"
  assert_install_skipped_in "$WORK/bare.git"

  init_repository git-folder
  assert_install_skipped_in "$REPO/.git"
  [ ! -e "$REPO/.pre-commit-config.yaml" ] || fail "the installer linked the configuration"

  local global_config
  global_config=$(write_global_hooks_path_config)
  GIT_CONFIG_GLOBAL=$global_config assert_install_skipped_in "$WORK/bare.git"
  assert_output_lacks "comes from outside"
}

# Git runs no hook under an empty `core.hooksPath`, and prek refuses to install
# under it, so the check refuses as it does for a path. It shows the empty
# value as `(empty)`, and not as a blank. This case pins the Git behavior too:
# the hook in `.git/hooks` doesn't run.
case_empty_global_core_hooks_path_is_refused_and_shown() {
  init_repository empty-path
  local config=$WORK/empty-config
  printf '[core]\n\thooksPath =\n' >"$config"
  printf '#!/bin/sh\ntouch "%s/empty-path-hook-ran"\n' "$WORK" >"$REPO/.git/hooks/pre-commit"
  chmod +x "$REPO/.git/hooks/pre-commit"

  GIT_CONFIG_GLOBAL=$config try_install_in "$REPO"
  [ "$STATUS" = 1 ] || fail "expected status 1 from the installation script, got $STATUS"
  assert_output_contains "$(printf 'global\t(empty)')"
  ! git -C "$REPO" config --local --get core.hooksPath >/dev/null ||
    fail "the installer set the local core.hooksPath"

  stage_file notes.txt "plain text"
  GIT_CONFIG_GLOBAL=$config run_git commit --quiet --message "docs: add the notes"
  assert_accepted
  [ ! -e "$WORK/empty-path-hook-ran" ] || fail "Git ran a hook under an empty core.hooksPath"
}

# The installer in the main checkout sets `core.hooksPath` to the relative path
# `.git/hooks`. Git resolves that path from the root of each work tree, and a
# linked work tree has a `.git` file, not a directory. So no hook runs in a
# linked work tree that never ran the installer, and a bad message passes. This
# case pins the limit that the reference page on the Git hooks states. A
# change of git-hooks.nix that removes it makes the case fail: then update the
# page.
case_linked_worktree_runs_no_hook_before_its_install() {
  new_repository relative
  git -C "$REPO" worktree add --quiet -b feat/linked "$WORK/relative-linked"

  REPO=$WORK/relative-linked
  stage_file notes.txt "plain text"
  run_git commit --quiet --message "added some notes"
  assert_accepted
  assert_output_lacks "gitpolicy-commit-msg"
}

# The installer links the configuration in the work tree that runs it, and it
# writes `core.hooksPath` and the hooks into the Git directory that all work
# trees share. After an install in a linked work tree, `core.hooksPath` is the
# absolute path of the shared directory, so each work tree runs the hooks, and
# a work tree that never ran the installer has no configuration: `prek` refuses
# every commit there. Removing a linked work tree breaks no other work tree.
case_linked_worktree_install_is_per_worktree() {
  new_repository shared
  local main=$REPO
  git -C "$main" worktree add --quiet -b feat/linked "$WORK/linked-tree"
  git -C "$main" worktree add --quiet -b feat/other "$WORK/other-tree"

  REPO=$WORK/linked-tree
  install_hooks
  [ "$(git -C "$main" config --local core.hooksPath)" = "$(cd "$main" && pwd -P)/.git/hooks" ] ||
    fail "core.hooksPath doesn't name the shared hooks directory"
  stage_file notes.txt "plain text"
  run_git commit --quiet --message "docs: add the notes"
  assert_accepted

  REPO=$WORK/other-tree
  stage_file notes.txt "plain text"
  run_git commit --quiet --message "docs: add the notes"
  assert_refused
  assert_output_contains "config file not found"

  git -C "$main" worktree remove --force "$WORK/linked-tree"
  REPO=$main
  stage_file other.txt "plain text"
  run_git commit --quiet --message "docs: add other notes"
  assert_accepted
}

# A commit with a conforming message and clean files passes every hook.
case_clean_commit_is_accepted() {
  new_repository clean

  stage_file notes.txt "plain text"
  stage_file README.md "$(printf '# Title\n\nThis page is still short.')"
  run_git commit --quiet --message "docs: add the notes"
  assert_accepted
  assert_commit_count 2
}

# A message that isn't a Conventional Commit stops the commit at `commit-msg`.
# The refused commit leaves no commit behind.
case_bad_message_is_refused() {
  new_repository message

  stage_file notes.txt "plain text"
  run_git commit --quiet --message "added some notes"
  assert_refused
  assert_output_contains "gitpolicy-commit-msg"
  assert_output_contains "Failed"
  assert_commit_count 1
}

# `git commit --fixup` makes a header that no Conventional Commit has. The hook
# lets it pass, because a rebase folds it. The CI check of the range doesn't.
case_fixup_commit_is_accepted() {
  new_repository fixup

  stage_file notes.txt "plain text"
  run_git commit --quiet --fixup HEAD
  assert_accepted
  assert_commit_count 2
}

# A staged secret stops the commit at `pre-commit`. The output names the hook
# and the rule, and it holds no secret: `run_git` checks that on every run.
case_staged_secret_is_refused() {
  new_repository secret

  stage_secret
  run_git commit --quiet --message "docs: add the notes"
  assert_refused
  assert_output_contains "secrets-scan"
  assert_output_contains "github-pat"
  assert_commit_count 1
}

# A badly formatted staged file stops the commit at `treefmt`. The hook formats
# the file in the work tree and fails, and it leaves the index alone, so the
# person stages the file again. The second commit passes. Without the hook the
# first commit would pass.
case_unformatted_file_is_formatted_and_refused() {
  new_repository format

  stage_file module.nix '{a=1;}'
  run_git commit --quiet --message "feat: add the module"
  assert_refused
  assert_output_matches 'treefmt\.+Failed'
  assert_commit_count 1
  assert_file_text module.nix '{ a = 1; }'
  assert_staged_text module.nix '{a=1;}'

  git -C "$REPO" add -- module.nix
  run_git commit --quiet --message "feat: add the module"
  assert_accepted
  assert_commit_count 2
}

# `prek` can't apply the formatting on top of an unstaged edit of the same
# file. It reverts the formatting and restores the edit, so the commit fails
# and the work tree and the index keep the text that they had. The person runs
# the formatter and stages the file.
case_formatting_is_reverted_when_the_file_has_an_unstaged_edit() {
  new_repository format-conflict

  stage_file module.nix $'{a=1;\nb=2;}'
  printf '%s\n' $'{a=1;\nb=3;}' >"$REPO/module.nix"
  run_git commit --quiet --message "feat: add the module"
  assert_refused
  assert_output_matches 'treefmt\.+Failed'
  assert_output_contains "Reverting the hook changes"
  assert_file_text module.nix $'{a=1;\nb=3;}'
  assert_staged_text module.nix $'{a=1;\nb=2;}'
  assert_commit_count 1
}

# A Markdown file with a rule violation stops the commit at `docs`. The output
# names the rule. Without the hook the commit would pass.
case_markdown_violation_is_refused() {
  new_repository markdown

  stage_file README.md $'# Title\n\n### Section\n\nText.'
  run_git commit --quiet --message "docs: edit the page"
  assert_refused
  assert_output_matches 'docs\.+Failed'
  assert_output_contains "MD001"
  assert_commit_count 1
}

# `docs` checks the whole work tree, so a Markdown file that is untracked and
# not ignored fails a commit that stages another Markdown file.
case_markdown_check_reads_untracked_files() {
  new_repository untracked
  printf '# Title\n\n### Section\n\nText.\n' >"$REPO/draft.md"

  stage_file README.md $'# Title\n\n## Section\n\nText.'
  run_git commit --quiet --message "docs: edit the page"
  assert_refused
  assert_output_contains "draft.md"
  assert_commit_count 1
}

# A staged workflow without `timeout-minutes` stops the commit at `workflows`.
# The workflow passes the formatter, which also runs the workflow linters, so
# the hook `workflows` is the one that refuses it. Without the hook the commit
# would pass.
case_workflow_without_a_time_limit_is_refused() {
  new_repository workflow

  mkdir -p "$REPO/.github/workflows"
  stage_file .github/workflows/check.yml "$(
    cat <<'EOF'
name: check
on: push
permissions: {}
concurrency:
  group: check-${{ github.ref }}
  cancel-in-progress: true
jobs:
  check:
    name: check
    runs-on: ubuntu-latest
    steps:
      - run: echo hello
EOF
  )"
  run_git commit --quiet --message "ci: add the check"
  assert_refused
  assert_output_matches 'treefmt\.+Passed'
  assert_output_matches 'workflows\.+Failed'
  assert_output_contains "timeout-minutes"
  assert_commit_count 1
}

# The hooks read the staged text of a file, whatever the work tree holds. A
# violation that only an unstaged edit has doesn't stop the commit, and a
# violation that only the staged text has does. `prek` saves the unstaged edit
# before the hooks run and restores it afterwards, in both cases, so the work
# tree keeps the edit, and `git stash` holds nothing.
case_hooks_read_the_staged_text() {
  new_repository staged-text
  local clean=$'# Title\n\n## Section\n\nText.'
  local broken=$'# Title\n\n### Section\n\nText.'

  stage_file README.md "$clean"
  printf '%s\n' "$broken" >"$REPO/README.md"
  run_git commit --quiet --message "docs: edit the page"
  assert_accepted
  assert_file_text README.md "$broken"

  git -C "$REPO" add -- README.md
  printf '%s\n' "$clean" >"$REPO/README.md"
  run_git commit --quiet --message "docs: edit the page again"
  assert_refused
  assert_output_matches 'docs\.+Failed'
  assert_file_text README.md "$clean"
  assert_staged_text README.md "$broken"
  [ -z "$(git -C "$REPO" stash list)" ] || fail "prek used git stash"
}

# A commit that only deletes a file selects no file for any hook, and `prek`
# skips a hook that has no file to check. `secrets-scan` still runs, because
# its hook has `always_run`: the scanner decides what a deletion or a rename
# holds. Without `always_run` the hook is skipped.
case_secrets_scan_runs_on_a_commit_without_files() {
  new_repository deletion
  stage_file notes.txt "plain text"
  run_git commit --quiet --message "docs: add the notes"
  assert_accepted

  git -C "$REPO" rm --quiet -- notes.txt
  run_git commit --quiet --message "docs: remove the notes"
  assert_accepted
  assert_output_matches 'treefmt\.+\(no files to check\)Skipped'
  assert_output_matches 'secrets-scan\.+Passed'
}

# `SKIP` names one hook to leave out, and the other hooks still run: the secret
# commits when `secrets-scan` is skipped, and a bad message still stops the
# commit.
case_skip_leaves_out_one_hook() {
  new_repository skip

  stage_secret
  SKIP=secrets-scan run_git commit --quiet --message "docs: add the notes"
  assert_accepted
  assert_commit_count 2

  stage_file other.txt "plain text"
  SKIP=secrets-scan run_git commit --quiet --message "added some notes"
  assert_refused
  assert_commit_count 2
}

# A push from a branch whose name breaks the rule stops at `pre-push`, and a
# push from a branch with a good name goes through.
case_bad_branch_name_is_refused_at_push() {
  new_repository branch
  git init --quiet --bare "$WORK/remote.git"
  git -C "$REPO" remote add origin "$WORK/remote.git"

  git -C "$REPO" switch --quiet --create Bad_Name
  run_git push origin Bad_Name
  assert_refused
  assert_output_contains "gitpolicy-branch"
  git -C "$WORK/remote.git" rev-parse --verify --quiet refs/heads/Bad_Name &&
    fail "the refused push reached the remote"

  git -C "$REPO" switch --quiet --create feat/good-name
  run_git push origin feat/good-name
  assert_accepted
  git -C "$WORK/remote.git" rev-parse --verify --quiet refs/heads/feat/good-name >/dev/null ||
    fail "the accepted push didn't reach the remote"
}

# `prek` runs the `pre-push` hook only when the push carries a commit that the
# remote-tracking branches of the remote lack. A push that has none, such as a
# tag on a commit that the remote has or the deletion of a remote branch, skips
# the hook, so the branch name rule doesn't apply to it. A push with a new
# commit still stops.
case_push_without_a_new_commit_skips_the_branch_hook() {
  new_repository push-skip
  git init --quiet --bare "$WORK/remote-skip.git"
  git -C "$REPO" remote add origin "$WORK/remote-skip.git"
  git -C "$REPO" switch --quiet --create feat/good-name
  run_git push origin feat/good-name
  assert_accepted

  git -C "$REPO" switch --quiet --create Bad_Name
  git -C "$REPO" tag v1
  run_git push origin v1
  assert_accepted
  assert_output_lacks "gitpolicy-branch"

  run_git push origin --delete feat/good-name
  assert_accepted
  assert_output_lacks "gitpolicy-branch"

  git -C "$REPO" commit --quiet --allow-empty --message "feat: add a commit"
  run_git push origin Bad_Name
  assert_refused
  assert_output_contains "gitpolicy-branch"
}

# Runs each case in the list below, or only the cases that the arguments name.
# The cases are independent: each one builds its own repository. The list is
# explicit because the minimal Bash of the Nix sandbox has no `compgen`. Add each
# new case here.
main() {
  local -a cases=(
    case_install_writes_the_three_hooks
    case_install_keeps_a_foreign_hook
    case_failing_foreign_hook_stops_the_commit
    case_install_replaces_an_earlier_core_hooks_path
    case_global_core_hooks_path_makes_the_install_fail_and_changes_nothing
    case_core_hooks_path_of_another_scope_makes_the_install_fail
    case_global_core_hooks_path_outside_a_work_tree_is_no_failure
    case_install_skips_a_repository_without_a_work_tree
    case_empty_global_core_hooks_path_is_refused_and_shown
    case_linked_worktree_runs_no_hook_before_its_install
    case_linked_worktree_install_is_per_worktree
    case_clean_commit_is_accepted
    case_bad_message_is_refused
    case_fixup_commit_is_accepted
    case_staged_secret_is_refused
    case_unformatted_file_is_formatted_and_refused
    case_formatting_is_reverted_when_the_file_has_an_unstaged_edit
    case_markdown_violation_is_refused
    case_markdown_check_reads_untracked_files
    case_workflow_without_a_time_limit_is_refused
    case_hooks_read_the_staged_text
    case_secrets_scan_runs_on_a_commit_without_files
    case_skip_leaves_out_one_hook
    case_bad_branch_name_is_refused_at_push
    case_push_without_a_new_commit_skips_the_branch_hook
  )
  # Names on the command line replace the list: run one case while you work.
  if [ "$#" -gt 0 ]; then
    cases=("$@")
  fi
  write_nix_store_stand_in
  local name
  for name in "${cases[@]}"; do
    case $name in
    case_*) ;;
    *)
      echo "not a case name: $name" >&2
      exit 2
      ;;
    esac
    CURRENT_CASE=$name
    echo "run:  $name"
    "$name"
    echo "ok:   $name"
  done
  echo "All ${#cases[@]} cases passed."
}

main "$@"
