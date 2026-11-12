# Leak check

The hub is public, so it holds no private fact of the organization. The flake
check `leaks` scans every text file of the hub and fails when a rule finds
one. It runs with `nix flake check`, locally and in CI, and it needs no
network.

The rules match the shape of a fact, never its value. The hub lists only the
names that are public, in `publicNames` in `flake.nix`, so the list of private
names isn't in the hub.

## Rules

| Rule | What it finds |
| ---- | ------------- |
| `aws-account` | A number of 12 digits that stands alone, plain or in three groups of four with dashes. |
| `aws-resource` | An Amazon Resource Name, a host name below the AWS endpoint domain, and a path-style bucket address. |
| `bucket` | An address with the S3 scheme, a Cloudflare R2 bucket address, the value of a bucket key, and a lower-case name that starts with the organization name and a dash. |
| `runner-label` | A label of a `runs-on` key that isn't a label of a GitHub-hosted runner, a list of labels that has `self-hosted` as an element, and a runner type of the form project, architecture, size. |
| `internal-host` | A host name under a private suffix or a Tailscale network, a private IPv4 address, and a host name below a domain of the organization other than the `www` site. |
| `github-app` | A client identifier of a GitHub App, a numeric App, installation or client identifier next to its key, an installation address, and the commit address of an App. |
| `repository` | The name of a repository of the organization that isn't on the public list, in the short form, in an address, in a flake reference, in a GitHub Pages address or with an escaped slash, a mention of a team that isn't on the public list, and the address of such a team. |

## What each rule reads

### AWS resources

An ARN is a finding, except an ARN with the account `aws`, such as
`arn:aws:iam::aws:policy/ReadOnlyAccess`: AWS owns that policy. A host name
below `amazonaws.com` is a finding, except a host with exactly one label before
the domain, such as `sts.amazonaws.com`: that's the name of a service. A
region, an account or a bucket adds a second label, so that host is a finding.
A path that starts with a letter or a digit after a one-label host, as in the
path-style address `https://s3.amazonaws.com/<bucket>/key`, names a bucket, so
that host is a finding too. The slash of that path may be escaped, as in JSON
or in a URL. A root path or a query, as in `https://sts.amazonaws.com/`, isn't
a finding.

### Buckets

The value of a bucket key is a finding. A key is the word `bucket`, with any
number of word prefixes before it, joined by `_` or `-`, and an optional
suffix `_name`, `-name` or `Name`. The camel-case forms start a new word with
a capital letter. So `bucket`, `bucket_name`, `bucket-name`, `bucketName`,
`state_bucket`, `s3-cache-bucket_name`, `stateBucket` and `stateBucketName`
are keys. A key that uses `_` or `-` takes any letter case, as in
`TF_STATE_BUCKET`. A key is followed by `=` or `:` and a value, in an
assignment, in a mapping or in JSON. The flags `--bucket` and `--bucket-name`
take the value after a space or an equals sign. The quotes around the value
are optional. A value is a bucket name when it has at least three lower-case
letters, digits, dots or dashes. A value that starts with `$` (a variable or
an expression), a Terraform address such as `var.name` or
`aws_s3_bucket.state.id`, and prose that has the word `bucket` but no
separator before a value aren't findings. A word that continues the key, such
as `bucketing` or `state_bucket_arn`, isn't a key.

A value of exactly `true`, `false`, `null`, `none`, `yes`, `no`, `on` or `off`
is a switch, not a bucket name. It takes any letter case, with or without
quotes, and a full stop at the end of a sentence may follow it. So
`create_bucket = true`, `enable_bucket: false` and `use_bucket = "yes"` aren't
findings. A longer word that starts with one of them, such as `trueish` or
`off-site`, is a name and a finding.

### Runner labels

The key `runs-on` takes its labels from these forms:

- A word or a list on the same line, as in `runs-on: ubuntu-latest` or
  `runs-on: [ubuntu-latest, ubuntu-24.04]`. A line can have several keys, each
  in its own code span.
