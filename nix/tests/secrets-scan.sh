#!/usr/bin/env bash
# Tests for `nix/scripts/secrets-scan.sh`, the command that
# `nix/lib/secrets-scan.nix` builds.
#
# Usage: SECRETS_SCAN_TEST_SCANNER=<gitleaks|betterleaks> \
#          bash nix/tests/secrets-scan.sh [case_name ...]
#
# With case names, the file runs only those cases.
#
# The command `secrets-scan` and `git` must be on PATH. The variable names the
# scanner that the command runs: only the cases of the ignore files and markers
# that belong to one scanner read it. The flake checks
# `secrets-scan-tests-gitleaks` and `secrets-scan-tests-betterleaks` run this
# file once for each scanner, with the same cases: the scanner is the one
# argument of `mkSecretsScan` that changes, and the cases are its contract.
#
# Each case builds a Git repository under a temporary directory. The secret
# that the cases commit or stage has the shape of a GitHub token, and the file
# assembles it from parts when it runs. No file of the hub holds the whole
# string, so neither the hub's own scan of its history nor the `leaks` check
# finds it. The token isn't valid for any account. The cases use no network.
#
# Git reads no configuration file of the user: a setting such as commit
# signing or hooks of the machine can't change a case. The cases that test a
# setting of the user write their own file, for the length of the case. A
# failing case prints
# its name and the output of the last scan, then stops the run with exit status
# 1. Every scan asserts that its output never holds the secret. No case puts the
# secret in a file name or a commit message, where the output can show it.

set -euo pipefail

readonly SCANNER=${SECRETS_SCAN_TEST_SCANNER:?set it to gitleaks or betterleaks}

export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME=Test
export GIT_AUTHOR_EMAIL=test@example.test
export GIT_COMMITTER_NAME=Test
export GIT_COMMITTER_EMAIL=test@example.test

WORK=$(mktemp -d)
readonly WORK
trap 'rm -rf -- "$WORK"' EXIT

readonly OUT=$WORK/output

# The rule of both scanners that matches the secret of the cases.
readonly RULE=github-pat

# Set by `new_repository`: the work tree of the running case.
REPO=
# Set by `run_scan`: the exit status of the last scan.
STATUS=0

# --- Helpers ---------------------------------------------------------------

# Prints the secret of the cases: a GitHub-token-shaped string that the
# function assembles from parts.
secret() {
  printf '%s%s%s%s%s' gh p_ 7Kq2Zx9LmN4v B8tRw3YhD5sF g1JcUo6EaP0i
}

# Prints the failure message $1 with the name of the running case, then the
# output of the last scan, and exits 1.
fail() {
  echo "FAIL: ${CURRENT_CASE:-setup}: $1" >&2
  if [ -f "$OUT" ]; then
    echo "--- output of the last scan:" >&2
    cat "$OUT" >&2
  fi
  exit 1
}

# Fails unless the last scan exited with the status $1.
assert_status() {
  [ "$STATUS" = "$1" ] || fail "exit status: expected $1, got $STATUS"
}

# Fails unless the output of the last scan contains the text $1.
assert_output_contains() {
  grep -qF -- "$1" "$OUT" || fail "the output lacks '$1'"
}

# Fails if the output of the last scan contains the text $1.
assert_output_lacks() {
  ! grep -qF -- "$1" "$OUT" || fail "the output has '$1'"
}

# Creates the repository $WORK/$1 with no commit, and sets REPO to its path.
# The repository is the working directory afterwards.
init_repository() {
  REPO=$WORK/$1
  mkdir -p "$REPO"
  cd "$REPO"
  git init --quiet .
  rm -f "$OUT"
}

# Creates the repository $WORK/$1 with one commit that holds a clean file, and
# sets REPO to its path. The repository is the working directory afterwards.
new_repository() {
  init_repository "$1"
  printf '# Title\n\nThis page is short.\n' >README.md
  git add README.md
  git commit --quiet --message "Add the readme"
}

# Appends a line to the readme of REPO and commits it, so that the commit
# that came before has a child.
commit_readme_edit() {
  printf 'More text.\n' >>"$REPO/README.md"
  git -C "$REPO" commit --quiet --all --message "Edit the readme"
}

# Deletes the loose object that the revision $1 names from the object store of
# REPO, and prints the object ID. Git writes every object of a test repository
# as a loose file, so the damage is the same on each run.
remove_object() {
  local id
  id=$(git -C "$REPO" rev-parse "$1")
  rm -f -- "$REPO/.git/objects/${id:0:2}/${id:2}"
  printf '%s\n' "$id"
}

# Overwrites the loose object that the revision $1 names in the object store of
# REPO with bytes that are no valid object, and prints the object ID. The file
# stays in place, so a check that only looks for the object finds it. Git makes
# a loose object read-only, so the function makes it writable first.
damage_object() {
  local id path
  id=$(git -C "$REPO" rev-parse "$1")
  path=$REPO/.git/objects/${id:0:2}/${id:2}
  chmod u+w "$path"
  printf 'these bytes are not a zlib stream\n' >"$path"
  printf '%s\n' "$id"
}

