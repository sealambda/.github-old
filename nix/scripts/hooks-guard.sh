#!/usr/bin/env bash
# The check that runs before the installer of the Git hooks.
# `nix/lib/hooks.nix` wraps this file with `writeShellApplication`, and the
# `shellHook` and the installation script of `lib.mkHooks` run it first. The
# exit status tells them what to do:
#
#   0  Run the installer.
#   1  Refuse. The shell ends with status 1 and the installer doesn't run.
#   2  Skip. The installer doesn't run, and the shell goes on.
#
# The installer of git-hooks.nix changes the Git configuration of a clone. When
# Git reads `core.hooksPath` from outside the repository, in the system or the
# global configuration, prek refuses to install and prints a message. The
# installer ignores that refusal and sets the local `core.hooksPath` to the
# empty `hooks` folder of the repository. That setting hides the hooks that the
# outside setting names, no hook runs, and the shell prints no error.
#
# The installer also goes on in a repository that has no work tree, such as a
# bare repository or the `.git` folder of a work tree. It finds no top-level
# folder there, links the configuration at `/.pre-commit-config.yaml` and writes
# a `core.hooksPath` that no work tree can use. A hook needs a work tree, so
# this check skips the installation there (status 2) and prints one line.
#
# Outside a Git repository the check exits with status 0, and the installer
# prints its own warning. When Git fails for another reason, such as a
# configuration file that it can't parse or a directory that it refuses, the
# check can't know what `core.hooksPath` the installer would meet. It prints the
# message of Git, changes nothing and exits with status 1.
#
# Otherwise the check reads every `core.hooksPath` that Git sees, with its
# scope. It exits with status 0 when no value comes from outside the local
# configuration of the repository. When one does, it prints the values, the
# cause and the repair on standard error, changes nothing and exits with
# status 1. The scopes `worktree` and `command` count as outside too:
# a value of either scope wins over the value that the installer writes. An
# empty value counts as well, and the message shows it as `(empty)`: Git runs
# no hook with an empty `core.hooksPath`, and prek refuses to install under it.

# Prints why `git rev-parse` fails in the current directory, in the C locale so
# that the text of the message doesn't depend on the language of the user.
rev_parse_error() {
  { LC_ALL=C git rev-parse --is-inside-work-tree >/dev/null; } 2>&1 || true
}

# Ends the check with status 1 after it prints the cause $1 on standard error,
# then the text $2 when there is one. Pass the message of Git as $2 when the
# call of Git hid it.
refuse_unreadable_git() {
  {
    echo "The Git hooks are not installed: $1"
    echo
    if [ -n "${2:-}" ]; then
      printf '%s\n\n' "$2"
    fi
    echo "The check can't tell whether Git reads a core.hooksPath from outside this"
    echo "repository. The repository is unchanged. Repair the cause and enter this"
    echo "shell again."
  } >&2
  exit 1
}

if ! inside=$(git rev-parse --is-inside-work-tree 2>/dev/null); then
  error=$(rev_parse_error)
  case $error in
  *"not a git repository"*) exit 0 ;;
  *) refuse_unreadable_git "Git fails in this directory." "$error" ;;
  esac
fi

if [ "$inside" != true ]; then
  echo "The Git hooks are not installed: this directory is in a repository but not in a work tree." >&2
  exit 2
fi

# Each line is `<scope><TAB><value>`. The command exits with status 1 when
# no value exists. Any other failing status means that Git could not read its
# configuration, and Git has printed the cause on standard error.
config_status=0
settings=$(git config --show-scope --get-all core.hooksPath) || config_status=$?
if [ "$config_status" -gt 1 ]; then
  refuse_unreadable_git "Git can't read its configuration (status $config_status)."
fi

outside=
while IFS=$'\t' read -r scope value; do
  case $scope in
  local | '') ;;
  *) outside+="  $scope"$'\t'"${value:-(empty)}"$'\n' ;;
  esac
done <<<"$settings"

if [ -z "$outside" ]; then
  exit 0
fi

{
  echo "The Git hooks are not installed: core.hooksPath comes from outside this repository."
  echo
  printf '%s' "$outside"
  echo
  echo "prek refuses to install while Git reads hooks from another folder, and an"
  echo "installer that went on would leave this repository with no hook at all."
  echo "The repository is unchanged. Remove the setting from the configuration of"
  echo "the scope above and enter this shell again, or use a dev shell that"
  echo "installs no hook."
} >&2
exit 1
