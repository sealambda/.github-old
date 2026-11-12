# Git policy

The tool `gitpolicy` checks commit messages and branch names. A commit header
is a [Conventional Commit][spec], and a branch name is `<type>/<slug>`. The hub
gives the tool to every repository as `lib.mkGitPolicyTool`, as the package
`gitpolicy` and as the app `gitpolicy`. The choice of a hub tool over the
`conform` program is in
[ADR 0006](../decisions/0006-check-commits-and-branches-with-a-hub-tool.md).

## Where the rules run

A flake check can't enforce these rules. A flake source holds no Git history
and no branch name: `self` carries the revision metadata of the source (`rev`,
`shortRev`, `revCount` and `lastModified`), and the check runs in a sandbox
with no repository. The rules therefore run where Git is present:

- The CI job `git-policy` of the hub checks every commit of a pull request and
  the name of its head branch.
- A repository can run the same command in a `commit-msg` hook or in its own
  CI. The hub ships no hook: the command `commit-msg` is there for a
  repository to call from the hook that it installs.

The rules still travel with `flake.lock`, because the command comes from the
hub input. The hub's flake check `check-gitpolicy-tests` tests the rules. It
doesn't run them on the history of the repository.

## Types

One list of types serves commits and branches:

| Type | Use for |
| ---- | ------- |
| `feat` | A new capability. |
| `fix` | A bug fix. |
| `docs` | Documentation only. |
| `refactor` | A change that keeps behavior. |
| `test` | Tests only. |
| `ci` | Workflows and CI configuration. |
| `build` | Build, packaging and dependency changes. Renovate uses it. |
| `chore` | Maintenance that fits no other type. |
| `perf` | A performance change. |

A commit header can also use `revert`. A branch name can't, because a branch
that undoes a change is named for its kind of work, such as `fix/...`. The
constant `CHANGE_TYPES` in `nix/scripts/gitpolicy/vocabulary.py` is the one
source of the list.

## Commit messages

The header is the first line: `type(scope)!: description`.

| Rule | Requirement |
| ---- | ----------- |
| Type | One of the types above, in lower case. |
| Scope | Optional. Lower-case words of letters and digits that one `-`, `_`, `.` or `/` joins, in parentheses, such as `ci` or `nix/lib`. |
| Breaking mark | Optional `!` before the colon. |
| Colon | Directly after the type, scope or `!`, then exactly one space. |
| Description | Not empty, no trailing whitespace and no final period. |
| Length | At most 100 characters in the header. The unit is the Unicode code point, not the byte. |
| Body | The second line is blank when the message has a body. |

The grammar follows the [Conventional Commits 1.0.0][spec] specification:
type, optional scope, optional `!`, colon, space and description, then a body
that starts one blank line after the description. The hub is stricter than the
specification in each of these places, and the specification allows each:

- The specification says that implementations must not treat the elements as
  case-sensitive. The hub requires lower case, so one commit has one spelling.
- The specification names `feat` and `fix` and allows other types. The hub
  fixes the list above.
- The specification allows any noun as the scope. The hub requires the grammar
  in the table, so a scope has one spelling too.
- The specification allows whitespace after the colon. The hub requires
  exactly one space.
- The specification sets no length. The hub sets 100 characters, the limit of
  the `header-max-length` rule in the
  [`commitlint` `config-conventional`][commitlint] configuration.
- The specification says nothing about a final period or trailing whitespace.
  The hub forbids both.

The tool doesn't check the footers, the width of the body or the signature of a
commit. The check covers the header and the blank line only.

Git's default header for a revert, `Revert "<subject>"`, isn't a Conventional
Commit. The message says to write `revert: <description>` instead.

A merge commit fails whatever its header says. The message names the case and
the fix: rebase the branch onto its base, so that the history stays linear. The
"Update branch" button of GitHub creates a merge commit by default. Its rebase
option, or a local rebase, avoids the merge commit. The hook gives the same
advice for the header that `git merge` and `git pull` write, which starts with
the word `Merge` and a space.

A commit whose message isn't valid UTF-8 is a problem of that commit: it has
status 1 and its short hash, and the other commits are still checked. A commit
that declares another encoding in its `encoding` header is read in that
encoding, as Git re-encodes it for output. A commit with an empty message has no
header and fails.

