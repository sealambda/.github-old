# Synthetic consumer

This folder is a repository that adopts the hub with the steps of the hub page
*Adopt the hub in a repository*. Its flake calls `mkTreefmt`, `mkConfigCheck`,
`mkDocsCheck`, `mkDecisionsCheck` and `mkWorkflowsCheck` as a consumer does.
The check `gitpolicy` builds `mkGitPolicyTool` and runs `gitpolicy branch` on
a valid name.

The files `.editorconfig`, `.markdownlint-cli2.yaml`, `.vale.ini`, `lychee.toml`
and the Vale vocabulary `Sealambda` are copies that `sync-config` writes. The
check `config-in-sync` fails when a copy differs from the hub. The vocabulary
`Repository` is empty.

The folder `docs/decisions` holds one record and a ledger of one deleted
record, so the check `decisions` reads both. The record links to the heading
of this page, so the check `docs` resolves a link with an anchor.
