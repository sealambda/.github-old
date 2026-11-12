# Run the synthetic consumer

Check that a change to the hub keeps a repository that adopts the hub green.
The synthetic consumer is a small flake that calls the functions of the hub as
[Adopt the hub in a repository](adopt-the-hub.md) documents. CI builds its
checks on every pull request, and you can run the same command locally.

## What the consumer is

The folder `nix/tests/consumers/legacy` is a repository in miniature. The name
`legacy` means the consumer that adopts the hub through the separate `lib`
functions and the synced configuration files. It holds:

- `flake.nix` holds the hub input with the URL `github:sealambda/.github`, a
  dev shell, the formatter, and the checks `formatting`, `config-in-sync`,
  `docs` and `decisions`. It uses only what the adoption page documents.
- The synced tool configuration and the empty `Repository` Vale vocabulary are
  real files, as in any consumer.
- `README.md` is the page that the `docs` check lints.

The folder is copyable. To try the hub in a scratch repository, copy it and
run `nix flake lock`, because the input URL names the hub on GitHub.

The tracked files of the folder are files of the hub too, so the hub's own
checks run on them, with no exclusion. A file that fails them isn't a valid
fixture.

## Before you start

- You can run `nix flake check` in the hub repository.

## Run it

Run this command in the root of the hub repository:

```console
nix flake check --all-systems --no-write-lock-file --override-input hub "path:$PWD" "path:$PWD/nix/tests/consumers/legacy"
```

`--override-input hub "path:$PWD"` replaces the hub on GitHub with your work
tree, uncommitted changes included, and the pins of the hub's `flake.lock`
apply. `--no-write-lock-file` keeps the run from writing a lock file into the
folder. `--all-systems` evaluates the outputs of every system that the fixture
lists, and Nix builds only the checks of your own system. The exit status is 0
when every check builds.

To run the `sync-config` app of your work tree in the fixture, and to see
whether a file changes or appears, run these commands:

```console
cd nix/tests/consumers/legacy
nix run "path:$(git rev-parse --show-toplevel)#sync-config"
git status --short .
```

The last command prints nothing when the copies in the fixture and the app
agree. It lists a file that the app changed or added. `git diff` would miss an
added file, which is untracked. The step overlaps the check `config-in-sync`,
and it also runs the app as a consumer does.

The CI job `consumer` runs both steps on a hosted runner. It uses no secret and
holds a read-only token. The job is in the `needs` of the job `ci`, so a red
consumer blocks a merge.

## If it fails

- **A check names a file of the consumer.** The hub changed a rule and the
  consumer breaks it. Every real consumer that takes this revision gets the
  same failure, so decide how the hub rolls the rule out before you change the
  consumer to pass.
- **`config-in-sync` fails.** A file in `config/` changed. Write the new copies
  into the fixture:

  ```console
  cd nix/tests/consumers/legacy
  nix run "$(git rev-parse --show-toplevel)#sync-config"
  ```

- **The step that runs `sync-config` fails.** The app writes files that differ
  from the tracked copies in the fixture. Write the new copies as for
  `config-in-sync`, and commit them.

## Add a case

A case is a call of a hub function in the consumer.

1. Add the call to the set that `checks` builds in
   `nix/tests/consumers/legacy/flake.nix`. Copy the call from the adoption
   page, and don't add an argument that the page doesn't document.
2. If the call needs a file in the consumer, add the file as a real file of
   the folder. The file must pass the hub's own checks without an exclusion.
   If a hub check can't accept the file, add the narrowest exclusion that
   works and list it on this page.
3. Run the command above.
4. Check that the case can fail. Break the function that the case calls, for
   example by making `mkDocsCheck` run on a path that doesn't exist, run the
   command, read the failure and restore the function.

To test another shape of adoption, add a folder next to `legacy` and add its
command as a step of the job `consumer`.

## Related

- [Test a hub function](test-a-hub-function.md) tests each function against
  fixtures that it must reject. The consumer checks that the functions accept a
  repository that follows the documented steps.
- [Adopt the hub in a repository](adopt-the-hub.md) documents what the consumer
  uses.