### Commits that a rebase folds

`git commit --fixup` and `git commit --squash` make commits whose header
starts with `fixup!`, `squash!` or `amend!` and a space. These commits are steps
of work that the rebase folds into another commit. They pass in the `commit-msg`
hook with `--allow-autosquash` and fail in `range`, because a commit that
lands must stand alone. A message that passes this way isn't checked further:
it copies the header of the commit that it corrects.

## Branch names

A name is one of these:

- `main`.
- `renovate/<topic>`, the name that Renovate gives its branches by default
  (`branchPrefix` is `renovate/`). The name needs a topic after the prefix.
- `<type>/<slug>`, where the type is one of the types above and the slug is
  lower-case letters and digits that single hyphens join, such as
  `fix/listen-address`. A slug holds no second slash, underscore, dot or
  capital letter.

## Command line

```console
gitpolicy commit-msg FILE [--allow-autosquash]
gitpolicy range A..B
gitpolicy branch [NAME]
```

- `commit-msg` checks the message in `FILE`, the file that Git passes to the
  `commit-msg` hook. Git gives the hook the file before it cleans the message
  up, so the file still holds the comment lines of the editor. The command
  cleans the message as Git does for the mode of the `commit.cleanup` setting,
  which it reads with `git config`:
  - `strip`, and `default` or no setting: removes the comment lines, the text
    after the scissors line, the trailing whitespace of each line and the blank
    lines around the message.
  - `whitespace`: the same, but it keeps the comment lines.
  - `scissors`: the same as `whitespace`, and it removes the text after the
    scissors line.
  - `verbatim`: changes nothing.

  Any other value is a usage error. The command reads the bytes of the file
  and decodes them as UTF-8, and it changes no line end. It splits the lines on
  `\n` only, as Git does. A `\r` before a `\n` is trailing whitespace and goes
  in the modes that strip it, and a `\r` inside a line stays in the line.
  Git's own space characters are the space, the tab, `\n` and `\r`.
  The `range` command reads the stored message the same way, so both commands
  give one answer for one message.

  The string that starts a comment line comes from `core.commentChar` or
  `core.commentString`, which are one setting under two names. The setting can
  have several characters, and the last one that Git reads wins. A missing
  setting gives `#`. The scissors line is that string, a space and the dashes.
  The value `auto` is a usage error with a message that says so: Git picks the
  character when it commits, from the first characters of the lines of the
  message, and it doesn't tell the hook which one it picked. Set a fixed
  character, or set `commit.cleanup` to `verbatim`, which uses no comment
  string. An empty value is a usage error too.

  One difference remains, because the hook can't know how the commit was made.
  Git's default mode is `strip` when an editor edits the message and
  `whitespace` otherwise, such as `git commit --message`. The hook sees no
  difference between the two, so the command uses `strip` when the setting is
  missing. A commit made with `--message` or `--file` keeps a `#` line of its
  body in the stored message, and the hook removes that line before the check.
  The `range` check of the CI job reads the stored message and so sees the
  line. The command also cuts at the scissors line in every mode but
  `verbatim`, because the hook can't see whether `--verbose` wrote it.
- `range` checks every commit that `B` reaches and `A` doesn't, the oldest
  first, merge commits included. It reads the stored messages and strips
  nothing. It runs one `git` command to list the commits and one more for the
  message of each commit. The range needs two dots, and both sides must be
  present and must not start with `-`. A single revision, a range with three
  dots, a range such as `..HEAD` or `<sha>..` (Git reads an empty side as
  `HEAD`) and a side that starts with `-` are usage errors, so that no run
  walks the whole history or reads an option by mistake. The tool passes
  `--end-of-options` to `git`, which needs Git 2.24 or later.
- `branch` checks `NAME`, or the checked-out branch when `NAME` is missing. A
  detached HEAD with no `NAME` is a usage error. An empty `NAME`, as in
  `gitpolicy branch ""`, is a name that was given, so it's a bad name and exits
  with status 1. A `NAME` that starts with `-` needs `--` before it:
  `gitpolicy branch -- --help`. The name is then a bad name and exits with
  status 1. Without `--`, the dash makes it an option.

