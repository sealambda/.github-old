---
status: proposed
date: 2026-11-12
decision-makers: Sealambda maintainers
---

# Offer Git hooks through git-hooks.nix and prek

## Context and Problem Statement

The hub's tools run in CI and in flake checks. A person learns of a problem
after a push: a badly formatted file, a broken link, a commit header that isn't
a Conventional Commit, or a secret in a commit. A secret is the worst case,
because a pushed secret needs a rotation, and the scan of the staged changes
exists to stop it before the commit. Can the hub offer Git hooks that run its
own tools on the machine of the person who commits, without a second copy of
the rules?

[ADR 0003](0003-gate-documentation-with-a-flake-check.md) rejects git-hooks.nix
as the gate of the documentation, because the flake check does the same work
without an extra layer. [ADR 0006](0006-check-commits-and-branches-with-a-hub-tool.md)
says that the hub ships no hook. Both decisions hold. They answer how the hub
gates a change, and a hook doesn't gate anything: a person can skip it. This
record answers a different question, which is how the hub shortens the way to
the first message of a failed check.

## Decision Drivers

- The hooks run the tools that the hub pins, so a hook and CI never disagree.
- A repository that doesn't opt in sees no change.
- A repository adds a hook of its own without a copy of the hub's hooks.
- A hook runs on a machine with Nix and nothing else installed.
- The hub owns little code for the installation of hooks.
- The hooks are testable in the sandbox with real Git.

## Considered Options

- git-hooks.nix with prek, exported as `lib.mkHooks`
- Hand-written hook scripts and `core.hooksPath`
- lefthook
- pre-commit, the Python program
- No hooks

## Decision Outcome

Chosen option: "git-hooks.nix with prek" because it generates the
configuration and the installation script from Nix values, it runs each hook by
its store path, so the tools are the ones that `flake.lock` pins, and its
derivation is a flake check that runs the same hooks over the whole source.

The hub exports these:

- `lib.mkHooks`, which takes the package set, the source, an optional
  formatter evaluation and optional extra hooks, and returns the evaluation of
  git-hooks.nix.
- `devShells.<system>.hooks`, which installs the hooks when a person enters the
  shell with `nix develop .#hooks`.
- `checks.<system>.pre-commit`, which runs the `pre-commit` stage over the whole
  source, `checks.<system>.hooks-tests`, which tests the installation and each
  stage in real Git, and `checks.<system>.dev-shells`, which keeps every other
  shell free of the installer.

The hooks are the formatter, the documentation check, the workflow checks and
the secrets scan at `pre-commit`, `gitpolicy commit-msg` at `commit-msg` and
`gitpolicy branch` at `pre-push`. [Git hooks](../reference/hooks.md) lists them.

The hooks are a convenience, and CI stays the gate. The hub keeps every rule in
its flake checks, `gitpolicy range` and the secrets workflow, and no merge
depends on a hook. This record corrects one sentence of ADR 0006: the hub now
ships hooks. The decision of ADR 0006 stands, because the rules still live in
the tool and the tool still runs in CI. ADR 0003 stands as well: the hooks
add no gate, and the flake check `pre-commit` reuses the tools that the other
checks run.

The hooks are an opt-in. The hub's `default` dev shell stays `base`, so a person
or a CI job that enters it gets the shell that they had, and the installer
never runs there. The `hooks` shell is `base` plus the installer. No shell that
other shells include with `inputsFrom` carries the hook, because `mkShell` runs
the shell hooks of the shells that it includes. A repository that wants the
hooks puts the `shellHook` of `lib.mkHooks` in one shell that nothing includes,
and it chooses whether the shell that people already enter is that shell.

### Consequences

- Good, because a failed check shows at the commit, before CI does, and a
  secret stops before it enters the history.
- Good, because a rule changes in one place. The hooks call the hub's tools,
  so an update of `flake.lock` updates them.
- Good, because a repository that doesn't call `lib.mkHooks` has the same shells
  and checks that it had, and the hub's `default` shell is still `base`. The
  `legacy` synthetic consumer and the flake check `dev-shells` prove it. The CI
  job `secrets`, which enters `default`, runs no installer.
- Good, because the hub's tests run the installation script and the stages in
  real Git, so a change in git-hooks.nix that breaks them fails a check.