# Makes the text $1 the global Git configuration of the user for the commands
# that follow, so a case can test a user setting. The text is a Git
# configuration file as `printf '%b'` prints it: `\n` is a line break and `\t`
# a tab. `reset_user_git_config` ends the effect, and every case that calls this
# function calls that one before it ends.
set_user_git_config() {
  printf '%b\n' "$1" >"$WORK/user.gitconfig"
  export GIT_CONFIG_GLOBAL=$WORK/user.gitconfig
}

# Ends the effect of `set_user_git_config`.
reset_user_git_config() {
  export GIT_CONFIG_GLOBAL=/dev/null
}

# Writes the line `ref: <secret>` into the file $1 of the repository, a path
# relative to the repository. The key `ref` is no word that a generic rule
# looks for, so only the rule of the token shape matches. The function creates
# the parent directories.
write_secret_file() {
  mkdir -p "$(dirname -- "$REPO/$1")"
  printf 'ref: %s\n' "$(secret)" >"$REPO/$1"
}

# Writes the secret into the file $1 and commits it.
commit_secret() {
  write_secret_file "$1"
  git -C "$REPO" add -- "$1"
  git -C "$REPO" commit --quiet --message "Add $1"
}

# Writes the secret into the file $1 and stages it without a commit.
stage_secret() {
  write_secret_file "$1"
  git -C "$REPO" add -- "$1"
}

# Runs `secrets-scan` with the arguments $1 and later in the directory $SCAN_DIR
# or, without that variable, in the repository. Sets STATUS to its exit status
# and writes its stdout and stderr to OUT. Fails when the output holds the
# secret, whatever the status is.
run_scan() {
  STATUS=0
  (cd "${SCAN_DIR:-$REPO}" && secrets-scan "$@") >"$OUT" 2>&1 || STATUS=$?
  assert_output_lacks "$(secret)"
}

# Writes the fingerprint $1 into the file `.gitleaksignore` of the repository.
write_ignore_file() {
  printf '%s\n' "$1" >"$REPO/.gitleaksignore"
}

# Prints the fingerprint of the secret in the file $1 at line 1 as a scan of
# the history gives it: the commit, the file, the rule and the line.
history_fingerprint() {
  printf '%s:%s:%s:1' "$(git -C "$REPO" rev-parse HEAD)" "$1" "$RULE"
}

# Prints the fingerprint of the secret in the file $1 at line 1 as a scan of
# the staged changes gives it: the file, the rule and the line.
staged_fingerprint() {
  printf '%s:%s:1' "$1" "$RULE"
}

# --- Cases -----------------------------------------------------------------

# A repository without a secret passes both scans.
case_clean_repository_passes() {
  new_repository clean

  run_scan history
  assert_status 0
  assert_output_contains "no leaks found"

  run_scan staged
  assert_status 0
  assert_output_contains "no leaks found"
}

# A secret in a commit fails the scan of the history. The output names the
# rule and the file.
case_history_finds_a_committed_secret() {
  new_repository committed
  commit_secret ci.yml

  run_scan history
  assert_status 1
  assert_output_contains "$RULE"
  assert_output_contains "ci.yml"
}

# A later commit that removes the secret doesn't remove it from the history.
case_history_finds_a_secret_that_a_commit_removed() {
  new_repository removed
  commit_secret ci.yml
  git rm --quiet ci.yml
  git commit --quiet --message "Remove ci.yml"

  run_scan history
  assert_status 1
  assert_output_contains "$RULE"
}

# The scan reads every branch, not only the checked-out one.
case_history_reads_every_branch() {
  new_repository branches
  git checkout --quiet -b side
  commit_secret ci.yml
  git checkout --quiet -

  run_scan history
  assert_status 1
  assert_output_contains "$RULE"
}

# A secret that is staged and not yet committed isn't in the history.
case_history_ignores_a_staged_secret() {
  new_repository staged-only
  stage_secret ci.yml

  run_scan history
  assert_status 0
}

# A secret in the index fails the scan of the staged changes.
case_staged_finds_a_staged_secret() {
  new_repository staged
  stage_secret ci.yml

  run_scan staged
  assert_status 1
  assert_output_contains "$RULE"
  assert_output_contains "ci.yml"
}

# A secret in a file that isn't staged passes the scan of the staged changes:
# the hook checks what the commit holds.
case_staged_ignores_an_unstaged_secret() {
  new_repository unstaged
  write_secret_file ci.yml

  run_scan staged
  assert_status 0
}

# A secret in an earlier commit passes the scan of the staged changes. The scan
# of the history finds it.
case_staged_ignores_a_committed_secret() {
  new_repository earlier
  commit_secret ci.yml
  printf 'More text.\n' >>README.md
  git add README.md

  run_scan staged
  assert_status 0
}

# The scan runs at the top of the work tree, so a hook that runs in a subfolder
# finds the secret and the `.gitleaksignore` file at the root.
case_staged_runs_from_a_subfolder() {
  new_repository subfolder
  mkdir -p deep/er
  stage_secret ci.yml
  SCAN_DIR=$REPO/deep/er

  run_scan staged
  assert_status 1

  write_ignore_file "$(staged_fingerprint ci.yml)"
  run_scan staged
  assert_status 0
  unset SCAN_DIR
}

# A fingerprint in `.gitleaksignore` suppresses a finding in the history.
case_gitleaksignore_suppresses_a_committed_secret() {
  new_repository ignored-committed
  commit_secret ci.yml
  run_scan history
  assert_status 1

  write_ignore_file "$(history_fingerprint ci.yml)"
  run_scan history
  assert_status 0
}