The commands `range` and `branch` run `git` in the current directory, and
`commit-msg` runs it there to read `commit.cleanup` and the comment string.

Every command accepts `--help` and `-h`, prints the usage to standard output and
exits with status 0. The tool doesn't accept an abbreviation of an option, so
`--he` is a usage error and can't turn into another option later.

### Output and exit status

Each problem prints on its own line to standard output: `FILE: problem` for
`commit-msg`, `<short hash>: problem` for `range` and `NAME: problem` for
`branch`. One run prints all problems. A summary goes to standard error.

| Status | Meaning |
| ------ | ------- |
| 0 | Nothing is wrong. |
| 1 | A message or a name breaks a rule. |
| 2 | A usage error, a file that can't be read, or a failing `git` command. |
| 3 | An internal error: a bug in the tool, with the traceback on standard error. |

The pure functions are `check_commit_message(message, *, allow_autosquash)` and
`check_stored_commit(message, *, is_merge)` in `nix/scripts/gitpolicy/commit.py`
and `check_branch_name(name)` in `nix/scripts/gitpolicy/branch.py`. The second
function checks a commit that Git stores: it fails a merge commit, and it fails
a message that isn't text (`None`). Each function returns a list of problems,
empty for a message or a name that passes.

## The hub's CI job

The job `git-policy` in `ci.yml` runs on pull requests. It fetches the whole
history and runs two steps:

```console
nix run .#gitpolicy -- range "$BASE_SHA..$HEAD_SHA"
nix run .#gitpolicy -- branch -- "$HEAD_REF"
```

`BASE_SHA` and `HEAD_SHA` are the base and head commits of the pull request.
The checkout of a pull request holds a merge commit that isn't a commit of the
branch, so the job names the head commit and doesn't use `HEAD`. A stacked
pull request has the branch below it as its base, so it checks only its own
commits. The second step runs after a failed first step, so one run shows both
problems. The `--` before the name ends the options of the tool: a head branch
that's named `--help` reaches the check and fails as a bad name, and doesn't
print the help and pass.

The job is skipped on a push to `main`. The job `ci` is the one required
status check, and it accepts that skip on a push and nowhere else: on a pull
request the job `git-policy` must succeed, like every other job that `ci`
needs.

## Run it

```console
nix run .#gitpolicy -- range origin/main..HEAD
nix run .#gitpolicy -- branch
```

A repository builds the command with the function that it takes from the hub:

```nix
gitpolicy = hub.lib.mkGitPolicyTool pkgs;
```

The function takes the package set of one system and builds the tool from the
hub's own nixpkgs, whatever nixpkgs the repository follows. The tests of the
tool are the check `check-gitpolicy-tests`. They cover the rules as tables and
the `range`, `branch` and hook commands against temporary Git repositories,
including a real `commit-msg` hook. They also read `CONTRIBUTING.md` and this
page, and they fail when the list of types or the header limit that a page
states differs from the code.

## Limits

- `range` reads all the commits with one `git log` command, so the cost of the
  process doesn't grow with the length of the range. If one message isn't
  valid UTF-8, the tool reads the commits again, one command for each message.
  That path takes about 12 ms for each commit, and only a range with such a
  message takes it.
- `range` can't check a root commit. The range `A..B` leaves out `A` and its
  ancestors, and a root commit has no parent to put on the left. `<root>^..B`
  is a usage error, because Git can't resolve the revision.
- A NUL byte in a message isn't detected. `git commit` refuses such a message,
  but a commit that other tools write can hold one. `git log` ends the message
  at the byte, so `range` checks the text before it only.
- The comment string `auto` has no answer in the hook. See `commit-msg` above.

## Not checked

The tool doesn't check these parts of [Contributing](../../CONTRIBUTING.md):

- The signature of a commit. A signed head commit is the evidence of origin,
  and the hub has no rule that requires signed commits.
- The `Assisted-by` trailer, and the ban on `Co-authored-by` and
  `Signed-off-by` trailers.
- The title of a pull request.
- The width of the body.

[commitlint]: https://github.com/conventional-changelog/commitlint/blob/master/%40commitlint/config-conventional/src/index.ts
[spec]: https://www.conventionalcommits.org/en/v1.0.0/
