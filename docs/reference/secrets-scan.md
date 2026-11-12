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
| `secrets-scan staged` | The changes in the index. | A `pre-commit` hook. |

Both commands run at the top of the work tree, so a hook that starts in a
subfolder finds the secrets and the `.gitleaksignore` file all the same. Any
other arguments are a usage error.

`history` checks the history before it scans, and it scans nothing when the
history is incomplete or unreadable. A scanner reports "no leaks" for both,
and the result would look clean and mean nothing:

- A shallow clone lacks the older commits. The command exits with status 3 and
  names the two fixes: `fetch-depth: 0` on `actions/checkout`, or
  `git fetch --unshallow`.
- A missing object makes the history unreadable. `git rev-list --objects --all`
  walks every object that the refs reach, and the command exits with status 4
  when that walk fails. Git names the missing object on standard error.
  gitleaks exits 0 with "no leaks found" for such a history, and `betterleaks`
  exits 1 with a "partial scan" line, the status of a finding.

`staged` needs neither check, because it reads the index and no history. A
repository with no commit has no history, so `history` passes.

| Exit status | Meaning |
| ----------- | ------- |
| 0 | No finding. |
| 1 | A finding, or a failure of the scanner. The scanner uses 1 for both, and the output says which. |
| 2 | A usage error. |
| 3 | `history` on a shallow clone. Nothing is scanned. |
| 4 | `history` on a history that Git can't read. Nothing is scanned. |
| Other | A failure of `git`, such as 128 outside a work tree. |

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
- A repository can run `secrets-scan history` in its own CI step and
  `secrets-scan staged` in a hook. It then gets the hub's configuration, and a
  `.gitleaks.toml` of the repository has no effect.
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

A repository can suppress any finding with a fingerprint or a comment. The hub
doesn't prevent that, and review does: a change to `.gitleaksignore` or a new
`gitleaks:allow` comment needs a reviewer who checks that the string is no
secret.

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
  clone (status 3) and a history with a missing object (status 4). A CI step
  fetches the whole history, as `secrets.yml` does.
- `staged` scans the index only. A file that isn't staged isn't scanned, and a
  hook can be skipped with `git commit --no-verify`. A scan of the history in
  CI finds what the hook missed, with the guards of the workflow or of the
  command, as [The workflow and the command](#the-workflow-and-the-command)
  compares.
- `staged` scans the lines that the change adds. A staged deletion and a staged
  rename without an edit add no line, so they pass. The secret that they leave
  or move is in the history, and the scan of the history finds it.
- A secret in a binary file passes `history` and `staged`. A file is binary
  when it holds a NUL byte or when a `binary` or `-diff` attribute marks it.
  Both scanners also skip a file with the extension of a binary format, such as
  `.png` or `.bin`, even when the file is text. A repository that keeps secrets
  in such files needs another control.
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

The scanner must provide the `git` command with the flags above, and it must
read `.gitleaksignore`. The same 26 cases of `nix/tests/secrets-scan.sh` run
with gitleaks and with `betterleaks`, and both pass. These differences of
`betterleaks` 1.9.0 don't break the contract, and a repository that replaces the
scanner meets them:

- Its rule `aws-access-token` reports an access key only when a secret access
  key is on a line within five lines. A lone access key ID passes, and gitleaks
  reports it.
- Its default output has no fingerprint line.
- It scans archives to a depth of 8 by default, and gitleaks scans none.
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
