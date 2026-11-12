# Run the synthetic consumer

Check that a change to the hub keeps a repository that adopts the hub green.
The synthetic consumers are the folders below `nix/tests/consumers`: small
flakes that call the functions of the hub as
[Adopt the hub in a repository](adopt-the-hub.md) documents. Each folder adopts
the hub in one shape of
[Adopt the hub in a repository](adopt-the-hub.md#set-up-the-tool-configuration).
The folder `legacy` adopts the hub through the separate `lib` functions and the
synced configuration files, with one page, one decision record and a ledger.
The folder `layered` holds no copy of the hub's configuration: its own
`.vale.ini` and `.markdownlint-cli2.yaml` layer over the hub's base, and it
builds the [Git hooks](../reference/hooks.md) with `mkHooks`. The folder
`legacy` doesn't call `mkHooks`, which shows that the hooks change nothing for
a repository that doesn't opt in. The folder `standards` calls only
`lib.mkStandards`, with the three required arguments, and holds no tool
configuration. The README of each folder lists its files.

A folder is copyable. To try the hub in a scratch repository, copy it and run
`nix flake lock`, because the input URL names the hub on GitHub.

## Before you start

- You can run `nix flake check` in the hub repository.

## Run it

1. Build the checks of each consumer against your work tree. Run these
   commands in the root of the hub repository, one for each consumer:

   ```console
   nix flake check --all-systems --no-write-lock-file --override-input hub "path:$PWD" "path:$PWD/nix/tests/consumers/legacy"
   nix flake check --all-systems --no-write-lock-file --override-input hub "path:$PWD" "path:$PWD/nix/tests/consumers/layered"
   nix flake check --all-systems --no-write-lock-file --override-input hub "path:$PWD" "path:$PWD/nix/tests/consumers/standards"
   ```

   `--override-input hub "path:$PWD"` replaces the hub on GitHub with your work
   tree, uncommitted changes included, and the pins of the hub's `flake.lock`
   apply. `--no-write-lock-file` keeps the run from writing a lock file into
   the folder. `--all-systems` evaluates the outputs of every system that the
   fixture lists, and Nix builds only the checks of your own system.

2. Run the `sync-config` app of your work tree in the `legacy` fixture, and list
   what changes. The `layered` and `standards` fixtures have no synced copy, so
   they have no such step:

   ```console
   cd nix/tests/consumers/legacy
   nix run "path:$(git rev-parse --show-toplevel)#sync-config"
   git status --short .
   ```

   The prefix `path:` makes Nix read the whole work tree. Without it, Nix reads
   the tracked files only, and the app misses a file that you didn't add yet.

The CI job `consumer` runs the check of each consumer and the `sync-config` step
on a hosted runner, with the commands of `.github/workflows/ci.yml`. Change the
commands in both places together. The job uses no secret and holds a read-only
token. It's in the `needs` of the job `ci`, so a red consumer blocks a merge.

## Check the result

Each `nix flake check` command exits with status 0 and prints
`all checks passed!`. The `sync-config` step prints nothing: the app writes the
copies that the fixture already holds. That step overlaps the check
`config-in-sync`, and it also runs the app as a consumer does. `git diff` would
miss a file that the app adds, which is untracked, so the step reads
`git status`.

## If it fails

- **A check names a file of the consumer.** The hub changed a rule and the
  consumer breaks it. Every real consumer that takes this revision gets the
  same failure, so decide how the hub rolls the rule out before you change the
  consumer to pass.
- **`config-in-sync` fails, or the `sync-config` step lists a file.** The check
  exists in the `legacy` fixture only. A file in `config/` changed, or the app
  writes a file that the fixture doesn't hold. Run the second step of the
  section *Run it* to write the new copies, and commit them.

## Add a case

A case is a call of a hub function in the consumer.

1. Add the call to the set that `checks` builds in the `flake.nix` of the
   consumer whose shape the call belongs to, such as
   `nix/tests/consumers/legacy/flake.nix`. Copy the call from the adoption
   page, and don't add an argument that the page doesn't document.
2. If the call needs a file in the consumer, add the file as a real file of
   the folder. The tracked files of the folder are files of the hub too, so the
   hub's own checks run on them, with no exclusion. The file must pass them.
   The hub runs Vale from its root, so its Vale reads the hub's `.vale.ini` and
   not the one of a fixture. The term in the vocabulary of `layered` is in the
   hub's own `Repository` vocabulary as well, and the file
   `.markdownlint-cli2.yaml` of a fixture applies in both runs. If a hub check
   can't accept the file, add the narrowest exclusion that works and list it on
   this page.
3. Run the command of that consumer from step 1 of the section *Run it*.
4. Check that the case can fail. Break the function that the case calls, for
   example by making `mkDocsCheck` run on a path that doesn't exist, run the
   command, read the failure and restore the function.

The flake of the consumer is a second copy of the snippets of the adoption
page, and no check compares the two. A change to a snippet of that page
changes the flake in the same commit, and the reverse.

To test another shape of adoption, add a folder next to the others and add its
command as a step of the job `consumer`.

## Related

- [Test a hub function](test-a-hub-function.md) tests each function against
  fixtures that it must reject. The consumer checks that the functions accept a
  repository that follows the documented steps: it covers the flake API and the
  rules that its own files exercise.
- [Adopt the hub in a repository](adopt-the-hub.md) documents what the consumer
  uses.