# A fingerprint in `.gitleaksignore` suppresses a staged finding.
case_gitleaksignore_suppresses_a_staged_secret() {
  new_repository ignored-staged
  stage_secret ci.yml

  run_scan staged
  assert_status 1

  write_ignore_file "$(staged_fingerprint ci.yml)"
  run_scan staged
  assert_status 0
}

# A fingerprint for another line, another file or another commit suppresses
# nothing: the file matches findings, not the repository.
case_gitleaksignore_matches_only_its_fingerprint() {
  new_repository ignored-other
  commit_secret ci.yml

  local fingerprint
  fingerprint=$(history_fingerprint ci.yml)
  write_ignore_file "${fingerprint%:1}:2"
  run_scan history
  assert_status 1

  write_ignore_file "$(history_fingerprint other.yml)"
  run_scan history
  assert_status 1
}

# A `gitleaks:allow` comment on the line suppresses the finding in both scans.
case_allow_comment_suppresses_the_line() {
  new_repository allowed
  printf 'ref: %s # gitleaks:allow\n' "$(secret)" >ci.yml
  git add ci.yml
  git commit --quiet --message "Add ci.yml"

  run_scan history
  assert_status 0

  printf 'ref: %s # gitleaks:allow\n' "$(secret)" >staged.yml
  git add staged.yml
  run_scan staged
  assert_status 0
}

# A configuration file in the repository has no effect: the base configuration
# of the hub is the only one. The files here allow the path of the secret, and
# the scan still finds it.
case_repository_configuration_file_is_not_read() {
  new_repository own-config
  printf '[extend]\nuseDefault = true\n\n[allowlist]\npaths = [%s]\n' \
    "'''ci\\.yml'''" >.gitleaks.toml
  cp .gitleaks.toml .betterleaks.toml
  commit_secret ci.yml

  run_scan history
  assert_status 1
  assert_output_contains "$RULE"
}

# The output is redacted. A finding shows the word REDACTED where the secret
# is, in both scans. `run_scan` asserts that the secret itself never shows.
case_output_is_redacted() {
  new_repository redacted
  commit_secret ci.yml
  stage_secret staged.yml

  run_scan history
  assert_status 1
  assert_output_contains "REDACTED"

  run_scan staged
  assert_status 1
  assert_output_contains "REDACTED"
}

# A call with no argument, an unknown command or an extra argument is a usage
# error with exit status 2, and no scan runs.
case_wrong_arguments_exit_2() {
  new_repository usage
  commit_secret ci.yml

  run_scan
  assert_status 2
  assert_output_contains "usage: secrets-scan history | staged"

  run_scan everything
  assert_status 2

  run_scan history staged
  assert_status 2
  assert_output_lacks "$RULE"
}

# A directory that isn't a work tree is an error and not a clean result. The
# status is the 128 of `git`, so it isn't the 1 of a finding.
case_outside_a_work_tree_fails() {
  new_repository outside
  SCAN_DIR=$WORK
  mkdir -p "$SCAN_DIR"

  run_scan history
  assert_status 128
  assert_output_contains "not a git repository"
  unset SCAN_DIR
}

# A shallow clone lacks the older commits, and a scan of it passes the secret
# that they hold: here a commit removed the secret, so the one commit of the
# clone is clean while the history holds the secret. The scan of the history refuses it with status 3 and names the
# two ways to fetch the rest. The scan of the staged changes needs no history.
case_history_refuses_a_shallow_clone() {
  new_repository shallow-source
  commit_secret ci.yml
  git rm --quiet ci.yml
  git commit --quiet --message "Remove ci.yml"
  git clone --quiet --depth 1 "file://$REPO" "$WORK/shallow-clone"
  REPO=$WORK/shallow-clone
  test "$(git -C "$REPO" rev-parse --is-shallow-repository)" = true

  run_scan history
  assert_status 3
  assert_output_contains "fetch-depth: 0"
  assert_output_contains "git fetch --unshallow"
  assert_output_lacks "no leaks found"

  stage_secret staged.yml
  run_scan staged
  assert_status 1
  assert_output_contains "staged.yml"

  git -C "$REPO" fetch --quiet --unshallow
  run_scan history
  assert_status 1
  assert_output_contains "ci.yml"
}

# A history with a missing object is incomplete, and a scanner doesn't say so:
# gitleaks exits 0 with "no leaks found", and betterleaks exits 1, the status
# of a finding. The scan of the history refuses it with status 4 for a missing
# blob, tree or commit, and the output names the object.
case_history_refuses_an_unreadable_history() {
  local kind revision id
  for kind in blob tree commit; do
    new_repository "damaged-$kind"
    commit_secret ci.yml
    commit_readme_edit
    case $kind in
    blob) revision=HEAD~1:ci.yml ;;
    tree) revision='HEAD~1^{tree}' ;;
    commit) revision=HEAD~1 ;;
    esac
    id=$(remove_object "$revision")

    run_scan history
    assert_status 4
    assert_output_contains "$id"
    assert_output_lacks "no leaks found"
  done
}