- Bad, because the hub adds an input, git-hooks.nix, that follows the hub's
  nixpkgs. A new input is a thing to update and to review, and ADR 0003 gave it
  as a reason against the option.
- Bad, because prek is a younger program than pre-commit, and git-hooks.nix
  takes it through its `package` option. A bug of prek reaches every opted-in
  repository with the next update of the input.
- Bad, because entering the `hooks` shell changes the Git configuration of the
  clone: it replaces the local `core.hooksPath` and writes
  `.pre-commit-config.yaml`. A clone that kept its hooks in another folder,
  such as a husky folder, stops running them. The setting and the hooks go to
  the Git directory that all work trees share, but the link
  `.pre-commit-config.yaml` belongs to one work tree. After an install in the
  main checkout, a linked work tree runs no hook. After an install in a linked
  work tree, every work tree finds the hooks, and a work tree that never ran
  the installer has no link, so prek refuses every commit there. The tests pin
  both outcomes, and a person enters the shell once in each work tree.
- Bad, because a global or system `core.hooksPath` stops prek from installing,
  and the installer of git-hooks.nix then sets the local value anyway, which
  leaves the clone with no hook and no error. The hub's `shellHook` checks for
  such a value first. It prints the cause, changes nothing and ends the shell
  with status 1. A warning would let the shell go on, and a missing hook
  doesn't show until a bad commit passes. The reference page shows how to
  repair it.
- Bad, because the hub's contributors enter a second shell,
  `nix develop .#hooks`, and a clone that only enters `default` has no hooks.
  That's the price of leaving the shell that people already enter untouched.
- Bad, because an existing hook of another tool moves to `<name>.legacy` and
  runs after the hooks of prek. If that tool is gone, the old hook fails the
  commit until a person deletes the file. The installer deletes nothing.
- Bad, because the hooks give a false sense of safety. A person can skip them,
  and a rebase doesn't run them for the commits that it replays. The reference
  page states both limits.

### Confirmation

The flake check `pre-commit` runs the `pre-commit` stage over the source. The
flake check `hooks-tests` installs the hooks in temporary repositories and runs
the cases for a clean commit, one refusal for each hook of the `pre-commit`
stage, a bad message, a `fixup!` commit, `SKIP`, a bad branch name at push, the
installation over an earlier `core.hooksPath`, the refusal under a global,
system, worktree or command `core.hooksPath` and the installation in linked work
trees. The flake check `dev-shells`
fails when a shell other than `hooks` carries the installer. The flake check
`lib-functions` tests `extraHooks`, and the `consumer` job builds the hooks in
the layered synthetic consumer.

## Pros and Cons of the Options

### git-hooks.nix with prek, exported as `lib.mkHooks`

- Good, because it generates the configuration and the installer from Nix, and
  its derivation runs the hooks as a flake check.
- Good, because each hook runs a tool by its store path, so the hooks need no
  `PATH` and the tools are the pinned versions.
- Good, because a repository adds hooks of its own in the same format.
- Bad, because it adds a flake input and a layer that the hub maintains.
- Bad, because the installer changes the Git configuration of the clone.

### Hand-written hook scripts and `core.hooksPath`

- Good, because it needs no input, and the scripts are short.
- Bad, because the hub owns the installation, the bypass variable, the
  handling of an existing hook and the tests for them. git-hooks.nix and prek
  already do this.
- Bad, because a script that runs on every commit must select the files that
  it checks, which prek does with a pattern for each hook.

### lefthook

- Good, because it's a single binary that nixpkgs packages.
- Bad, because the hub would write its own generation of the configuration,
  its installation and the flake check that runs the hooks over the source.
  git-hooks.nix provides all three for prek.

### pre-commit, the Python program

- Good, because it's the reference implementation, and git-hooks.nix uses it
  by default.
- Bad, because it needs a Python runtime. prek is a single binary that reads the
  same configuration, and git-hooks.nix accepts it through its `package`
  option.

### No hooks

- Good, because the hub adds nothing to maintain, and CI is the gate anyway.
- Bad, because a secret reaches the history and a rotation follows, and each
  failed check costs a push and a wait.

## More Information

- [Git hooks](../reference/hooks.md)
- [git-hooks.nix](https://github.com/cachix/git-hooks.nix)
- [prek](https://github.com/j178/prek)
- [lefthook](https://github.com/evilmartians/lefthook)
- [pre-commit](https://pre-commit.com/)