- A flow list that goes on over up to 20 lines, up to its closing bracket.
- The list items on the lines below the key, also when a comment follows the
  key and when the items have the indentation of the key.
- The `group` and the `labels` of a mapping below the key. Their values are
  findings, and the keys aren't.

A line can end with LF or with CRLF. A label of a hosted runner isn't a
finding. The check accepts only the shapes that GitHub documents in the
tables of [GitHub-hosted runners][hosted] and [larger runners][larger], for
any version:

| Family | Shapes |
| ------ | ------ |
| Linux | `ubuntu-latest`, `ubuntu-slim`, `ubuntu-NN.NN`, `ubuntu-NN.NN-arm` |
| Windows | `windows-latest`, `windows-NNNN`, `windows-NNNN-vsNNNN`, `windows-NN-arm`, `windows-NN-vsNNNN-arm` |
| macOS | `macos-latest`, `macos-NN`, `macos-NN-intel`, `macos-latest-large`, `macos-latest-xlarge`, `macos-NN-large`, `macos-NN-xlarge`, `xcode-NN`, `xcode-NN-xlarge` |

[hosted]: https://docs.github.com/en/actions/reference/runners/github-hosted-runners
[larger]: https://docs.github.com/en/actions/reference/runners/larger-runners

Any other text after the family prefix is a finding, as in
`ubuntu-acme-pool`, `macos-selfhosted` or `ubuntu-24.04-gpu`. The name of a
larger Linux or Windows runner is a name that its owner chooses, so it's a
finding. The check reads a hosted label in any letter case, because GitHub
documents that labels are case-insensitive (the note in [using labels with
self-hosted runners][labels]), so `Ubuntu-Latest` isn't a finding.

[labels]: https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/apply-labels

An expression right after a hosted prefix stands for the version, as in
`ubuntu-${{ matrix.version }}` or `macos-${{ matrix.version }}-large`. Only
digits, dots, another expression, a dash before another expression, and the
suffixes `-arm`, `-intel`, `-large`, `-xlarge` and `-vs` may follow that
expression, so `ubuntu-${{ matrix.version }}-${{ matrix.size }}` isn't a
finding and `ubuntu-${{ matrix.version }}-acme-pool` is one. The three
families share this suffix list, so `ubuntu-${{ matrix.version }}-intel` isn't
a finding either. An expression isn't a label, because the file doesn't hold
its value. The quoted strings inside an expression are labels, so
`${{ c && 'ubuntu-latest' || 'self-hosted' }}` is a finding for `self-hosted`.
A label that starts with an expression, as in `${{ matrix.os }}-large`, is
left to the expression.

A list is a finding when `self-hosted` is an element of it: it follows `[`, a
comma or a quote, and a comma, a quote or `]` follows it. A phrase such as
`[about self-hosted runners]` isn't a list. A list has at most 200 characters
on each side of the element and no line break. A runner type is a finding
unless an `@` or a `/` comes right before it, so a package name such as
`@rollup/rollup-linux-x64-gnu` in a lock file passes.

### Repositories

The name of the organization is read after one of these prefixes, in any
letter case:

- A host name and a slash, a colon or a port: `github.com/`,
  `raw.githubusercontent.com/`, `ghcr.io/`, `gitlab.com/`, `git@host:`.
- The API path, `repos/` with or without its first slash.
- `@`, for a team.
- A slash that starts a path, as in `see /<organization>/<name>`.
- Nothing, in the short form `<organization>/<name>`.

Three more forms name a repository:

- The address of a GitHub Pages site, `<organization>.github.io/<name>`, also
  with an escaped slash after `.github.io`, as in
  `https:\/\/<organization>.github.io\/<name>` and
  `https%3A%2F%2F<organization>.github.io%2F<name>`.
- The JSON form, with a backslash before each slash, as in
  `<organization>\/<name>`.
- The URL-encoded form, `<organization>%2F<name>`, in any letter case of the
  hex digits.

The escaped forms read the same prefixes as the plain form, with the escaped
slash in the place of each slash. A public repository stays public in every
form.

