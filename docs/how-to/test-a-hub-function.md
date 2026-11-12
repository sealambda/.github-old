# Test a hub function

Add a test case for a function that the flake exports in `lib`, or run the
cases that exist. A case builds the function on a fixture and asserts that the
check passes, or that it fails with a message that names the problem.

## Before you start

- The function is in `nix/lib` and `flake.nix` exports it in `lib`.
- You can run `nix build` in the repository.

## Run the cases

Run one flake check for all cases:

```console
nix build .#checks.<system>.lib-functions -L
```

`nix flake check` runs the same check. The check builds one derivation for
each case. The name of a derivation is `lib-` and the name of its case, so a
failed build names the fixture in its first line:

```text
error: Cannot build '/nix/store/<hash>-lib-docs-broken-link-fails.drv'.
> ERROR: testBuilderLogEntries: original builder log does not contain 'missing-page.md'
```

The second line is what the case expected and didn't find. A case that must
pass fails with the log of the check itself.

## Add a case

Each function has a case file in `nix/tests/lib`, named like its `nix/lib`
file, such as `docs.nix`, `decisions.nix` and `treefmt.nix`. The file
`standards.nix` holds the cases of `mkStandards`, which composes the other
functions.

1. Open the case file of the function. The case file holds a function from
   `pkgs`, `hub` (the `lib` of the flake) and `harness` to an attribute set of
   cases.
2. Add a case named `<function>-<situation>`, for example
   `docs-broken-link-fails`. Write one comment above it that states the
   requirement that the case asserts. A case name is unique across the case
   files: a name that two files use fails the evaluation of the check.
3. Build the fixture with `harness.mkTree`. The fixture is a store path that
   holds the files that you give as text, so no tracked file of the repository
   is a bad example. Set `synced = true` for the tool configuration that
   `sync-config` writes, and `setup` for a change that text can't say, such as
   a removed file.
4. Set `check` to the function applied to the fixture. For a case that must
   fail, also set `expectedLog` to the text that the log of the failure must
   hold: the name of the file or the rule that the message names. An empty
   list is an error, because the case would pass for any failure. An entry
   that's a bare file name can match the store path of the fixture, so give
   the entry a slash before the name, or keep the name out of the fixture.

   ```nix
   docs-broken-link-fails = {
     check = docsCheck (project "broken-link" { "README.md" = "[x](missing-page.md)\n"; });
     expectedLog = [ "missing-page.md" ];
   };
   ```

   A case file can also build its cases from a list, as `config.nix` does for
   each file that `sync-config` writes. Write the list in the case file from
   the requirement. Don't take it from the function's own data: a file that
   the function drops would then drop its case. Add one case that compares
   what the function writes with the literal list, so both a dropped
   comparison and a dropped list entry turn a case red.

5. Run the cases, as in the section above.

An evaluation error can't be a case with `expectedLog`, because that reads the
log of a failed build, and an error of the evaluation leaves no log. Decide
such a case in Nix instead. Test the text of a message on the pure function
that builds it, and test that a call fails with `builtins.tryEval`. Pass the
result to `harness.mustHold`, which builds when its condition is true and
fails the evaluation with your message when it's false. Pair a call that must
fail with a call that must work, so the failure comes from the part under test.
`nix/tests/lib/standards.nix` shows both forms. To read the hooks of an
evaluation of `lib.mkHooks`, call `harness.hookIds` and `harness.hookEntry`.
They hold the shape of its configuration in one place.

```nix
standards-unknown-argument-stops-the-evaluation = {
  check = mustHold "A call with the argument foo was accepted, or a valid call failed." (
    evaluates (standards { }) && !evaluates (standards { foo = 1; })
  );
};
```

The hub's own `decisions` check reads the case files. A fixture that holds a
citation of a record or a path of a page must build the text from parts, as
`nix/tests/lib/decisions.nix` does. Otherwise the check resolves the citation
in the hub and fails.

## Add a function

Add `nix/tests/lib/<function>.nix`, with the same arguments as the other case
files, and list it in `caseFiles` in `nix/tests/lib/default.nix`.

## Check that a case can fail

A case proves nothing until it has failed once. Change one `expectedLog` entry
to a text that the log doesn't hold, run the cases, and read the error. The
derivation `lib-<case>` fails and the log says which entry is missing. Restore
the entry.

## If it fails

- **The log lacks an entry that you expect.** Run `nix log` on the derivation
  `lib-<case>-subject` to read the output of the function. Change the entry or
  the fixture.
- **The log says `The builder did not fail, but a failure was expected!`.**
  The derivation `lib-<case>-subject` prints this when the function accepted
  the fixture.
  Either the fixture isn't bad or the function has a gap. Fix whichever is
  wrong.
- **A case that must pass fails.** The log of the derivation `lib-<case>` is the
  output of the check. Fix the function or the fixture.

## Related

- The tester is `pkgs.testers.testBuildFailure'` of nixpkgs: it runs a build
  that must fail, then checks the exit status and the log.
- [Adopt the hub in a repository](adopt-the-hub.md) describes the functions that
  a consumer calls.
- [Run the synthetic consumer](run-the-synthetic-consumer.md) builds the checks
  of a repository that calls them.