# A history with an object that holds no valid data is unreadable, and a check
# that only looks for each object doesn't see it: the file is there. Git fails
# on it, gitleaks logs "inflate: data stream error" and exits 0, and betterleaks
# exits 1, the status of a finding. The scan of the history refuses it with
# status 4 for a blob, a tree or a commit, and the output names the object.
case_history_refuses_an_object_with_damaged_content() {
  local kind revision id
  for kind in blob tree commit; do
    new_repository "garbage-$kind"
    commit_secret ci.yml
    commit_readme_edit
    case $kind in
    blob) revision=HEAD~1:ci.yml ;;
    tree) revision='HEAD~1^{tree}' ;;
    commit) revision=HEAD~1 ;;
    esac
    id=$(damage_object "$revision")

    run_scan history
    assert_status 4
    assert_output_contains "$id"
    assert_output_lacks "no leaks found"
  done
}

# A repository with no commit has no history to scan: the scan of the history
# passes. The scan of the staged changes still finds a staged secret.
case_repository_without_commits() {
  init_repository no-commits

  run_scan history
  assert_status 0
  assert_output_contains "no leaks found"

  run_scan staged
  assert_status 0

  stage_secret ci.yml
  run_scan staged
  assert_status 1
  assert_output_contains "$RULE"

  run_scan history
  assert_status 0
}

# In a linked worktree the command runs at the top of that worktree: it finds
# the staged secret there, and the `.gitleaksignore` file of that worktree
# applies to the staged scan and to the scan of the history.
case_linked_worktree() {
  new_repository main-tree
  git worktree add --quiet -b side "$WORK/linked-tree"
  REPO=$WORK/linked-tree
  stage_secret ci.yml

  run_scan staged
  assert_status 1
  assert_output_contains "ci.yml"

  write_ignore_file "$(staged_fingerprint ci.yml)"
  run_scan staged
  assert_status 0

  rm -f "$REPO/.gitleaksignore"
  git -C "$REPO" commit --quiet --message "Add ci.yml"
  run_scan history
  assert_status 1

  write_ignore_file "$(history_fingerprint ci.yml)"
  run_scan history
  assert_status 0
}

# A secret that a staged rename carries together with an edit is a finding in
# the new file. The line that the commit adds is the finding, so the scan names
# the new path.
case_staged_finds_a_secret_added_in_a_renamed_file() {
  new_repository rename-adds
  printf 'Line one.\nLine two.\nLine three.\nLine four.\n' >notes.txt
  git add notes.txt
  git commit --quiet --message "Add notes.txt"
  git mv notes.txt ci.yml
  printf 'ref: %s\n' "$(secret)" >>ci.yml
  git add ci.yml

  run_scan staged
  assert_status 1
  assert_output_contains "$RULE"
  assert_output_contains "ci.yml"
}

# Git prints a rename that has no edit as `rename from` and `rename to` lines
# without a hunk, so a scanner that reads the added lines finds nothing. The
# command turns rename detection off: Git prints the file as an addition at the
# new path with its whole content. A staged rename of a file with a committed
# secret is a finding at the new path, and the scan of the history finds the
# secret at the old path.
case_staged_finds_a_committed_secret_that_a_rename_moves() {
  new_repository rename-moves
  commit_secret ci.yml
  git mv ci.yml moved.yml

  run_scan staged
  assert_status 1
  assert_output_contains "moved.yml"

  run_scan history
  assert_status 1
  assert_output_contains "ci.yml"
}

# Both scanners skip a file whose path the default rules allow, such as
# `creds.png`. A rename of such a file to a path that the scanners read prints no
# added line with rename detection, so the secret would pass at the new path
# while the file at HEAD holds it. With the detection off, both scans read the
# file at the new path.
case_a_rename_out_of_a_skipped_path_does_not_hide_a_secret() {
  new_repository rename-from-skipped-history
  commit_secret creds.png
  run_scan history
  assert_status 0
  git mv creds.png deploy.yml
  git commit --quiet --message "Rename creds.png"

  run_scan history
  assert_status 1
  assert_output_contains "deploy.yml"

  new_repository rename-from-skipped-staged
  commit_secret creds.png
  git mv creds.png deploy.yml

  run_scan staged
  assert_status 1
  assert_output_contains "deploy.yml"
}

# A staged deletion adds no line, so the scan of the staged changes passes, and
# the secret stays in the history.
case_staged_deletion_passes_and_history_keeps_the_secret() {
  new_repository deletion
  commit_secret ci.yml
  git rm --quiet ci.yml

  run_scan staged
  assert_status 0

  run_scan history
  assert_status 1
  assert_output_contains "ci.yml"
}

# Makes Git treat the files `*.txt` of REPO as binary in the way that $1 names:
#   nul                A NUL byte in the content decides: `write_txt_secret`
#                      adds it, and the function sets nothing.
#   diff-attribute     `*.txt -diff` in a `.gitattributes` file of the commits.
#   binary-attribute   `*.txt binary` in a `.gitattributes` file of the commits.
#   info-attributes    `*.txt binary` in `.git/info/attributes`, a file of the
#                      clone that no commit holds.
#   diff-driver        `*.txt diff=opaque` in a `.gitattributes` file, and the
#                      setting `diff.opaque.binary = true` in the configuration
#                      of the repository.
make_txt_files_binary() {
  case $1 in
  nul) ;;
  diff-attribute | binary-attribute | diff-driver)
    case $1 in
    diff-attribute) printf '*.txt -diff\n' >.gitattributes ;;
    binary-attribute) printf '*.txt binary\n' >.gitattributes ;;
    diff-driver) printf '*.txt diff=opaque\n' >.gitattributes ;;
    esac
    git add .gitattributes
    git commit --quiet --message "Add the attributes"
    if [ "$1" = diff-driver ]; then
      git config diff.opaque.binary true
    fi
    ;;
  info-attributes)
    printf '*.txt binary\n' >"$(git rev-parse --git-path info/attributes)"
    ;;
  esac
}

