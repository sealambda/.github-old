---
status: accepted
date: 2026-11-02
decision-makers: Sealambda maintainers
---

# Keep the hub repository public

## Context and Problem Statement

The hub holds standards that the public and private repositories of the
organization consume. Should the hub be a public or a private repository?

## Decision Drivers

- GitHub reads default community files only from a public `.github`
  repository.
- Private repositories must consume the hub without a token.
- The hub needs repository protections and secret scanning.
- The hub must not leak anything sensitive.

## Considered Options

- A public hub
- A private hub

## Decision Outcome

Chosen option: "A public hub" because the default community files and the
consumption without credentials need a public repository, and the content is
a set of standards, not operational data.

The hub holds only generic standards. It names no private repository,
account, role, host, address, customer or incident, and it does not describe
the organization's own systems or deployments. Those records stay in private
repositories. Maintainers appear only as an organization team. A reviewer
rejects a change that breaks one of these rules.

### Consequences

- Good, because GitHub applies the hub's community files to every repository
  of the organization.
- Good, because a private repository calls the hub's reusable workflows and
  reads its flake without a token.
- Good, because the hub gets repository protections and secret scanning.
- Bad, because anyone can read the standards. They are written for that.
- Bad, because a mistake publishes at once, so review and scanning carry the
  weight.

### Confirmation

The `secrets` job of the hub's `ci` runs gitleaks over the whole history of
every change. The reviewer checks the rules above in each pull request.

## Pros and Cons of the Options

### A public hub

- Good, because the default community files apply.
- Good, because consumers need no credentials.
- Good, because the hub can protect itself.
- Bad, because the content is world-readable.

### A private hub

- Good, because the content is not world-readable.
- Bad, because GitHub does not read default community files from a private
  `.github` repository.
- Bad, because consumers would need a token to read it.

## More Information

- [Creating a default community health file](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file)
- [About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
