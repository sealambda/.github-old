# Contributing

This guide is the process guide of the Sealambda organization. It applies to
people and AI agents, in every repository that has no `CONTRIBUTING.md` of its
own. A repository adds its own commands and facts and links here.

## Commits

Each commit is one logical change. Use this form:

```text
type(scope)!: summary in the imperative, at most 100 characters

Why the change exists: the problem, and why this is the fix. Wrap at 72.

Assisted-by: <tool> (<model>)
```

- Follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).
  The type is `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `build`,
  `chore` or `perf`, in lower case. The scope names the area. `!` marks a
  breaking change. The header has no final period.
- To undo a change, write `revert: <description>`. Git's default header,
  `Revert "<subject>"`, isn't a Conventional Commit.
- The tool `gitpolicy` checks these rules. The hub's CI runs it on every pull
  request, and the hub's `commit-msg` hook runs it on your machine after you
  enter the hub's `hooks` shell with `nix develop .#hooks`
  ([Git hooks](https://github.com/sealambda/.github/blob/main/docs/reference/hooks.md)).
  [Git policy](https://github.com/sealambda/.github/blob/main/docs/reference/git-policy.md)
  lists them.
- Say why in the body. The diff shows what.
- **Sign every commit.** Use SSH signing and add the key to GitHub as a
  signing key:

  ```sh
  git config --global gpg.format ssh
  git config --global user.signingkey <path to your public key>
  git config --global commit.gpgsign true
  ```

- When an AI tool helped, add the `Assisted-by: <tool> (<model>)` trailer.
  Never add an AI as `Co-authored-by`. Don't add `Signed-off-by`.
- Never use `--no-verify`. If a hook refuses a commit, fix the cause.
- Each commit passes the repository's checks.

## Pull requests

- One pull request is one change. Split a change that grows past a few
  hundred lines of written code.
- The title is a Conventional Commit. The body follows the pull request
  template.
- Branch names are `<type>/<short-slug>` with a type from the list above, for
  example `fix/listen-address`. The slug is lower-case letters and digits that
  single hyphens join. Two names are the exception: `main`, and `renovate/...`
  for the branches of Renovate.
- Update a branch by rebase. Never merge the base into it.
- Make dependent changes a stack: one pull request per layer, each on the
  branch of the layer below.
- A contribution is under the license that the repository gives to the file
  that it changes. That's the license of the repository, except for a file of
  third-party content, which keeps the license of its source.

## Review and landing

- A code owner who didn't commit to the pull request approves it.
- Fix review findings with fixup commits, so that the reviewer sees each
  change. Then fold them in with `git rebase -i --autosquash`. The CI check of
  the commits fails a `fixup!`, `squash!` or `amend!` commit, so the pull
  request check stays red until you fold them in and push the result. Fold them
  in before you ask for the final approval.
- Land with **Rebase and merge**. `main` stays linear. Nobody pushes to
  `main`.
- To undo a landed pull request, revert its commits in a new pull request.

## Dependencies

[Renovate](https://docs.renovatebot.com/) is the only dependency updater.
Commit lock files. Don't write update scripts.

## Documentation

Follow [Diátaxis](https://diataxis.fr/): tutorials, how-to guides, reference
and explanation are separate pages. Write short sentences in the active voice,
and use one term for one concept.

### Current state only

- A document describes what exists now. Plans and open questions are issues.
  History lives in git and in decision records.
- Delete a dead document in the pull request that makes it dead.
- A design spec (`docs/specs/`) describes work that isn't built yet. The pull
  request that implements a spec moves its verified behavior into reference or
  explanation pages, moves its decisions into decision records, opens issues
  for what remains, and deletes the spec. Code cites the current pages, never a
  spec.
- The Vale rule `Sealambda.CurrentState` fails the `docs` check. The rule
  `Sealambda.History` and the rules of the level warning, such as
  `Sealambda.SentenceLength`, show only in an editor that runs Vale, because the
  check runs Vale with `--minAlertLevel=error`.
  [Writing style](https://github.com/sealambda/.github/blob/main/docs/reference/writing-style.md)
  defines them all.

### Decision records

[Decision records](https://github.com/sealambda/.github/blob/main/docs/reference/decision-records.md)
defines the format of a record and of the ledger. These rules apply:

- Record only an architecturally significant decision, as a
  [MADR 4.0.0](https://adr.github.io/madr/) file named
  `docs/decisions/NNNN-slug.md`. The `status` is `proposed`, `accepted` or
  `rejected`.
- An accepted record is immutable, except for its `status`, its `date` and a
  correction that keeps the decision, such as a renamed path or a removed
  example. A correction updates `date`.
- A changed decision is a new record that restates the whole current decision.
  Delete the old record, and list it in `docs/decisions/superseded.yaml` with
  the commit of its last text and its successor. The `decisions retire`
  command does both, as
  [Retire a decision record](https://github.com/sealambda/.github/blob/main/docs/how-to/retire-a-decision-record.md)
  shows.
- A decision that no longer applies, with no replacement, is deleted into the
  ledger as withdrawn, with `decisions retire --withdrawn`.
- A `rejected` record stays only while it holds reasoning that no other record
  holds.
- A record states a decision, not an inventory. A list that changes, such as
  modules, layers or owners, lives in its source of truth, a code file or a
  reference page, and the record links to it.

The hub explains this deviation from the usual practice of keeping a replaced
record in
[ADR 0004](https://github.com/sealambda/.github/blob/main/docs/decisions/0004-delete-a-replaced-decision-record-into-a-ledger.md).

## Agents

An agent follows this guide and these rules:

- Never push to `main`. Never merge a pull request unless a person asks. This
  rule doesn't cover the Renovate merge of a security fix inside the declared
  range.
- Open pull requests as drafts.
- Disclose AI help with the `Assisted-by` trailer.
- Read a repository's `AGENTS.md` for its commands.
