---
status: accepted
date: 2026-11-02
decision-makers: Example maintainers
---

# Keep the fixture small

## Context and Problem Statement

The fixture is a repository that the hub builds on every pull request. A
large fixture costs build time and hides which file a failure comes from.

## Decision Outcome

The fixture holds one record, one page and the synced configuration. The
record exists so that the check `decisions` reads a valid record. It links to
the [page of the fixture](../../README.md#synthetic-consumer), so the check
`docs` resolves a link with an anchor.
