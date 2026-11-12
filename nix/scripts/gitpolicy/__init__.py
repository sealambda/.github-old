"""Check the commit messages and the branch names of a repository.

The rules are the hub's Git policy: a commit header is a Conventional Commit
with a type from one list, and a branch name is `<type>/<slug>` with a type
from the same list. `gitpolicy.commit` and `gitpolicy.branch` hold the two pure
checks, `gitpolicy.vocabulary` holds the one list of types and the limits,
`gitpolicy.history` reads Git, and `gitpolicy.cli` is the command line. The
contract is in `docs/reference/git-policy.md`.
"""
