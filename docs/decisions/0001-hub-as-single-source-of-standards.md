---
status: accepted
date: 2026-11-02
decision-makers: Sealambda maintainers
---

# Keep the organization's standards in one hub with two distribution mechanisms

## Context and Problem Statement

Several Sealambda repositories need the same toolchain versions, formatter
settings, Renovate policy, documentation rules and CI steps. Each repository
kept its own copy, and the copies drifted. How do the repositories share one
definition and stay aligned without a custom tool to manage it?

## Decision Drivers

- One definition of each standard, with one place to change it.
- Only documented, maintained mechanisms of the tools themselves.
- A consumer controls when it adopts a change, and Renovate proposes it.
- No code that a maintainer must own besides a few lines of glue.

## Considered Options

- Copy the files by hand
- Build a tool that resolves and enforces versions
- Use native references and synced files

## Decision Outcome

Chosen option: "Use native references and synced files" because every tool the
organization uses offers one of the two, and neither needs a custom engine.

The hub, this repository, uses the native reference of each tool where it has
one, and a synced file where it has none:

1. **Native reference.** The consumer points at the hub, and its own lock or
   `uses:` SHA is the pin:
   - A Nix flake input, `hub`, gives the dev shells and `lib.mkTreefmt`. With
     `nixpkgs.follows = "hub/nixpkgs"`, the consumer evaluates the hub's
     `nixpkgs` revision.
   - A Renovate preset, `github>sealambda/.github`, gives the update policy.
   - Reusable workflows give the CI steps.
2. **Synced file.** Some tools read only a file in the repository:
   markdownlint-cli2, lychee, Vale and EditorConfig. The `sync-config` flake app
   copies the hub's files into the repository. The `config-in-sync` flake check
   fails when a copy differs from the hub.

A toolchain version is the name of a nixpkgs attribute in `flake.nix`. Library
versions stay in the lock file of each application.

### Consequences

- Good, because a change to a standard is one pull request in the hub.
- Good, because Renovate carries the change to each consumer as a normal
  dependency update.
- Good, because the hub has no version engine to maintain.
- Bad, because a synced file needs one extra command, `sync-config`, after each
  hub update.
- Bad, because a consumer cannot edit a synced file. A new setting belongs in
  the hub, for every repository, or in a file that the tool reads besides the
  synced one, such as the Vale `Repository` vocabulary.

### Confirmation

`nix flake check` runs the `config-in-sync` check in the hub and in each
consumer that adds it. The hub's `flake-check` job runs it, and the hub's `ci`
workflow calls the hub's own reusable workflows as a consumer does.

## Pros and Cons of the Options

### Copy the files by hand

- Good, because it needs no tooling.
- Bad, because the copies drift, and nothing reports it.

### Build a tool that resolves and enforces versions

- Good, because it can express any rule.
- Bad, because the organization would own and test a version engine, and nixpkgs
  and Renovate already do this work.

### Use native references and synced files

- Good, because each part is a documented feature of a maintained tool.
- Good, because a drifted copy fails a check.
- Bad, because there are two mechanisms to explain.

## More Information

- [Nix flake inputs](https://nix.dev/manual/nix/latest/command-ref/new-cli/nix3-flake.html)
- [Renovate shared config presets](https://docs.renovatebot.com/config-presets/)
- [GitHub reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows)
- [Adopt the hub in a repository](../how-to/adopt-the-hub.md) shows how a
  repository consumes each part.
