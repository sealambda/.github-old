---
status: proposed
date: 2026-11-12
decision-makers: Sealambda maintainers
---

# Check commits and branches with a hub tool instead of conform

## Context and Problem Statement

The organization requires Conventional Commits and branch names of the form
`<type>/<slug>`. [ADR 0001](0001-hub-as-single-source-of-standards.md) makes the
hub the one source of standards, so one implementation of these rules must serve
every repository. The program `conform` enforces commit policies, and the hub's
locked nixpkgs has it. Can the hub use it as the shared implementation?

The hub looked at `conform` 0.1.0-alpha.29, the version in its locked nixpkgs.
Three facts decide the question:

- The command `conform enforce` has no option for a configuration file. Its
  options are `--base-branch`, `--commit-msg-file`, `--commit-ref`,
  `--revision-range` and `--reporter`. Run in a folder without `.conform.yaml`,
  it stops with `open .conform.yaml: no such file or directory`. Every
  repository would hold a copy of the configuration, and the hub couldn't
  change a rule for all of them with one update of `flake.lock`.
- The command has no option for a branch name, so the branch rule needs another
  tool anyway.
- A flake check sees no Git history and no branch name, so the rules can't
  be a pure flake check, whichever tool holds them.

## Decision Drivers

- One implementation in the hub, with no copy of its configuration in a
  consumer.
- One list of types for commits and branches.
- A change of a rule reaches every repository with one update of the hub input.
- The rules are testable without Git, and the Git reading is testable on real
  repositories.
- Few lines of code that a maintainer must own.

## Considered Options

- Use `conform` with a configuration file in each repository
- A Python tool in the hub, `gitpolicy`

## Decision Outcome

Chosen option: "A Python tool in the hub" because it reads no configuration
file, so the hub holds the rules once, and because it checks branch names,
which `conform` doesn't.

The tool is the package `nix/scripts/gitpolicy`. Two pure functions hold the
rules, `check_commit_message` and `check_branch_name`, and one constant holds
the types for both. The hub's CI runs `gitpolicy range` and `gitpolicy branch`.
A repository can run `gitpolicy commit-msg` from a `commit-msg` hook that it
installs: the hub ships no hook. The hub exports the tool as
`lib.mkGitPolicyTool`, as `packages.<system>.gitpolicy` and as the app
`gitpolicy`. The rules run where Git is present, in CI and in a hook, not in a
flake check, and the flake check `check-gitpolicy-tests` tests them. The hub's
CI job `git-policy` runs the tool on every pull request.

[Git policy](../reference/git-policy.md) lists the rules.

### Consequences

- Good, because a rule changes in one place, and a consumer takes the change
  with the hub input.
- Good, because commits and branches share one list of types.
- Good, because the rules are pure functions with table tests, and the Git
  reading has tests on temporary repositories.
- Bad, because the hub owns a small parser that `conform` would have
  provided.
- Bad, because the rules run in CI and in a hook that a repository installs,
  so `nix flake check` doesn't show a bad commit message.
- Bad, because the limit of 100 characters can reject a Renovate commit. The
  number is the `header-max-length` of the `commitlint` configuration
  `config-conventional`, not a limit that Renovate sets. The Renovate
  documentation builds the header from the `commitMessage*` options and a
  template, and it states no limit for its length. A maintainer who meets a
  rejected header changes the options of Renovate or the limit, by a new
  record.

### Confirmation

The flake check `check-gitpolicy-tests` runs the tests of the tool: tables for
both rules, the `range` and `branch` commands on temporary repositories, and a
real `commit-msg` hook. The job `git-policy` of the hub's `ci` workflow runs the
tool on every pull request, and the job `ci` fails when it fails.

## Pros and Cons of the Options

### Use `conform` with a configuration file in each repository

- Good, because it's an existing program with commit rules that need no code
  in the hub.
- Bad, because it reads only `.conform.yaml` in the working directory, so each
  repository holds a copy of the rules.
- Bad, because it has no branch-name rule.
- Bad, because its version in nixpkgs is an alpha release.

### A Python tool in the hub

- Good, because the hub holds one copy of the rules.
- Good, because it covers commits and branches with one list of types.
- Bad, because the hub maintains the code and its tests.

## More Information

- [Git policy](../reference/git-policy.md)
- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)
- [`commitlint` `config-conventional`](https://github.com/conventional-changelog/commitlint/blob/master/%40commitlint/config-conventional/src/index.ts)
- [conform](https://github.com/siderolabs/conform)
- [Renovate: semantic commits](https://docs.renovatebot.com/semantic-commits/)