# Writes the secret into the file $2, as `write_secret_file` does, and adds a
# NUL byte after it when the kind of binary file $1 is `nul`.
write_txt_secret() {
  write_secret_file "$2"
  if [ "$1" = nul ]; then
    printf '\0tail\n' >>"$REPO/$2"
  fi
}

# Git prints "Binary files differ" and no line for a file that it treats as
# binary, and a scanner finds nothing in such a file. A person who can commit
# decides which files are binary: a NUL byte in a file, the attribute `-diff`
# or `binary` in a `.gitattributes` file, and a diff driver whose `binary`
# setting is true. The attributes of the clone in `.git/info/attributes` do the
# same. The command makes Git print every file as text, so both scans find a
# secret in a file of each kind.
case_a_file_that_git_treats_as_binary_does_not_hide_a_secret() {
  local kind
  for kind in nul diff-attribute binary-attribute info-attributes diff-driver; do
    new_repository "binary-$kind"
    make_txt_files_binary "$kind"
    write_txt_secret "$kind" committed.txt
    git add committed.txt
    git commit --quiet --message "Add committed.txt"
    write_txt_secret "$kind" staged.txt
    git add staged.txt

    run_scan history
    assert_status 1
    assert_output_contains "committed.txt"

    run_scan staged
    assert_status 1
    assert_output_contains "staged.txt"
  done
}

# Both scanners skip a file whose extension marks a binary format, such as
# `.png`, even when the file is text: the default rules of the scanner allow
# the path. This case pins a limit that the page lists: a repository that keeps
# secrets in such a file needs another control.
case_a_file_with_the_extension_of_a_binary_format_is_not_scanned() {
  new_repository binary-extension
  write_secret_file committed.png
  git add committed.png
  git commit --quiet --message "Add committed.png"
  stage_secret staged.png

  run_scan history
  assert_status 0

  run_scan staged
  assert_status 0
}

# The default filter of the scanners for the diff of the history is
# `--diff-filter=tuxdb`: its `t` leaves out a commit that turns a symbolic link
# into a file, and the diff of that commit holds the whole content of the file.
# The command uses its own filter, so the scan finds the secret.
case_history_finds_a_secret_in_a_file_that_replaced_a_symbolic_link() {
  new_repository type-change
  ln -s README.md ci.yml
  git add ci.yml
  git commit --quiet --message "Add a link"
  rm ci.yml
  commit_secret ci.yml
  test "$(git ls-tree HEAD ci.yml | cut -c1-6)" = 100644

  run_scan history
  assert_status 1
  assert_output_contains "ci.yml"
}

# A `refs/replace` reference makes Git show another object in place of a commit.
# gitleaks reads the replacement, and betterleaks turns the feature off. The
# command turns it off for both scanners, so the scan reads the commit that the
# history holds. The branch `kept` keeps the commit with the secret reachable.
case_a_replace_reference_does_not_hide_a_commit() {
  new_repository replace
  commit_secret ci.yml
  local secret_commit
  secret_commit=$(git rev-parse HEAD)
  git branch kept
  git reset --quiet --hard HEAD~1
  commit_readme_edit
  git replace "$secret_commit" HEAD

  run_scan history
  assert_status 1
  assert_output_contains "ci.yml"
}

# A user who sets `color.ui=always` or `color.diff=always` makes `git diff` and
# `git log -p` print escape codes. gitleaks reads such a diff without an error,
# finds nothing in it and exits 0, so the command pins both settings to `never`.
# Both scans must still find the secret.
case_colour_settings_of_the_user_do_not_hide_a_secret() {
  new_repository colour
  commit_secret ci.yml
  stage_secret staged.yml

  local setting
  for setting in '[color]\n\tui = always' '[color]\n\tdiff = always'; do
    set_user_git_config "$setting"

    run_scan history
    assert_status 1
    assert_output_contains "ci.yml"

    run_scan staged
    assert_status 1
    assert_output_contains "staged.yml"
  done
  reset_user_git_config
}

# The command adds its Git settings to the ones that the caller put in the
# variables `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_<n>` and `GIT_CONFIG_VALUE_<n>`,
# and it doesn't replace them. Here the caller's setting names an order file
# that doesn't exist, which makes `git diff` fail, so the scan refuses with
# status 4 and shows that the setting reached Git. Without the caller's setting,
# the scan finds the secret.
case_settings_of_the_caller_in_the_environment_stay() {
  new_repository environment
  stage_secret ci.yml

  GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=diff.orderFile \
    GIT_CONFIG_VALUE_0=$WORK/no-such-file run_scan staged
  assert_status 4

  run_scan staged
  assert_status 1
  assert_output_contains "ci.yml"
}

