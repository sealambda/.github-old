# Secrets scan

The command `secrets-scan` runs a secret scanner on a Git repository with the
hub's base configuration. The hub gives it to every repository as
`lib.mkSecretsScan`, as the package `secrets-scan`, and in the `base` dev shell
that every other shell includes. The default scanner is gitleaks, and the
scanner is one argument of the function.

## Commands

| Command | What it scans | Where it runs |
| ------- | ------------- | ------------- |
| `secrets-scan history` | Every commit that the repository's refs reach, all branches included. | A CI step. |
| `secrets-scan staged` | The changes in the index. | The `pre-commit` hook. |

Both commands run at the top of the work tree, so a hook that starts in a
subfolder finds the secrets and the `.gitleaksignore` file all the same. Any
other arguments are a usage error.

Both commands check what Git gives the scanner before they scan, and they scan
nothing when the check fails. A scanner reports "no leaks" for each case below,
and the result would look clean and mean nothing:

- A shallow clone lacks the older commits. `history` exits with status 3 and
  names the two fixes: `fetch-depth: 0` on `actions/checkout`, or
  `git fetch --unshallow`. `staged` reads the index and no history, so it needs
  no such check.
- Git can't produce the diff that the scanner reads. The command runs the Git
  command that the scanner runs, with the output discarded and with the pinned
  settings of the next section: `git log -p -U0` with the options of the scan
  for `history`, and `git diff -U0 --no-ext-diff --staged .` for `staged`. It
  exits with status 4 when the command exits with a status other than 0, or
  writes any message to standard error. Git names the cause on standard
  error, and the command prints it. The causes include a missing or damaged
  object, a setting that makes Git fail, such as `diff.orderFile` with a file
  that doesn't exist (status 128), and a value that Git can't parse and only
  warns about, such as `diff.dirstat = bogus` (status 0). gitleaks exits 0 with
  "no leaks found" for all of them, and after a warning of Git it scans no
  commit at all. `betterleaks` exits 1 with a log line, the status of a
  finding. A walk with `git rev-list --objects --all` isn't enough for a
  history: it only checks that each object exists, so it passes a blob that
  holds garbage. `git cat-file --batch` and `git rev-list --verify-objects` read
  the content, but they exit 0 for some damaged objects.
