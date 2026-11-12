# Git hooks

The hub offers Git hooks that run its own tools at the stages of a commit and a
push. The function `lib.mkHooks` builds them with
[git-hooks.nix](https://github.com/cachix/git-hooks.nix), and
[prek](https://github.com/j178/prek) runs them. The hooks add no rule. They run
the formatter, the [documentation check](wrapped-tools.md), the
[workflow checks](workflow-checks.md), the [secrets scan](secrets-scan.md) and
the [Git policy](git-policy.md) on the machine of the person who commits, so
that a problem shows before CI does. The reasons for the design are in
[ADR 0008](../decisions/0008-offer-git-hooks-through-git-hooks-nix.md).

## What runs

| Stage | Hook id | Command | Runs when | Fails when |
| ----- | ------- | ------- | --------- | ---------- |
| `pre-commit` | `treefmt` | The formatter of the repository, with `--fail-on-change`. | A staged file exists. | The formatter changed a file. The hook has formatted it: stage the result and commit again. |
| `pre-commit` | `docs` | `check-docs .` | A staged file ends in `.md`, or is a configuration file of the documentation tools. | markdownlint-cli2, lychee or Vale reports a problem. |
| `pre-commit` | `workflows` | `workflows .` | A staged file is below `.github/workflows` or `workflow-templates`. | A job has no `timeout-minutes`, or a pull request workflow has no `concurrency` group. |
| `pre-commit` | `secrets-scan` | `secrets-scan staged` | Every commit. | The scanner finds a secret in the staged changes. |
| `commit-msg` | `gitpolicy-commit-msg` | `gitpolicy commit-msg --allow-autosquash` | Every commit. | The header isn't a Conventional Commit. |
| `pre-push` | `gitpolicy-branch` | `gitpolicy branch` | The push carries a commit that the remote lacks. | The name of the checked-out branch isn't `main`, `renovate/<topic>` or `<type>/<slug>`. |

Each hook runs its tool by its path in the Nix store, so the tool is the version
that the hub's `flake.lock` pins, and the hooks need nothing on `PATH`. The
rules of each tool are on its own page. Four facts about the hooks themselves:

- `docs` checks the whole work tree, not only the staged files, because lychee
  also checks the links to files that a changed page names. It runs when a
  staged file is Markdown or a configuration file of the three tools:
  `.vale.ini`, a file below `.vale/`, a file named `.markdownlint-cli2.*` in
  any folder, `lychee.toml` or `.lycheeignore` at the top of the work tree,
  because each of them changes the result for every page. A change that only
  deletes a linked file doesn't run it.
- `treefmt` formats the staged files in the work tree and then fails. What it
  leaves behind depends on the unstaged changes of the file, as
  [What the hooks read](#what-the-hooks-read) explains.
- `gitpolicy-commit-msg` passes `--allow-autosquash`, so `git commit --fixup`
  works while you develop. `gitpolicy range` in CI fails a `fixup!` commit that
  stays in the history, as [Git policy](git-policy.md#commits-that-a-rebase-folds)
  states.
- `gitpolicy-branch` runs only when the push carries a commit that the remote
  lacks. A push without one skips it, so the branch name rule doesn't apply
  to it: a tag on a commit that the remote has, the deletion of a remote
  branch, and a force push that moves a branch back. Git runs no hook at all
  when everything is up to date.

### What the hooks read

prek saves the unstaged changes of the tracked files before it runs the hooks
of a commit, and it restores them afterwards. The hooks read what the commit
holds:

| Hook | Reads |
| ---- | ----- |
| `treefmt` | The staged files, with the staged text. |
| `docs` and `workflows` | The whole work tree: the staged text of the tracked files, and the untracked files that Git doesn't ignore. |
| `secrets-scan` | The index, through `git diff --staged`. Unstaged changes never reach it. |
| `gitpolicy-commit-msg` | The file with the commit message. |

A violation that only an unstaged edit has doesn't fail the commit. A
violation that only the staged text has does, whatever the work tree holds.

prek writes the saved changes to a patch file in its cache folder, not to
`git stash`, and it prints the path. It restores the changes when every hook
passes and when a hook fails. The patch file stays in the folder.

`treefmt` formats the staged file in the work tree and fails, because of
`--fail-on-change`. The index keeps the text that you staged, so stage the file
again and commit. When the file also has an unstaged edit, prek can't apply the
formatting on top of it. It prints `Hook changes conflicted with the saved
unstaged changes. Reverting the hook changes`, and the file keeps your edit
without the formatting. Run `nix fmt` and stage the file.

## Install

The `hooks` dev shell of the hub installs the hooks. Enter the shell once in
each clone:

```console
nix develop .#hooks
```

The installer changes the Git configuration of the clone, so no other shell of
the hub runs it. The `default` shell, which `nix develop` enters without a name,
is `base` and installs nothing, and the CI job `secrets` of the hub, which runs
`nix develop -c gitleaks`, enters that shell. The check `dev-shells` fails when
another shell carries a hook or when `default` isn't `base`.

A repository that consumes the hub builds the hooks with `lib.mkHooks` and puts
the `shellHook` of the result in one dev shell of its own. It passes the
formatter that it already uses, so `nix fmt` and the hook format the same way:

```nix
hooks = hub.lib.mkHooks {
  inherit pkgs;
  src = self;
  treefmt = treefmtFor.${pkgs.stdenv.hostPlatform.system};
};
```

```nix
devShells.hooks = pkgs.mkShell {
  inputsFrom = [ hub.devShells.${pkgs.stdenv.hostPlatform.system}.node ];
  inherit (hooks) shellHook;
};

checks.pre-commit = hooks;
```

Add `.pre-commit-config.yaml` to the `.gitignore` of the repository. The
installer writes a link with that name.

A repository that calls [`lib.mkStandards`](standards-contract.md) gets the same
result as `standards.hooks` and installs it the same way. The function installs
nothing by itself.

Put the `shellHook` in a shell that no other shell includes with `inputsFrom`.
`mkShell` runs the shell hooks of the shells that it includes, so a hook in an
included shell installs the hooks in every repository that builds on it. The
hub's `base` shell has no hook for this reason, and the shells `default`,
`node`, `elixir`, `tofu` and `docs` have none either.

The first entry of a shell with the hook replaces the `core.hooksPath` of each
clone, as [An earlier `core.hooksPath`](#an-earlier-corehookspath) shows. Tell
the people of the repository before you add the hook to a shell that they
already enter.

### What the installer does

The `shellHook` runs two scripts each time that you enter the shell. The first
is a check of the hub. It refuses to go on when Git reads `core.hooksPath` from
outside the repository, as [An earlier `core.hooksPath`](#an-earlier-corehookspath)
explains, and it skips the installation in a repository with no work tree, as
[A repository without a work tree](#a-repository-without-a-work-tree) explains.
The second is a script of git-hooks.nix. It changes nothing when the hooks are
current, and it does these steps when the configuration changed or the hooks are
missing:

1. It checks that the current directory is in a Git repository. It prints a
   warning and stops when it isn't. It doesn't check for a work tree.
2. It links `.pre-commit-config.yaml` at the top of the work tree to the
   configuration in the Nix store, and it adds a garbage-collector root for it.
   It stops with a message when that path holds a regular file: remove the file
   and enter the shell again.
3. It runs `prek uninstall` for each stage, which removes the hooks that prek
   wrote and leaves any other hook.
4. It removes `core.hooksPath` from the local configuration, installs the three
   stages `pre-commit`, `commit-msg` and `pre-push`, and sets `core.hooksPath`
   to the `hooks` folder of the common Git directory. The path is relative
   (`.git/hooks`) in the main checkout and absolute in a linked work tree.

A hook that another tool wrote, such as a lefthook script in
`.git/hooks/pre-commit`, isn't deleted. The installer moves it to
`pre-commit.legacy` in the same folder, and prek runs it after its own hooks
(prek calls this migration mode). The old hook keeps running, and its exit
status counts: an old hook that exits with a status other than 0 fails the
commit. A lefthook script that can't find `lefthook` doesn't do that. It prints
`Can't find lefthook in PATH` and exits with status 0, so the commit passes and
the old hook does nothing. A script that a Nix `lefthook` wrote also holds the
store path of that `lefthook` and keeps working until the garbage collector
removes the path. This is the behavior of lefthook 2.2.2.

The settings go to the shared configuration of the repository, and the hooks go
to the shared `hooks` folder. The link `.pre-commit-config.yaml` belongs to one
work tree. [Work trees](#work-trees) explains what that means for linked work
trees.

### An earlier `core.hooksPath`

Step 4 replaces the local `core.hooksPath`. A clone that kept its hooks in
another folder, such as the `.husky` folder of husky, loses them: Git runs the
hooks of `.git/hooks` and ignores the old folder. The installer
deletes nothing there and doesn't migrate those hooks, so the old scripts stay
in place and stop running. To keep one, copy it into `.git/hooks` before you
enter the shell, where the migration above moves it to `<name>.legacy`, or move
its checks into the hooks of the repository.

A `core.hooksPath` in the system or global configuration makes the shell fail.
prek refuses to install while Git reads hooks from a folder outside the
repository. The installer of git-hooks.nix goes on after that refusal and sets
the local `core.hooksPath` to the `hooks` folder of the repository, which is
empty. That setting hides the outside hooks too, so no hook runs in the clone,
a bad commit message passes, and the shell prints no error. The hub's check
stops this before the installer runs. It reads every `core.hooksPath` that Git
sees, with its scope. A value from the system, global, worktree or command
scope makes the check print the values, the cause and the repair, and end the
shell with status 1. A command such as `nix develop .#hooks -c <command>`
doesn't run the command. The check changes nothing: the local `core.hooksPath`,
the `hooks` folder and the link `.pre-commit-config.yaml` stay as they were,
and the outside hooks keep running. An empty value counts too, as in
`core.hooksPath =` with nothing after the sign. Git runs no hook under it: a
hook in `.git/hooks` doesn't run. prek refuses to install under it. The
message shows the value as `(empty)`.

The hub chose to fail and not to warn and go on. A warning scrolls past, and a
clone without hooks looks like a clone with hooks until a bad commit passes. To
repair it, remove the setting from the configuration that the message names,
and enter the shell again, or use a dev shell that installs no hook, such as
`default`. Nothing else needs a cleanup. Outside a Git repository the check
passes, and the installer prints its own warning.

When Git fails for another reason, such as a configuration file that it can't
parse or a directory that it refuses, the check can't tell whether an outside
`core.hooksPath` exists. It prints the message of Git and ends the shell with
status 1, as it does for a value. Without the check, the installer would print
that it found no repository and the shell would go on with no hook.

### A repository without a work tree

A bare repository and the `.git` folder of a work tree are in a Git repository
and not in a work tree. The script of git-hooks.nix goes on there. It finds no
top-level folder, tries to link the configuration at `/.pre-commit-config.yaml`,
writes the hooks into the Git directory, sets a `core.hooksPath` that no work
tree can resolve, and ends with status 0. The check of the hub asks Git
`git rev-parse --is-inside-work-tree` first. When the answer isn't `true`, the
check prints one line that says the hooks aren't installed because the
directory isn't in a work tree, and the installer doesn't run. The shell goes on
with status 0, the `PATH` doesn't change, and the repository doesn't change. A
global `core.hooksPath` doesn't change this, because there is nothing to
install. Enter the shell in a work tree to install the hooks.

### Remove an old hook

The installer never deletes a `.legacy` file. To drop the hooks of a tool that
the repository no longer uses, such as lefthook, delete the files yourself:

```console
rm "$(git rev-parse --git-common-dir)"/hooks/*.legacy
```

The command deletes every `.legacy` hook, one for each stage that the old tool
installed. Look at `ls "$(git rev-parse --git-common-dir)"/hooks` first if
another tool also left a hook there. Then remove the configuration of the old
tool, such as `lefthook.yml`, in the change that drops the tool.

### Work trees

The hooks and `core.hooksPath` belong to the whole repository, and the link
`.pre-commit-config.yaml` belongs to one work tree. In a repository with linked
work trees (`git worktree`), this has two effects:

- After the installer ran in the main checkout, `core.hooksPath` is the
  relative path `.git/hooks`. Git resolves it from the root of each work tree,
  and a linked work tree has a `.git` file, not a folder. No hook runs in that
  linked work tree, and a commit message that breaks the rule passes.
- After the installer ran in a linked work tree, `core.hooksPath` is the
  absolute path of the shared `hooks` folder, and the main checkout reads the
  same value. Every work tree runs the hooks from that folder. A work tree
  that never ran the installer has no link, and prek refuses every commit there
  with `config file not found: .pre-commit-config.yaml`.

In both cases, enter the shell once in each work tree. Removing a linked work
tree breaks no other work tree: the hooks and the setting stay in the common Git
directory, and each other work tree keeps its own link. The cases
`case_linked_worktree_runs_no_hook_before_its_install` and
`case_linked_worktree_install_is_per_worktree` of `nix/tests/hooks.sh` pin all
of this.

The hub doesn't wrap the `shellHook` to write the absolute path in the main
checkout as well. That path makes every work tree find the hooks, but a work
tree that never entered the shell then refuses every commit with `config file
not found`, including the work trees of people and tools that don't use Nix.
The documented step replaces a refusal that no one expects.

## Skip one hook

`prek` reads the variable `SKIP`: a comma-separated list of hook ids from the
table above. The other hooks still run.

```console
SKIP=docs git commit
SKIP=docs,treefmt git commit
SKIP=gitpolicy-branch git push
```

`git commit --no-verify` and `git push --no-verify` skip every hook.
[CONTRIBUTING.md](../../CONTRIBUTING.md) forbids `--no-verify` and says what to
do when a hook refuses a commit: fix the cause. `SKIP` fixes no cause. The CI
checks run the same tools on the pull request, so a skipped hook moves the
failure to CI.

## Options

| Argument | Meaning | Default |
| -------- | ------- | ------- |
| `pkgs` | The package set of one system. Only its system is used, and the tools come from the hub's nixpkgs. | Required. |
| `src` | The source tree, normally the `self` of the flake. The check `pre-commit` runs on it. | Required. |
| `treefmt` | The evaluation that `lib.mkTreefmt` returns, with the modules of the repository. | `mkTreefmt pkgs [ ]` |
| `extraHooks` | Hooks of the repository, in the format of git-hooks.nix. They add to the hub's hooks. | `{ }` |
| `scanner` | The package of the secret scanner that the hook `secrets-scan` runs. [Secrets scan](secrets-scan.md) lists what it must support. | gitleaks of the hub's nixpkgs |

A name in `extraHooks` that a hub hook uses is an evaluation error that lists the
names. A repository can't replace a hub hook or switch it off in a call. It
skips one with `SKIP`, or it doesn't call the function.

The result is the evaluation that git-hooks.nix returns. These attributes are
the ones that a repository uses:

| Attribute | Use |
| --------- | --- |
| `shellHook` | The text for the `shellHook` of one dev shell. It includes the check of `core.hooksPath`. |
| The derivation itself | `checks.pre-commit`. |
| `config.configFile` | The generated prek configuration, a JSON file in the Nix store. |
| `enabledPackages` | The packages of the hooks. A shell can add them to its packages. |

## The checks of the hub

- The flake check `pre-commit` commits the source in a scratch repository and
  runs `prek run --all-files`. That runs the `pre-commit` stage only, so the
  check never runs `gitpolicy-commit-msg` or `gitpolicy-branch`. It runs the
  formatter, the documentation check and the workflow check over every file of
  the source. It also runs the hook `secrets-scan`, but the scratch repository
  commits the source before the run, so no change is staged and the hook scans
  nothing. The check doesn't gate secrets. A scan of the history in CI can, with
  the guards of the command only, as
  [The workflow and the command](secrets-scan.md#the-workflow-and-the-command)
  says.
- The flake check `hooks-tests` runs `nix/tests/hooks.sh`. Each case installs
  the hooks with the installation script into a new repository and uses real
  Git. The cases cover the installation, a second entry of the shell that
  changes nothing, an old hook that passes and one that fails, an earlier local
  `core.hooksPath`, a global one and an empty one that make the installation
  fail, a Git configuration that Git can't read, the skip in a bare repository
  and in a `.git` folder, the installation in linked work trees, a clean commit
  and one refusal for each hook of the `pre-commit` stage: a badly formatted
  file, a Markdown violation, a workflow without `timeout-minutes` and a staged
  false secret. They also cover the run of `docs` for a configuration file, the
  secret scan of a commit that only deletes a file, what the hooks read when a
  file is staged in part, a bad message, a `fixup!` commit, `SKIP`, a push from
  a branch with a bad name and the pushes that skip the hook. The false secret
  is assembled when the test runs, so no file holds it.
- The flake check `dev-shells` fails when a dev shell other than `hooks`
  carries a shell hook, or when `default` isn't `base`.
- The flake check `lib-functions` has two cases for `extraHooks` and two for
  `scanner`.
- The `consumer` job of the CI builds the check `pre-commit` of the layered and
  the standards synthetic consumers, so a change that a consumer can't build
  fails the job. The legacy consumer doesn't call `mkHooks`, so the hooks change
  nothing for a repository that doesn't opt in.

## Limits

- The hooks are local, and a person can bypass them. `--no-verify`, `SKIP`, a
  clone that never entered the shell and a commit from a tool that doesn't run
  hooks all skip them. The flake checks and `gitpolicy range` run in CI on
  every pull request, so the hooks only show those problems sooner. For
  secrets, a CI scan of the history can catch what a skipped hook missed, but
  only with the guards of the command `secrets-scan history`. The reusable
  workflow `secrets.yml` runs gitleaks without those guards, so a secret in a
  file with the attribute `-diff` passes it:
  [The workflow and the command](secrets-scan.md#the-workflow-and-the-command)
  compares the two forms of that scan.
- The installation is per clone. A new clone has no hooks until someone enters
  the shell. An update of the hub input changes the configuration, and the next
  entry of the shell links and installs it again.
- The link to the configuration is per work tree, and `core.hooksPath` is per
  repository, so each work tree needs one entry of the shell. `mkHooks` can't
  remove the limit and the hub's `shellHook` doesn't work around it, as
  [Work trees](#work-trees) shows.
- The installer replaces a local `core.hooksPath`. Under a system or global one
  the shell fails and installs nothing, as
  [An earlier `core.hooksPath`](#an-earlier-corehookspath) shows.
- `gitpolicy-branch` checks the checked-out branch, not the branch that the
  push names. `git push origin other:refs/heads/Bad_Name` isn't checked. A
  detached `HEAD` is a usage error of the tool, so a push from a detached `HEAD`
  fails until you skip the hook or switch to a branch. CI checks the head branch
  of the pull request.
- `secrets-scan` scans the index. The limits of the scan, such as binary files
  and the history, are on [its page](secrets-scan.md#limits).
- The hooks need `nix-store` on `PATH` to install, which a Nix shell provides.
  They run no network call.
- A rebase replays commits without running `pre-commit` or `commit-msg` for
  them, so the hooks don't check a commit that a rebase changes. `gitpolicy
  range` in CI checks every commit of the pull request, and it fails a merge
  commit.
