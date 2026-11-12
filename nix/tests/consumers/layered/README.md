# Layered consumer

This folder is a repository that takes the documentation rules from the hub and
holds no copy of them. Its flake calls `mkTreefmt`, `mkDocsCheck`,
`mkDecisionsCheck` and `mkWorkflowsCheck`, and it has no `config-in-sync` check.

The folder adds two things to the hub's rules. The file `.vale.ini` lists the
vocabulary `Repository`, which holds the term Dialyxir, and Vale's dictionary
doesn't know that term. The file `.markdownlint-cli2.yaml` switches off the rule
for heading levels, and the page `guide.md` skips a level.

The check `docs` can't show that the hub's base is in: without the base, each
tool lints less, and the pages of this folder still pass. The check
`docs-hub-base` shows it. It lints the files of this folder with one more page
that breaks a rule that only the base holds, and it passes only when the check
fails on all three findings: the Vale style `Sealambda`, the markdownlint
option `noInlineConfig` and the lychee option `include_fragments`.