# A textconv filter replaces the content of a file in the diff. The attribute
# `diff=<driver>` in a `.gitattributes` file of the repository selects the
# driver, and the configuration of the user defines its filter. A filter that
# prints nothing hides the file from gitleaks, so the command sets the filter
# of every driver to `cat`. Both scans must still find the secret.
case_textconv_filter_does_not_hide_a_secret() {
  new_repository textconv
  printf '*.yml diff=hide\n' >.gitattributes
  git add .gitattributes
  git commit --quiet --message "Add the attributes"
  commit_secret ci.yml
  stage_secret staged.yml
  set_user_git_config '[diff "hide"]\n\ttextconv = true'

  run_scan history
  assert_status 1
  assert_output_contains "ci.yml"

  run_scan staged
  assert_status 1
  assert_output_contains "staged.yml"
  reset_user_git_config
}

# Git reads `GIT_CONFIG_PARAMETERS` after `GIT_CONFIG_COUNT`, so a setting in it
# wins over the pins of the command unless the command writes its pins there.
# The variable holds what `git -c` exports to the processes that Git starts. In
# each form that Git reads, a caller who sets a colour option to `always` must
# not hide the secret from either scan. The last check shows that a setting of
# the caller for another key still reaches Git: it names an order file that
# doesn't exist, so the scan refuses with status 4.
case_git_config_parameters_of_the_caller_do_not_override_the_pins() {
  new_repository parameters
  commit_secret ci.yml
  stage_secret staged.yml

  local setting
  for setting in \
    "'color.diff'='always'" \
    "'color.ui'='always'" \
    "'color.ui'='always' 'color.diff'='always'" \
    "'color.diff=always'"; do
    GIT_CONFIG_PARAMETERS=$setting run_scan history
    assert_status 1
    assert_output_contains "ci.yml"

    GIT_CONFIG_PARAMETERS=$setting run_scan staged
    assert_status 1
    assert_output_contains "staged.yml"
  done

  GIT_CONFIG_PARAMETERS="'diff.orderFile'='$WORK/no-such-file'" \
    run_scan staged
  assert_status 4
}

# The same as the case above, with the real source of the variable: a Git alias
# that a `git -c` command starts. Git puts each `-c` option into
# `GIT_CONFIG_PARAMETERS` for the alias. The alias runs the command, as a Git
# alias or a hook of a user can.
case_git_dash_c_options_of_a_calling_alias_do_not_override_the_pins() {
  new_repository dash-c
  commit_secret ci.yml
  stage_secret staged.yml

  local subcommand
  for subcommand in history staged; do
    STATUS=0
    git -c color.diff=always -c color.ui=always \
      -c "alias.scan=!secrets-scan $subcommand" scan >"$OUT" 2>&1 || STATUS=$?
    assert_output_lacks "$(secret)"
    assert_status 1
    assert_output_contains "$RULE"
  done
}

# Fails unless both scans exit with status 4, print no "no leaks found" and
# print the text $1, which Git's message holds.
assert_both_scans_refuse() {
  local subcommand
  for subcommand in history staged; do
    run_scan "$subcommand"
    assert_status 4
    assert_output_lacks "no leaks found"
    assert_output_contains "$1"
  done
}

# A scanner can't tell that Git failed to produce a diff: gitleaks exits 0 with
# "no leaks found" when `git diff` fails, and when Git writes a warning to
# standard error, and betterleaks exits 1, the status of a finding. Both scans
# refuse such a repository with status 4, and the output names the setting. The
# first setting makes Git exit with status 128, the second one only warns and
# exits 0. The last check shows that the scan finds the secret once the setting
# is gone, so the repository was the cause and the status 4 was no accident.
case_a_diff_that_git_cannot_produce_is_refused() {
  new_repository failing-diff
  commit_secret ci.yml
  stage_secret staged.yml

  set_user_git_config '[diff]\n\torderFile = /nonexistent'
  assert_both_scans_refuse "/nonexistent"

  set_user_git_config '[diff]\n\tdirstat = bogus'
  assert_both_scans_refuse "bogus"
  reset_user_git_config

  run_scan staged
  assert_status 1
}

# Git prints no diff for a file that a diff driver marks as binary and for a file
# above `core.bigFileThreshold`, and neither setting is an error, so a scanner
# reports no finding. The `--text` of the command overrides both, and both scans
# find the secret.
case_diff_driver_binary_and_big_file_threshold_do_not_hide_a_secret() {
  new_repository hiders
  printf '*.yml diff=hide\n' >.gitattributes
  git add .gitattributes
  git commit --quiet --message "Add the attributes"
  commit_secret ci.yml
  stage_secret staged.yml

  local setting
  for setting in \
    '[diff "hide"]\n\tbinary = true' \
    '[core]\n\tbigFileThreshold = 1'; do
    set_user_git_config "$setting"

    run_scan history
    assert_status 1
    assert_output_contains "ci.yml"

    run_scan staged
    assert_status 1
    assert_output_contains "staged.yml"
  done
  reset_user_git_config
}

# The command writes the name of each driver into `GIT_CONFIG_PARAMETERS` in
# Git's quoting. A name with a single quote or an exclamation mark needs the
# escapes of Git, and a wrong quote makes Git reject the variable, which the scan
# reports with status 4. With the right quotes, the filter of the driver is
# replaced and the scans find the secret.
case_driver_names_with_quote_characters_are_pinned() {
  new_repository quoting
  printf "*.yml diff=x'y!z\n" >.gitattributes
  git add .gitattributes
  git commit --quiet --message "Add the attributes"
  commit_secret ci.yml
  stage_secret staged.yml
  set_user_git_config "[diff \"x'y!z\"]\n\ttextconv = true"

  run_scan history
  assert_status 1
  assert_output_contains "ci.yml"

  run_scan staged
  assert_status 1
  assert_output_contains "staged.yml"
  reset_user_git_config
}

