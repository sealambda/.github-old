# Run the synthetic consumer

Check that a change to the hub keeps a repository that adopts the hub green.
The synthetic consumer is the folder `nix/tests/consumers/legacy`: a small
flake that calls the functions of the hub as
[Adopt the hub in a repository](adopt-the-hub.md) documents, with the synced
configuration, one page, one decision record and a ledger. The name `legacy`
means the consumer that adopts the hub through the separate `lib` functions
and the synced files. The README of the folder lists its files.

The folder is copyable. To try the hub in a scratch repository, copy it and
run `nix flake lock`, because the input URL names the hub on GitHub.

## Before you start

- You can run `nix flake check` in the hub repository.

## Run it

1. Build the checks of the consumer against your work tree. Run this command in
   the root of the hub repository:

   ```console
   nix flake check --all-systems --no-write-lock-file --override-input hub "path:$PWD" "path:$PWD/nix/tests/consumers/legacy"
   ```

   `--override-input hub "path:$PWD"` replaces the hub on GitHub with your work
   tree, uncommitted changes included, and the pins of the hub's `flake.lock`
   apply. `--no-write-lock-file` keeps the run from writing a lock file into
   the folder. `--all-systems` evaluates the outputs of every system that the
   fixture lists, and Nix builds only the checks of your own system.

2. Run the `sync-config` app of your work tree in the fixture, and list what
   changes:

   ```console
   cd nix/tests/consumers/legacy
   nix run "path:$(git rev-parse --show-toplevel)#sync-config"
   git status --short .
   ```

   The prefix `path:` makes Nix read the whole work tree. Without it, Nix reads
   the tracked files only, and the app misses a file that you didn't add yet.

The CI job `consumer` runs both steps on a hosted runner, with the commands of
`.github/workflows/ci.yml`. Change the commands in both places together. The
job uses no secret and holds a read-only token. It's in the `needs` of the
job `ci`, so a red consumer blocks a merge.

## Check the result

The first command exits with status 0 and prints `all checks passed!`. The
second command prints nothing: the app writes the copies that the fixture
already holds. The second step overlaps the check `config-in-sync`, and it also
runs the app as a consumer does. `git diff` would miss a file that the app
adds, which is untracked, so the step reads `git status`.

## If it fails

- **A check names a file of the consumer.** The hub changed a rule and the
  consumer breaks it. Every real consumer that takes this revision gets the
  same failure, so decide how the hub rolls the rule out before you change the
  consumer to pass.
- **`config-in-sync` fails, or the second command lists a file.** A file in
  `config/` changed, or the app writes a file that the fixture doesn't hold.
  Run the second command of the section *Run it* to write the new copies, and
  commit them.

## Add a case

A case is a call of a hub function in the consumer.

1. Add the call to the set that `checks` builds in
   `nix/tests/consumers/legacy/flake.nix`. Copy the call from the adoption
   page, and don't add an argument that the page doesn't document.
2. If the call needs a file in the consumer, add the file as a real file of
   the folder. The tracked files of the folder are files of the hub too, so the
   hub's own checks run on them, with no exclusion. The file must pass them.
   If a hub check can't accept the file, add the narrowest exclusion that
   works and list it on this page.
3. Run the first command of the section *Run it*.
4. Check that the case can fail. Break the function that the case calls, for
   example by making `mkDocsCheck` run on a path that doesn't exist, run the
   command, read the failure and restore the function.

The flake of the consumer is a second copy of the snippets of the adoption
page, and no check compares the two. A change to a snippet of that page
changes the flake in the same commit, and the reverse.

The job `consumer` builds the folder `legacy` only. To test another shape of
adoption, add a folder next to `legacy` and add its command as a step of the
job.

## Related

- [Test a hub function](test-a-hub-function.md) tests each function against
  fixtures that it must reject. The consumer checks that the functions accept a
  repository that follows the documented steps: it covers the flake API and the
  rules that its own files exercise.
- [Adopt the hub in a repository](adopt-the-hub.md) documents what the consumer
  uses.