An encoded delimiter, such as `%3A`, may come before the organization, in the
plain form and in the escaped forms, as in `q=repo%3A<organization>%2F<name>`
or `q=org%3A<organization>+repo%3A<organization>%2F<name>`. Any encoded byte
is a delimiter, except the bytes that encode a character of a name or a slash:
`%2D` (`-`), `%2E` (`.`), `%5F` (`_`), `%7E` (`~`) and `%2F` (`/`), in any
letter case. A `+` is a delimiter too. So `example%2F<organization>%2F<name>`
is the name of another owner, and it isn't a finding. The exception for `%2F`
doesn't apply to a host name and to a Pages address, which `%2F` starts, as in
`https%3A%2F%2Fgithub.com%2F<organization>%2F<name>`.

The address of a team, `orgs/<organization>/teams/<team>`, is read in the same
way, in the web address of the team and in the path of the API, with a plain or
an escaped slash and with any host or none. It's a finding unless the team is
on the public list, in any letter case. The word `orgs` starts a token, so
`myorgs/<organization>/teams/<team>` isn't an address. Another page of the
organization, such as `orgs/<organization>/people`, isn't a finding.

A folder with the name of the organization inside a relative path, such as
`styles/<Organization>/rule.yml` or `./<organization>/name`, and a path with
another owner, such as `example/<organization>/name`, aren't repositories.

### GitHub Apps

The commit address of an App, `<number>+<slug>[bot]@users.noreply.github.com`,
is a finding, except for the three public accounts `github-actions`,
`renovate` and `dependabot`.

## Public names

| List | Names |
| ---- | ----- |
| Repositories | `.github`, `chironium`, `quints` |
| Teams | `maintainers` |

To add a name, change `publicNames` in `flake.nix` in a pull request. Add a
repository only when it's public on GitHub.

## Paths that the check skips

| Path | Reason |
| ---- | ------ |
| `nix/scripts/leaks/rules.py` | The patterns hold the prefixes that they search for. |
| `nix/tests/leaks` | The fixtures are leaks on purpose, with false identifiers. |

The check skips a file with a NUL byte, because it's binary, and it doesn't
follow a symbolic link. It reads every other file, lock files included.

## Findings

Each finding prints as `path:line: rule: text. advice`, and one run prints all
of them. To fix a finding, describe the thing without its name or identifier.
The rules are broad on purpose: when a rule matches a text that isn't a
private fact, reword the text.

## Limits

- The check reads the files of one commit. It doesn't read commit messages,
  pull request text or the Git history.
- A fact in a form that no rule describes passes. Review each pull request for
  private names as well.
- A runner type has the shape of other names. A name of that shape that
  follows a space, a quote or a bracket is a finding, even when it isn't a
  runner type: reword it.
- A flow list that goes on over more than 20 lines isn't read to its end, and
  a `runs-on` mapping key other than `group` and `labels` isn't read.
- A word after `--bucket` is a finding, also in prose.
- A runner label that a matrix or an input supplies isn't read: in
  `runs-on: ${{ matrix.os }}` the label is in the matrix, and the check reads
  only the text of the `runs-on` key.
- A JSON key written with quotes, as in `"runs-on": "label"`, isn't read.
- An identifier of a GitHub App in prose, or after a flag, isn't read. The
  check reads a key, the commit address and the installation address.
- An account identifier of AWS written with spaces, such as `1234 5678 9012`,
  isn't read.
- An IPv6 unique local address (`fc00::/7`) isn't read.
- A name that joins the organization and a repository with a separator other
  than a slash, such as `<organization>_<name>`, isn't read. The `bucket`
  rule reads the form with a dash.
- An address of a bot without a number before the slug isn't read.
- A repository name in a path that has a folder before the organization, such
  as `home/<organization>/name`, isn't read.
- Each rule runs in time that grows in step with the size of a file, also for
  one line of a million characters.

## Run it

```console
nix build .#checks.x86_64-linux.leaks -L
```

The tests of the rules are the check `check-leaks-tests`.
