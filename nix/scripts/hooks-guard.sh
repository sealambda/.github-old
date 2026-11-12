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
# prints its own warning. Otherwise the check reads every `core.hooksPath` that
# Git sees, with its scope. It exits with status 0 when no value comes from
# outside the local configuration of the repository. When one does, it prints
# the values, the cause and the repair on standard error, changes nothing and
# exits with status 1. The scopes `worktree` and `command` count as outside too:
# a value of either scope wins over the value that the installer writes. An
# empty value counts as well, and the message shows it as `(empty)`: Git runs
# no hook with an empty `core.hooksPath`, and prek refuses to install under it.

if ! inside=$(git rev-parse --is-inside-work-tree 2>/dev/null); then
  exit 0
fi

if [ "$inside" != true ]; then
  echo "The Git hooks are not installed: this directory is in a repository but not in a work tree." >&2
  exit 2
fi

# Each line is `<scope><TAB><value>`. The command exits with status 1 when
# no value exists.
settings=$(git config --show-scope --get-all core.hooksPath || true)

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
