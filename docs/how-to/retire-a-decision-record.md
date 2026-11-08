# Retire a decision record

Delete a decision record that no longer holds, and list it in the ledger, with
one command. The command finds the commit of the record's last text, so you
never type a commit hash. It also lists the citations that you must fix.

Do this in the pull request that makes the record dead. The rules are in
[CONTRIBUTING.md](../../CONTRIBUTING.md#decision-records). The reasons are in
[ADR 0004](../decisions/0004-delete-a-replaced-decision-record-into-a-ledger.md).

## Choose retire, correct or reject

| The situation | The action |
| ------------- | ---------- |
| The decision stays, but a detail is wrong, such as a path or an example. | Correct the record and update its `date`. Don't retire it. |
| A new decision replaces the old one. | Write a new record that restates the whole decision. Retire the old record with `--by`. |
| The decision no longer applies and nothing replaces it. | Retire the record with `--withdrawn`. |
| A proposal was refused and its reasoning is useful. | Set `status: rejected` and keep the record. |
| Every reason in a `rejected` record also appears in another record. | Retire it with `--withdrawn`. Nothing is lost. |

## Before you start

- The record is on `origin/main`: its pull request is merged. The ledger links
  to a commit that others can open, so a record that was never merged has no
  entry. Delete such a file with `git rm`.
- Your local `origin/main` is current. The command reads that local ref and
  doesn't fetch. Run `git fetch origin` first.
- The record has no uncommitted change, and its text equals the text on
  `origin/main`. A parent pull request that isn't merged yet may have moved the
  record to another folder. That's fine: the command follows the renames in the
  history of the file, and the ledger entry holds the path that `origin/main`
  has.
- For `--by`, the replacing record is a file in `docs/decisions/` in your
  branch. Write it first, with the next free number.

## Retire the record

1. Run the command in the repository, in any folder inside it. Replace `NNNN`
   with the number of the old record and `MMMM` with the number of the record
   that replaces it.

   ```sh
   git fetch origin
   nix run --inputs-from . hub#decisions -- retire NNNN --by MMMM
   ```

   For a record that no longer applies and has no replacement, run:

   ```sh
   nix run --inputs-from . hub#decisions -- retire NNNN --withdrawn
   ```

   The command needs the `hub` input and runs the pinned revision, as
   [Run a hub app](adopt-the-hub.md#run-a-hub-app) explains.

   A repository without a `hub` input has no pinned revision, so name one. Use a
   full commit hash of the hub that holds the `decisions` app, such as the hash
   that your reviewers approved:

   ```sh
   nix run "github:sealambda/.github/<commit>#decisions" -- retire NNNN --by MMMM
   ```

   When `flake.lock` already pins the hub, read the hash from it:

   ```sh
   nix run "github:sealambda/.github/$(jq -r '.nodes[.nodes.root.inputs.hub].locked.rev' flake.lock)#decisions" -- retire NNNN --by MMMM
   ```

2. Read the output. The command deleted the record with `git rm`, added an
   entry to `docs/decisions/superseded.yaml`, staged the ledger, and printed the
   permalink and the findings of the check:

   ```text
   retired record NNNN: <the title of the record>
   permalink: https://github.com/<owner>/<repo>/blob/<commit>/docs/decisions/NNNN-<slug>.md
   the check reports 2 finding(s) to fix:
   <path>:<line>: decision record NNNN was deleted into the ledger: cite its successor, ADR MMMM
   ```

   The command exits with status 0 when it retires the record, even when
   findings remain. If the output says that the final check didn't run, the
   record is retired all the same. Fix the cause that the output names, then
   run `nix flake check`.

3. Fix each finding. Each one is a citation of the retired record outside the
   ledger and its successor. Cite the successor as `ADR MMMM`, a form that the
   check recognizes. For a withdrawn record, remove the citation. The text must
   still be true after your edit.
4. Open the permalink and check that it shows the last text of the record.
5. Run `nix flake check`. The `decisions` check must pass.
6. Stage your edits of the citations, then commit. The command already staged
   the deletion of the record and the ledger, so a commit without `-a` keeps
   both. Put the deletion, the ledger and the fixed citations in the same pull
   request that makes the record dead.

The command changes the successor of every ledger entry that named the retired
record. Those entries now name `MMMM`.

## If the command refuses

The command checks everything before it changes a file. When it refuses, it
exits with status 2 and changes nothing.

| The message says | The cause and the fix |
| ---------------- | --------------------- |
| `origin/main does not exist here` | The repository has no local `origin/main`. Run `git fetch origin`. |
| `has never been on origin/main` | The record isn't merged, or your local `origin/main` is old. Run `git fetch origin`. If the record isn't merged, delete it with `git rm`. |
| `has uncommitted changes` | Commit or restore the record, then run the command again. |
| `differs from origin/main` | The record in your branch isn't the text on `origin/main`, so the permalink would show other text. Rebase onto `origin/main`, or restore the record. |
| `is already in the ledger` | The record was retired. Nothing to do. |
| `is not a record in force` | `--by` names a record that has no file. Write the replacing record first, and name a record that's in the folder. |
| `is the successor of` | Entries of the ledger name this record as their successor, so a withdrawal would leave them without a live record. Retire it with `--by`, or edit those entries by hand. |
| `not a github.com repository URL` | The `origin` remote isn't a GitHub URL. The permalink needs one. The message hides any user name or token in the URL. |
| `cannot rewrite the successor` | A ledger entry uses a YAML form that the command can't edit as text. Rewrite the entry in the usual block form, then run the command again. |
| `the ledger is not valid` | Fix the findings that the message lists first. Run `decisions check` to see them. |

If `git rm` or `git add` fails after the command writes the ledger, the command
restores the ledger and the record, in the index and in the work tree, and says
so. The tree is then as it was. If a restoration fails too, the message names
the command that finishes it.

The [decision records reference](../reference/decision-records.md#retire-command)
defines the command, its rules and its exit status.