- A merge commit of three or more parents has no diff that the scanner can
  read. `history` exits with status 4 and names the commits: see
  [Merge commits](#merge-commits).

The check reads the diff twice. On a synthetic history of 3301 commits, 300 of
them merge commits, with 15423 objects in a 3.2 MiB pack, `secrets-scan history`
takes 0.34 s, and gitleaks alone takes 0.17 s with the same options. On the
history of the hub, with 52 commits and 5650 objects, it takes 0.18 s against
0.13 s. The measurements ran on one machine with Apple silicon, Git 2.56.0 and
gitleaks 8.30.1, and each time is the median of seven runs. The check reads the
history once more, so the cost grows with the size of the history. With `--text`
a history of large binary files makes a long diff: the `git log -p` of the check
takes 0.25 s on 5 commits with 37.7 MiB of random binary files, a diff of 40 MB,
on the same machine. The scan of such a history takes 250 s with gitleaks, as the
section about binary files says, so the scanner is the cost there and the check
adds 0.1 percent. A repository with no commit has no history, so `history`
passes.

### Exit status

| Exit status | Meaning |
| ----------- | ------- |
| 0 | No finding. |
| 1 | A finding, or a failure of the scanner. The scanner uses 1 for both, and the output says which. |
| 2 | A usage error. |
| 3 | `history` on a shallow clone. Nothing is scanned. |
| 4 | Git can't produce the diff that the scan reads: a history with a missing or damaged object, or a setting that makes Git fail or warn. Also `history` on a history with a merge commit of three or more parents. Nothing is scanned. |
| Other | A failure of `git`, such as 128 outside a work tree. |

### The Git output that the scan reads

A scanner runs `git log -p` for `history` and `git diff --staged` for `staged`,
and it reads the diff in the output. The command pins the settings that change
that output, whatever the configuration of the user says:

- `color.ui` and `color.diff` are `never`. With `always` in either one, gitleaks
  reads the coloured diff as empty and exits 0 after it reports no leaks. The
  command doesn't touch the colour of its own output: that's the flag
  `--no-color`.
- Every `diff.<driver>.textconv` filter that a configuration file or the
  environment defines is `cat`. A `.gitattributes` line such as `*.yml diff=x`
  selects a driver, and a filter that prints nothing hides the file from
  gitleaks. A filter that exists only on the machine of a user has an effect
  only there.
- `GIT_NO_REPLACE_OBJECTS` is `1`. A `refs/replace` reference makes Git show
  another object in place of a commit, and gitleaks then scans the replacement
  and not the commit. A mirror clone brings these references. `betterleaks` sets
  the variable itself.

The command adds these settings to the end of the variable
`GIT_CONFIG_PARAMETERS`, in the form `'key'='value'` that `git -c` writes. Git
reads that variable after every configuration file and after the variables
`GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_<n>` and `GIT_CONFIG_VALUE_<n>` (`config.c`
of Git 2.56.0), and the last entry for a key wins. So a pin wins over the
configuration files, over those variables and over the `git -c` options of a
caller: a Git alias or a hook that Git starts from `git -c color.diff=always
commit` gets the options in `GIT_CONFIG_PARAMETERS`, and the scan still reads an
uncoloured diff. The command keeps every other entry of the caller, so a setting
such as `safe.directory` still reaches Git. The command doesn't unset the
variable, because that would lose these settings.

A setting that makes Git fail has no pin. `diff.orderFile`, `diff.algorithm`,
`diff.context`, `diff.renames`, `core.abbrev` and others make Git exit with
status 128 when their value is wrong, and a list of pins couldn't be complete.
A pin would also hide the mistake of a user. The check of the previous section
catches every such setting and names it, in every version of Git.

A probe of 91 settings of `diff.*`, `log.*`, `core.*`, `format.*`, `color.*`,
`i18n.*` and a few other sections, with gitleaks 8.30.1 and `betterleaks`
1.9.0, found four kinds of setting that make a scan pass a secret: the colour
settings, `diff.<driver>.textconv`, `diff.<driver>.binary` and
`core.bigFileThreshold`. The command pins the colours and the filters of
`diff.<driver>.textconv`, and the flag `--text` of the next section covers the
`binary` setting and the threshold. The probe also found settings that make Git
fail or warn. The status 4 covers them. No other setting of the probe hides a
secret. `diff.external` has no effect because the scanner
passes `--no-ext-diff` to `git diff`, and `git log -p` runs no external diff
program.

### Files that Git treats as binary

Git prints "Binary files differ" and no line for a file that it treats as
binary, and a scanner finds nothing in such a file. A person who can commit
decides which files are binary:

- A NUL byte in the content.
- The attribute `-diff` or `binary` in a `.gitattributes` file. The line
  `*.txt -diff` is enough to hide every text file.
- The same attributes in `.git/info/attributes`, a file of one clone that no
  commit holds. It has a higher rank than a `.gitattributes` file.
- A diff driver whose `diff.<driver>.binary` setting is true.

Both commands put a `git` first on PATH that adds `--text` after `diff` or `log`
and runs the real Git (`nix/scripts/secrets-scan-git.sh`). With `--text`, Git
prints the lines of every file, whatever the reason for a binary diff was. The
scanner and the check of the previous section both run `git`, so both get the
flag from the same command, and the check reads what the scanner reads. The
scanner must run `git` from PATH, as gitleaks and `betterleaks` do.

The flag has a cost, and it has two side effects:

- The scanner reads the content of every binary file that a commit changes. On
  a history of 3 commits with 10.8 MiB of executables and random data, the diff
  grows from 911 bytes to 12 MB. The scan of the history takes 0.15 s and 42 MiB
  without the flag, and 2.13 s and 103 MiB with it, for gitleaks. For
  `betterleaks` the values are 0.20 s and 29 MiB, and 0.50 s and 65 MiB. On a
  history of 5 commits with 37.7 MiB of such files, the diff grows from 1468
  bytes to 53 MB, and the scan takes 0.38 s without the flag and 250 s with it
  for gitleaks, and 0.47 s and 27 s for `betterleaks`. The time of gitleaks
  grows faster than the size, so a history with many large binary files makes
  the CI scan slow. `staged` reads only the files of the commit, and a change of
  a 3 MiB file takes 1.95 s with gitleaks and 0.34 s with `betterleaks`. The
  measurements ran on one machine with Apple silicon, Git 2.56.0, gitleaks 8.30.1
  and `betterleaks` 1.9.0, and each value is one run.
- A binary file can hold bytes that a rule matches, and the scan reports them.
  The scan of the history with 37.7 MiB of files reported one finding with
  gitleaks: the rule `aws-amazon-bedrock-api-key-short-lived` matched in a copy
  of the `betterleaks` executable, which holds no secret. A fingerprint in
  `.gitleaksignore` suppresses such a finding.
- `betterleaks` scans the content of an archive only in a binary diff. With the
  flag it reads the compressed bytes as text and finds nothing in a compressed
  zip file. Without the flag, it found the secret in one. gitleaks scans no
  archive with or without the flag. A zip file that stores a small file without
  compression holds the secret as plain bytes, and both scanners find it with
  the flag.

The scanner limits don't apply to the flag. The command passes no
`--max-target-megabytes`, and a limit would let a person hide a secret by
padding a file above the limit.

### Other repository content that changes the diff

A probe of the ways that the content of a repository changes what `git log -p`
and `git diff --staged` print, with both scanners, found three more cases that
passed a secret, and the command closes all three:

- A commit that turns a symbolic link into a file. The default filter of the
  scanners, `--diff-filter=tuxdb`, has a `t` that leaves out type changes, and
  the diff of such a commit holds the whole content of the file. The command
  passes `--diff-filter=uxdb`.
- A `refs/replace` reference, described in the list above.
- A commit that moves a file without an edit. With rename detection, Git prints
  `rename from` and `rename to` lines and no hunk, so a scanner reads no line
  of the file. A secret in a file at a path that the scanner skips, such as
  `creds.png`, passes after `git mv creds.png deploy.yml`, and the file at the
  new path holds it. The `git` of the command adds `--no-renames`, which
  overrides `diff.renames`. Git then prints the file at the new path as an
  addition with its whole content, and the scanner reads it. The cost is that a
  moved file is a finding at its new path, with a new fingerprint, even when a
  fingerprint suppresses the finding at the old path. Git also prints no
  warning about `diff.renameLimit` for a change with many renames, because it
  looks for none.

The attributes `working-tree-encoding`, `filter`, `ident`, `export-subst`,
`text`, `eol` and `-text`, a file mode change, a symbolic link, a line of
64 MiB and a file name with a tab, a line break or a fake diff header all leave
the scan unchanged: the scanners find the secret. The diff holds what Git
stores, so an encoding of the working tree has no effect. Two cases stay and
the Limits section lists them: a file in an encoding that the scanner can't
read, such as UTF-16, and the content of a submodule.

### Merge commits

`git log -p` prints no diff for a merge commit, so a secret that only the merge
commit holds passes: the resolution of a conflict that adds it, or a change that
the person who merged made by hand. `history` shows the diff of each merge
commit with `--diff-merges=remerge`. The option shows the difference between
the automatic merge of the parents and the merge commit, so it shows what the
person added and nothing that a merged branch brought. A diff against the first
parent would show the lines of the whole merged branch again, and a fingerprint
of an accepted finding on that branch would not suppress it for the merge
commit. CI on a pull request scans a merge commit that GitHub creates, and its
hash changes with each run, so no fingerprint could suppress such a finding.

The command passes the option in `--log-opts`, which replaces the default
options of the scanners, so the command names `--full-history --all
--diff-filter=uxdb` as well. The filter differs from the default `tuxdb` in the
`t`, as the previous section says. The option adds about 0.1 s to the scan of a
repository with 3300 commits, 300 merge commits and 13000 objects, and about
0.05 s to the scan of the hub. The hub has no merge commit.

A merge commit with three or more parents, an octopus merge, has no `remerge`
diff: Git prints the line `diff: warning: Skipping remerge-diff for octopus
merges.` in place of a diff, so a scanner reads nothing of what the merge
changed by hand. A secret that only such a merge holds would pass with the
result `no leaks found`. So `history` lists the octopus merges with
`git rev-list --min-parents=3 --all` before the scan, and exits with status 4
and the commit IDs when the list isn't empty. It exits with status 4 as well
when Git can't list them. `staged` has no such check.

A finding in a file that the merge left in conflict shows the path with the
prefix `b/`, and its fingerprint has the prefix, as in
`<commit>:b/<file>:<rule>:<line>`. Git prints a line `remerge CONFLICT` in the
diff header of such a file, and both scanners then take the path from another
line.

## Where the scan runs

A flake check sees no Git history, so no flake check of the hub scans a
history. The scan runs in a Git hook and in CI, and CI has two forms that
don't guard the same way:

- The reusable workflow `secrets.yml` scans the whole history with
  `gitleaks git --redact --verbose` in the default dev shell, after a checkout
  with `fetch-depth: 0`. It doesn't call `secrets-scan`, because repositories
  depend on it. It passes no `--config`, so gitleaks reads a `.gitleaks.toml`
  at the top of the repository. The base configuration of the hub has the
  default rules, so the two scans use the same rules in a repository that has
  no such file.
- The hook `secrets-scan` of the hub's [Git hooks](hooks.md) runs
  `secrets-scan staged` at `pre-commit`. A person can skip a hook, so the hook
  stops a secret early, and a scan of the history in CI can catch what the hook
  missed. The workflow `secrets.yml` misses some secrets that the command
  finds, as [The workflow and the command](#the-workflow-and-the-command)
  lists. A secret in a file with the attribute `-diff` passes the workflow.
- A repository can run `secrets-scan history` in its own CI step. It then gets
  the hub's configuration, and a `.gitleaks.toml` of the repository has no
  effect.
- The flake checks `secrets-scan-tests-gitleaks` and
  `secrets-scan-tests-betterleaks` run the command against Git repositories
  that the tests create. They scan no history of the hub.

### The workflow and the command

The workflow runs the scanner on its own. The command checks what Git gives the
scanner and pins the options that decide what the scanner reads, as the
sections above describe. A probe ran the line of the workflow, `gitleaks git
--redact --verbose` with gitleaks 8.30.1, and `secrets-scan history` with Git
2.56.0 on the same repositories. Each repository holds one secret that has the
shape of a GitHub token. The table gives the exit status of each run:

| Repository | The line of the workflow | `secrets-scan history` |
| ---------- | ------------------------ | ---------------------- |
| The secret in a plain text file. | 1, a finding. | 1, a finding. |
| A `.gitattributes` file with `*.txt -diff`. | 0, `no leaks found`. | 1, a finding. |
| A `.gitattributes` file with `*.txt binary`. | 0, `no leaks found`. | 1, a finding. |
| A NUL byte in the file that holds the secret. | 0, `no leaks found`. | 1, a finding. |
| A commit that turns a symbolic link into a file that holds the secret. | 0, `no leaks found`. | 1, a finding. |
| A merge commit that holds the secret in its conflict resolution. | 0, `no leaks found`. | 1, a finding. |
| A shallow clone whose older commit holds the secret. | 0, `no leaks found` after `1 commits scanned`. | 3, nothing scanned. |
| A damaged blob that holds the secret. | 0, `no leaks found` after `0 commits scanned`. | 4, nothing scanned. |
| A missing blob that held the secret. | 0, `no leaks found` after `0 commits scanned`. | 4, nothing scanned. |

The workflow lacks these guards of the command:

- It doesn't pass `--text`, so Git prints no line for a file with the attribute
  `-diff` or `binary` or with a NUL byte, and the scanner finds nothing in it.
- It doesn't pass `--diff-filter=uxdb`, so a commit that turns a symbolic link
  into a file shows no content.
- It doesn't pass `--diff-merges=remerge`, so a merge commit shows no diff, and
  a secret that only the merge commit holds passes.
- It doesn't check that Git can produce the diff, so a history with a missing
  or damaged object passes with `no leaks found`.
- It doesn't refuse a shallow clone. The checkout of the workflow sets
  `fetch-depth: 0`, so the clone is whole. The row of the table applies to a
  `gitleaks git` that runs on another checkout.
- It pins none of the Git settings that
  [The Git output that the scan reads](#the-git-output-that-the-scan-reads)
  lists. The probe doesn't cover them.

So the workflow is a scan of the history with the defaults of gitleaks, and the
result `no leaks found` doesn't show that the history holds no secret in the
cases above. A repository that wants the guards of the command runs
`secrets-scan history` in its own CI step, after a checkout of the whole
history. The command comes from the dev shell that includes the `base` shell of
the hub. The job needs `timeout-minutes`, and the workflow file needs a
`concurrency` group when a pull request triggers it, as
[Workflow checks](workflow-checks.md) says:

```yaml
name: Secrets scan

on:
  pull_request:
  push:
    branches: [main]

permissions: {}

concurrency:
  group: secrets-scan-${{ github.ref }}
  cancel-in-progress: true

jobs:
  history:
    name: Scan the history
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
          persist-credentials: false
      - uses: cachix/install-nix-action@75c75c31ebece974e48ebc36b4ad125bd97bd97b # v31.11.3
        with:
          install_url: https://releases.nixos.org/nix/nix-2.35.4/install
      - name: Run secrets-scan
        run: nix develop -c secrets-scan history
```

The pins of the two actions and the `install_url` are the ones of the hub's
`secrets.yml`. The `install_url` pins the Nix version of the hub's
`versions.json`, as [Toolchain versions](versions.md#nix) describes. Without
it, the action installs the version that its own revision carries. The step
exits with the status of the command, so a finding fails the job.

## Configuration

The base configuration is `config/gitleaks.toml`. It holds `[extend]` with
`useDefault = true`, so the scanner keeps its own default rules and the rule
set follows the scanner version that the hub pins. The command passes the file
with `--config`, and a scanner that gets `--config` reads no other
configuration file. The command also passes these flags, which gitleaks and
`betterleaks` share:

| Flag | Effect |
| ---- | ------ |
| `--redact` | Replaces each secret with `REDACTED` in the output. |
| `--verbose` | Prints each finding. |
| `--no-banner`, `--no-color` | Keep the output plain for a log or a hook. |
| `--staged` | Only for `staged`: scans the index. |

### What a repository can add

A repository suppresses a finding in one of two ways. Both work with gitleaks
and with `betterleaks`.

- A fingerprint on its own line in an ignore file at the top of the work tree.
  A fingerprint names one finding, and a fingerprint for another line, file or
  commit suppresses nothing.
- An `allow` comment on the line of the secret.

Each scanner reads these names:

| Scanner | Ignore file | Comment |
| ------- | ----------- | ------- |
| gitleaks | `.gitleaksignore` | `gitleaks:allow` |
| `betterleaks` | `.gitleaksignore` and `.betterleaksignore` | `gitleaks:allow` and `betterleaks:allow` |

The names of gitleaks work with both scanners. A repository that must work with
either scanner uses them. `.betterleaksignore` and `betterleaks:allow` suppress
nothing in gitleaks.

The fingerprint of a finding in the history is
`<commit>:<file>:<rule>:<line>`. The fingerprint of a staged finding has no
commit: `<file>:<rule>:<line>`. gitleaks prints the fingerprint of each
finding. The default output of `betterleaks` has none, so build it from the
commit, the file, the rule and the line that the finding shows.

```text
0f1e2d3c4b5a69788796a5b4c3d2e1f00f1e2d3c:deploy/ci.yml:github-pat:12
```

### What a repository can't change

- Rules. A `.gitleaks.toml` or `.betterleaks.toml` in the repository isn't
  read, so a repository adds no rule, no allowlist and no entropy setting.
- Flags. The command takes no flag of the scanner.

### Ways a repository switches the scan off

A repository owns the files that the scan reads, and it can silence the scan
with them. This is by design, and the hub doesn't prevent it: review does. A
change to one of these files needs a reviewer who checks that the string is no
secret. A probe of each way, with gitleaks 8.30.1 and `betterleaks` 1.9.0,
gave these results:

| A file or a line in the repository | `secrets-scan` | The `secrets.yml` workflow |
| ---------------------------------- | -------------- | -------------------------- |
| A fingerprint in `.gitleaksignore` | Suppresses that finding, in both modes. The scan reads the file from the work tree, so the file needs no commit. | The same. |
| A `gitleaks:allow` comment | Suppresses the finding on that line. | The same. |
| `[allowlist]` (`paths`, `regexes`) or `[extend] path` in `.gitleaks.toml` | No effect. The command passes `--config`, so the scanner reads no other file. | Suppresses what the allowlist names. The workflow passes no `--config`, and gitleaks reads `.gitleaks.toml` at the top of the repository. |
| `.betterleaksignore` and `betterleaks:allow` | Suppress findings with `betterleaks` only. | No effect: the workflow runs gitleaks. |
| A file with a name that the default rules of the scanner skip, such as `token.png` or `package-lock.json` | The scan skips the file. | The same. |
| A change to the workflow call, to the hook configuration or to the CI step that runs the command | The scan doesn't run. | The scan doesn't run. |

A hook is local and `git commit --no-verify` skips it, so a scan of the history
in CI is what stops a secret that a hook missed. The workflow and the command
guard the history differently, as
[The workflow and the command](#the-workflow-and-the-command) shows.

## Output

A finding names the rule, the file and the line. The scanner redacts the text
that the rule captured, and the rest of the line prints. The flake checks
assert that no scan prints the secret of the test when the secret is in the
content of a file, and that the output holds `REDACTED`.

The redaction covers file content only. Three other places can print a secret,
and the command doesn't filter the output:

- A file name. Both scanners print the path of a finding, so a secret in a
  path prints.
- A commit message. `betterleaks` prints the message of the commit of a
  finding. gitleaks doesn't.
- An invalid entry in `.gitleaksignore`. Both scanners print the entry in their
  warning, so a secret that someone pasted there by mistake prints.

## Limits

- The scan finds what the rules of the scanner match. A clean result doesn't
  prove that a repository holds no secret.
- `history` scans the commits that the clone holds, so it refuses a shallow
  clone (status 3). Both commands refuse (status 4) when Git can't produce the
  diff, for example for a missing or damaged object or for a setting that makes
  Git fail. A CI step fetches the whole history, as `secrets.yml` does.
- `staged` scans the index only. A file that isn't staged isn't scanned, and a
  hook can be skipped with `git commit --no-verify`. A scan of the history in
  CI finds what the hook missed, with the guards of the workflow or of the
  command, as [The workflow and the command](#the-workflow-and-the-command)
  compares.
- `staged` scans the lines that the change adds. A staged deletion adds no
  line, so it passes. The secret that it leaves is in the history, and the scan
  of the history finds it. A staged rename is an addition at the new path, so
  the scan reads the whole file.
- `history` refuses a history that has an octopus merge (status 4), and no
  fingerprint or setting accepts one, so a repository with such a merge can't
  scan its history with the command. `git show --cc <commit>` shows what the
  merge holds that none of its parents has.
- A submodule isn't scanned. `history` and `staged` read the commit ID of the
  submodule in the repository, and neither the history nor the files of the
  submodule. Run `secrets-scan` in the repository of the submodule itself.
- The scan reads a file that Git treats as binary, because of a NUL byte or of
  the attribute `binary` or `-diff`, as text: see the section about binary
  files. These files still pass:
  - A file whose path the default rules of the scanner allow. Both scanners skip
    the extensions of binary formats, such as `.png`, `.bin` and `.exe`, even
    when the file is text. They also skip `node_modules/`, lock files such as
    `package-lock.json`, and files with `gitleaks.toml` in the name. A person
    who can commit chooses the path, so naming a file `token.png` hides its
    secret as the attribute `-diff` did before the command read such files.
    Review of file names is the control.
  - A file in an encoding that the scanner can't read, such as UTF-16, and a
    secret in an encoded form, such as base64.
  - A compressed archive, such as a gzip or a deflated zip file.

  A repository that keeps secrets in such files needs another control.
- A secret in the history stays there after a commit removes it. Rotate the
  secret. A fingerprint only silences the finding.
- The command makes no network call. It doesn't enable the validation of
  findings against live APIs that `betterleaks` offers.

## Replace the scanner

`mkSecretsScan` takes `scanner`, a package with `meta.mainProgram`:

```nix
secrets-scan = hub.lib.mkSecretsScan {
  inherit pkgs;
  scanner = pkgs.betterleaks;
};
```

The scanner must provide the `git` command with the flags above and the flag
`--log-opts`, which replaces the options of `git log` that the scanner uses
otherwise. The options of the command carry the guards for the history: see
[Merge commits](#merge-commits). The scanner must run `git` from PATH so that
the flags `--text` and `--no-renames` of the command reach it, and it must read
`.gitleaksignore`. Its `git` command may start with the global options `-C`,
`-c`, `--git-dir`, `--work-tree`, `--namespace`, `--config-env` and
`--attr-source`, and with options that have their value after an equals sign.
The cases of `nix/tests/secrets-scan.sh` run with gitleaks and with
`betterleaks`, and both pass. These differences of
`betterleaks` 1.9.0 don't break the contract, and a repository that replaces the
scanner meets them:

- Its rule `aws-access-token` reports an access key only when a secret access
  key is on a line within five lines. A lone access key ID passes, and gitleaks
  reports it.
- Its default output has no fingerprint line.
- It scans archives to a depth of 8 by default, and gitleaks scans none. The
  flag `--text` of the command stops that for a compressed archive: see the
  section about binary files.
- It reads `.betterleaks.toml` when it gets no `--config`. The command always
  passes one.
- It gives its own confidence levels to findings, and its rule set differs from
  the gitleaks rule set, so the two scanners don't report the same findings on
  a real repository.
- It prints the message of the commit of a finding, and it also reads
  `.betterleaksignore` and `betterleaks:allow`.

The tests build every repository when they run. The secret that they use has
the shape of a GitHub token, and the test file assembles it from parts, so no
tracked file holds the whole string. That keeps the [leak check](leak-check.md)
clean.

### The history of the hub

The history scan of the hub is clean with gitleaks only. `betterleaks` 1.9.0
reports three low-confidence `generic-credential-uri` findings in the commit
`9a0cb13`: the lines 71 and 86 of `nix/tests/decisions/test_remote.py` and the
line 402 of `nix/tests/decisions/test_retire.py`. Each line holds a URL with
the placeholder owner `acme`, and none is a secret. A switch of the hub to
`betterleaks` first needs a decision on these findings: a fingerprint in
`.gitleaksignore` for each, or other placeholders in the tests. A repository
that switches the scanner runs `secrets-scan history` once and decides what it
reports in the same way.