# Git warns on standard error, and still prints the whole diff, when a change
# has more renamed files than `diff.renameLimit`. The `git` of the command turns
# rename detection off, so Git prints no warning during the scan, and the scan
# must not refuse such a repository. The check of the setup shows that Git does
# print the warning when rename detection is on.
case_rename_limit_warning_does_not_stop_the_scan() {
  new_repository rename-limit
  local number
  for number in 1 2 3 4 5 6; do
    seq 1 40 | sed "s/^/file $number /" >"old-$number.txt"
  done
  git add .
  git commit --quiet --message "Add the files"
  for number in 1 2 3 4 5 6; do
    git mv "old-$number.txt" "new-$number.txt"
    printf 'tail\n' >>"new-$number.txt"
    git add "new-$number.txt"
  done
  stage_secret ci.yml
  set_user_git_config '[diff]\n\trenameLimit = 2'
  local warning
  warning=$(git diff -U0 --no-ext-diff --staged . 2>&1 >/dev/null)
  [[ $warning == *"rename detection was skipped"* ]] ||
    fail "Git prints no rename warning, so the case tests nothing"

  run_scan staged
  assert_status 1
  assert_output_contains "ci.yml"

  git commit --quiet --message "Rename the files"
  run_scan history
  assert_status 1
  assert_output_contains "ci.yml"
  reset_user_git_config
}

# Makes REPO a repository whose merge of the branch `side` into the branch
# before it has a conflict in the file `config.yml`, and leaves the conflict
# unresolved in the work tree. Neither parent of the merge holds a secret.
start_conflicting_merge() {
  new_repository "$1"
  printf 'value: 0\n' >config.yml
  git add config.yml
  git commit --quiet --message "Add config.yml"
  git checkout --quiet -b side
  printf 'value: side\n' >config.yml
  git commit --quiet --all --message "Change config.yml on side"
  git checkout --quiet -
  printf 'value: main\n' >config.yml
  git commit --quiet --all --message "Change config.yml on main"
  git merge --quiet side >/dev/null 2>&1 || test -n "$(git ls-files --unmerged)"
}

# A secret that only the resolution of a merge conflict holds is in the merge
# commit and in neither parent. `git log -p` prints no diff for a merge commit,
# so the scan of the history needs `--diff-merges=remerge` to see it.
case_history_finds_a_secret_in_a_conflict_resolution() {
  start_conflicting_merge conflict
  write_secret_file config.yml
  git add config.yml
  git commit --quiet --message "Merge side"
  test "$(git rev-list --count --merges HEAD)" = 1

  run_scan history
  assert_status 1
  assert_output_contains "$RULE"
  assert_output_contains "config.yml"
}

# The diff of a merge commit holds only what the merge changed by hand. A secret
# that a merged branch brought in is a finding of the commit on that branch, and
# a fingerprint for that commit suppresses it. The merge commit doesn't report
# it again, as a diff against the first parent would: CI runs on a merge commit
# that GitHub makes of a pull request, and its hash changes with each run, so a
# fingerprint for it could not exist.
case_history_does_not_report_a_merged_branch_again() {
  new_repository merged-branch
  git checkout --quiet -b feature
  commit_secret ci.yml
  local feature_commit
  feature_commit=$(git rev-parse HEAD)
  git checkout --quiet -
  printf 'More text.\n' >>README.md
  git commit --quiet --all --message "Edit the readme"
  git merge --quiet --no-ff --message "Merge feature" feature
  test "$(git rev-list --count --merges HEAD)" = 1

  run_scan history
  assert_status 1

  write_ignore_file "$feature_commit:ci.yml:$RULE:1"
  run_scan history
  assert_status 0
}

# Makes REPO a repository whose last commit is an octopus merge, a merge of
# three parents: the readme edit and the branches `one` and `two`. The merge
# makes a change by hand that neither parent holds. The change is the secret in
# a new file when $2 is `add`, and a line with the secret at the end of the
# readme when $2 is `edit`. The name of the repository is $1.
commit_octopus_merge_with_secret() {
  new_repository "$1"
  local base branch
  base=$(git rev-parse HEAD)
  for branch in one two; do
    git checkout --quiet -b "$branch" "$base"
    printf '%s\n' "$branch" >"$branch.txt"
    git add "$branch.txt"
    git commit --quiet --message "Add $branch.txt"
    git checkout --quiet -
  done
  commit_readme_edit
  git merge --quiet --no-ff --no-commit one two >/dev/null
  if [ "$2" = add ]; then
    write_secret_file ci.yml
    git add ci.yml
  else
    printf 'ref: %s\n' "$(secret)" >>README.md
    git add README.md
  fi
  git commit --quiet --message "Merge one and two"
  git rev-parse --verify --quiet HEAD^3 >/dev/null
}

