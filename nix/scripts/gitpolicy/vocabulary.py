"""The words and limits of the Git policy, in one place.

Commit headers and branch names share `CHANGE_TYPES`, so a branch `fix/x` and
a commit `fix: x` use the same word. The rules that use these values are in
`gitpolicy.commit` and `gitpolicy.branch`, and the page that lists them for a
reader is `docs/reference/git-policy.md`.
"""

# The kinds of change. A commit header and a branch name both start with one.
CHANGE_TYPES: tuple[str, ...] = (
    "feat",
    "fix",
    "docs",
    "refactor",
    "test",
    "ci",
    "build",
    "chore",
    "perf",
)

# The extra type that only a commit header can have. A branch that undoes a
# change is named for its kind of work, such as `fix/...`, so a branch has no
# need for it.
REVERT_TYPE = "revert"

# The types that a commit header can have.
COMMIT_TYPES: tuple[str, ...] = (*CHANGE_TYPES, REVERT_TYPE)

# The types that a branch name can start with.
BRANCH_TYPES: tuple[str, ...] = CHANGE_TYPES

# The prefix of the branches that a bot makes. Renovate names its branches
# `renovate/<topic>`, and the hub cannot rename them.
BOT_BRANCH_PREFIXES: tuple[str, ...] = ("renovate/",)

# The one branch name that has no type: the trunk.
TRUNK_BRANCH = "main"

# The longest header of a commit, in Unicode code points. The number is the
# `header-max-length` of the `config-conventional` preset of commitlint, which
# `docs/decisions/0006-check-commits-and-branches-with-a-hub-tool.md` cites.
HEADER_LIMIT = 100

# The words that `git commit --fixup`, `--squash` and `rebase --autosquash` put
# before the header of a commit that is meant to disappear into another one.
AUTOSQUASH_PREFIXES: tuple[str, ...] = ("fixup! ", "squash! ", "amend! ")

# The string that starts a comment line in a commit message when
# `core.commentChar` and `core.commentString` are not set.
DEFAULT_COMMENT = "#"