# A merge of more than two parents has no remerge diff: Git prints a warning
# line in place of the diff. A secret that only an octopus merge holds passes
# the scan of the history, whether the merge adds it in a new file or edits a
# file. Neither parent has the secret. The checks of the setup show that Git
# has no remerge diff for the merge, that its combined diff holds the secret,
# and that no parent holds it. This case pins a limit that the page lists: if
# Git learns to remerge an octopus merge, the first check fails and the page
# needs a change.
case_octopus_merge_is_not_scanned() {
  local how remerge combined
  for how in add edit; do
    commit_octopus_merge_with_secret "octopus-$how" "$how"
    remerge=$(git log -1 --patch --diff-merges=remerge --format=%s)
    [[ $remerge == *"Skipping remerge-diff for octopus merges"* ]] ||
      fail "Git has a remerge diff for an octopus merge now"
    combined=$(git show --diff-merges=dense-combined --format= HEAD)
    [[ $combined == *"$(secret)"* ]] || fail "the merge lacks the secret"
    if git grep -qF "$(secret)" HEAD^1 HEAD^2 HEAD^3; then
      fail "a parent of the merge holds the secret"
    fi

    run_scan history
    assert_status 0
    assert_output_contains "no leaks found"
  done
}

# The scan reads the history of the repository and nothing of a submodule. The
# secret here is in the history and in the work tree of the submodule, and the
# commit of the repository holds only the commit ID of the submodule. This case
# pins a limit that the page lists: each repository needs its own scan.
case_submodule_content_is_not_scanned() {
  new_repository submodule-source
  commit_secret ci.yml
  local source=$REPO

  new_repository submodule-parent
  git -c protocol.file.allow=always submodule add --quiet "$source" vendor
  git commit --quiet --message "Add the submodule"
  test -f vendor/ci.yml

  run_scan history
  assert_status 0
  assert_output_contains "no leaks found"

  git -C vendor checkout --quiet --detach HEAD
  git add vendor
  run_scan staged
  assert_status 0
}

# The file `.betterleaksignore` and the marker `betterleaks:allow` suppress a
# finding with betterleaks only, and gitleaks ignores both. The names of
# gitleaks work with both scanners, and the cases above cover them. The first
# check uses the marker, the second the ignore file.
case_betterleaks_ignore_names_apply_to_betterleaks_only() {
  local expected=1
  if [ "$SCANNER" = betterleaks ]; then
    expected=0
  fi
  readonly expected

  new_repository own-marker
  printf 'ref: %s # betterleaks:allow\n' "$(secret)" >ci.yml
  git add ci.yml
  git commit --quiet --message "Add ci.yml"
  run_scan history
  assert_status "$expected"

  new_repository own-ignore-file
  commit_secret ci.yml
  printf '%s\n' "$(history_fingerprint ci.yml)" >"$REPO/.betterleaksignore"
  run_scan history
  assert_status "$expected"
}

# Runs each case in the list below, or only the cases that the arguments name.
# The cases are independent: each one builds its own repository. The list is
# explicit because the minimal Bash of the Nix sandbox has no `compgen`. Add each
# new case here.
main() {
  local -a cases=(
    case_clean_repository_passes
    case_history_finds_a_committed_secret
    case_history_finds_a_secret_that_a_commit_removed
    case_history_reads_every_branch
    case_history_ignores_a_staged_secret
    case_staged_finds_a_staged_secret
    case_staged_ignores_an_unstaged_secret
    case_staged_ignores_a_committed_secret
    case_staged_runs_from_a_subfolder
    case_gitleaksignore_suppresses_a_committed_secret
    case_gitleaksignore_suppresses_a_staged_secret
    case_gitleaksignore_matches_only_its_fingerprint
    case_allow_comment_suppresses_the_line
    case_repository_configuration_file_is_not_read
    case_output_is_redacted
    case_wrong_arguments_exit_2
    case_outside_a_work_tree_fails
    case_history_refuses_a_shallow_clone
    case_history_refuses_an_unreadable_history
    case_history_refuses_an_object_with_damaged_content
    case_repository_without_commits
    case_linked_worktree
    case_staged_finds_a_secret_added_in_a_renamed_file
    case_staged_finds_a_committed_secret_that_a_rename_moves
    case_a_rename_out_of_a_skipped_path_does_not_hide_a_secret
    case_staged_deletion_passes_and_history_keeps_the_secret
    case_a_file_that_git_treats_as_binary_does_not_hide_a_secret
    case_a_file_with_the_extension_of_a_binary_format_is_not_scanned
    case_history_finds_a_secret_in_a_file_that_replaced_a_symbolic_link
    case_a_replace_reference_does_not_hide_a_commit
    case_colour_settings_of_the_user_do_not_hide_a_secret
    case_settings_of_the_caller_in_the_environment_stay
    case_textconv_filter_does_not_hide_a_secret
    case_git_config_parameters_of_the_caller_do_not_override_the_pins
    case_git_dash_c_options_of_a_calling_alias_do_not_override_the_pins
    case_a_diff_that_git_cannot_produce_is_refused
    case_diff_driver_binary_and_big_file_threshold_do_not_hide_a_secret
    case_driver_names_with_quote_characters_are_pinned
    case_rename_limit_warning_does_not_stop_the_scan
    case_history_finds_a_secret_in_a_conflict_resolution
    case_history_does_not_report_a_merged_branch_again
    case_octopus_merge_is_not_scanned
    case_submodule_content_is_not_scanned
    case_betterleaks_ignore_names_apply_to_betterleaks_only
  )
  # Names on the command line replace the list: run one case while you work.
  if [ "$#" -gt 0 ]; then
    cases=("$@")
  fi
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
