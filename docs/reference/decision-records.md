# Decision records

A decision record states one architecturally significant decision. This page
defines the file name, the front matter, the ledger of deleted records, the
forms of a citation and the permalink of a deleted record. The rules that say
when to write, change or delete a record are in
[CONTRIBUTING.md](../../CONTRIBUTING.md#decision-records). The reasons for
deleting a replaced record are in
[ADR 0004](../decisions/0004-delete-a-replaced-decision-record-into-a-ledger.md).

## File name

| Part | Rule |
| ---- | ---- |
| Folder | `docs/decisions/` |
| Name | `NNNN-slug.md`: four digits, a dash, and a lowercase slug with dashes. |
| Number | Unique in the repository. A number is never reused, not even after the record is deleted. |
| Format | [MADR 4.0.0](https://adr.github.io/madr/). Start from `templates/adr.md.tmpl`. |

The folder holds the records, an optional `README.md`, and the ledger
`superseded.yaml`.

## Front matter

Every record starts with a YAML block.

| Key | Required | Value |
| --- | -------- | ----- |
| `status` | Yes | `proposed`, `accepted` or `rejected`. |
| `date` | Yes | `YYYY-MM-DD`. The day the record was last updated. |
| `decision-makers` | Yes | A name or a list of names. |
| `consulted` | No | The people whose opinion was sought. |
| `informed` | No | The people who are kept up to date. |

A record may hold other keys, such as `domain`.

### Status

| Value | Meaning |
| ----- | ------- |
| `proposed` | The decision is open for review. |
| `accepted` | The decision holds. The record is immutable. |
| `rejected` | The decision was considered and refused. |

There is no `superseded` status. A replaced record is deleted and listed in
the ledger.

### Changes to an accepted record

An accepted record changes only in these ways:

- Its `status` changes, for example from `proposed` to `accepted`.
- A correction keeps the decision and updates `date`. A renamed path and a
  removed example are corrections.
- A new record replaces it, and the pull request deletes it.

A `rejected` record stays only while it holds reasoning that no other record
holds.

## Ledger

`docs/decisions/superseded.yaml` lists each record that a pull request
deleted. The first deletion creates the file. It holds a YAML list with one
entry for each deleted record, in the order of deletion.

```yaml
- number: "NNNN"
  title: The title of the record at its last text
  commit: <the full 40-character hash of the last commit on main that changed the file>
  path: docs/decisions/NNNN-slug.md
  successor: "NNNN"
  date: YYYY-MM-DD
```

| Field | Required | Value |
| ----- | -------- | ----- |
| `number` | Yes | The number of the deleted record, as a quoted string so that YAML keeps the leading zeros. Four digits. |
| `title` | Yes | The title of the record at its last text. |
| `commit` | Yes | The full 40-character hash of the last commit on `main` that changed the file. That commit holds the last text of the record. |
| `path` | Yes | The path of the record in that commit. The folder can differ from `docs/decisions/` when the folder had another name then. The file name is the `number`, a dash and a slug, and ends in `.md`: `NNNN-slug.md`. |
| `successor` | Yes, except for a withdrawn record | The number of the record in force that replaced this one. When several records took over parts, the one that took over the decision. A record that no longer applies, and has no replacement, omits the key: it's withdrawn. |
| `date` | Yes | `YYYY-MM-DD`. The day the record was replaced or withdrawn. |

Rules for the entries:

- A number in the ledger has no record file in the folder.
- The file name of the `path` starts with the `number` of its entry and a
  dash. A typo there would make a permalink to another record.
- A successor is a record in force. When the successor is replaced in turn,
  the entries that name it name its successor.
- Only the ledger and the successor of a deleted record cite its number.

The fields are the same as those of the ledger in the `sealambda/infra`
repository, so an entry written there stays valid here.

## Citations

A citation names a record, a spec or a page. A reader or a tool resolves it in
the repository that holds the text. These forms are recognized:

| Form | Example | Resolves to |
| ---- | ------- | ----------- |
| `ADR NNNN` | `ADR NNNN`, `ADR-NNNN` | The record numbered `NNNN`. |
| `decision record NNNN` | `decision record NNNN` | The same record. |
| A list of numbers | `ADRs NNNN, NNNN and NNNN`, `decision records NNNN or NNNN` | Each record in the list. |
| A path prefix | `docs/decisions/NNNN-` | The record whose name starts with it. |
| A file name | `NNNN-slug.md`, `../decisions/NNNN-slug.md` | The record with that name. A name after the record folder of this repository always counts: `docs/decisions/`, `./docs/decisions/` or the address of the folder in this repository (see below). Any other path counts when it resolves into `docs/decisions/` from the citing file: a bare name in a file of that folder, or a relative link such as `../decisions/NNNN-slug.md`. |
| `spec NNNN` | `spec NNNN` | The file `docs/specs/NNNN-*.md`. |
| A page path | `docs/**/*.md` | The file at that path. |

A citation of a record names a record in force. A deleted record is cited only
in the ledger and in its successor.

Rules for the forms:

- A number has exactly four digits. A date such as `2026-11-08` isn't a
  number.
- The words `ADR` (also as `ADR-NNNN`), `decision record` and `spec` match in
  any letter case, and their plural forms match too. The word `record` alone
  isn't a form: "audit records 2024 to 2026" names no record. A list separates
  its numbers with commas, `and`, `or` or `to`.
- A range names every number from its first end to its second, both ends
  included. `NNNN to MMMM` is a range after every keyword. Two numbers that a
  dash joins are a range when the keyword and the dash allow it. The plural
  keywords are `ADRs`, `decision records` and `specs`. The singular ones are
  `ADR`, `ADR-`, `decision record` and `spec`. In the table, `NNNN` and `MMMM`
  stand for four-digit numbers:

  | Dash between the numbers | After a plural keyword | After a singular keyword |
  |---|---|---|
  | An en dash, with or without spaces | Range: `ADRs NNNN–MMMM` | Range: `ADR NNNN – MMMM` |
  | A hyphen with a space on each side | Range: `ADRs NNNN - MMMM` | Range: `ADR NNNN - MMMM` |
  | A hyphen with no space, or a space on one side only | Range: `ADRs NNNN-MMMM` | The first number only: `ADR-NNNN-MMMM`, `ADR NNNN-2026 plan` |

  A list follows the keyword that opens it: in `ADRs NNNN, MMMM-PPPP` the hyphen
  follows a plural keyword, so the second item is a range.
- The check resolves each number of a range as if the text cited it alone, so a
  range over a deleted record is a finding, except in the successor of that
  record. A range must run from the lower number to the higher: `NNNN to MMMM`
  is a finding when `MMMM` is lower. Equal ends name one number. A file may name
  at most 10000 numbers through ranges. A range past that budget is a finding
  and isn't expanded.
- A dash makes a range only when a second four-digit number follows it, and no
  other dash and letter or digit follows that number. Otherwise the text is a
  date or a slug that starts with a number, and only its first number counts:
  `ADR-NNNN-2026-roadmap` and `ADRs NNNN-MMMM-slug` cite one record, and a date
  such as `2026-11-08` cites none. The check doesn't ask what the second number
  means, so `ADRs NNNN-2026 here` is a range from `NNNN` to 2026. The word `to`
  has no such rule: after `ADRs NNNN to MMMM-slug`, the range ends at `MMMM`.
- The record folder is `docs/decisions/` at the root of the repository. A path
  names it when no other path segment comes before it: `docs/decisions/` and
  `./docs/decisions/` do, and `services/api/docs/decisions/` and
  `../docs/decisions/` don't. The check doesn't look at a nested record folder.
  The address `https://github.com/<owner>/<repo>/blob/<ref>/docs/decisions/` (or
  `/tree/<ref>/`) names the folder when `<owner>/<repo>` is the repository that
  holds the text, in any letter case. `<ref>` is one path segment, so a branch
  name with a slash isn't recognized.
- A page path counts when it starts at `docs/` or `./docs/` and ends in `.md`,
  relative to the root of the repository. A relative link such as
  `../reference/page.md` isn't a page path: the link checker covers it.
- The placeholder `NNNN` in a template or in prose matches no form, because
  every form needs digits. A path that holds `NNNN` isn't a page path.

A citation that a repository name qualifies is about that repository. It's not
resolved here. A repository name is `<owner>/<repo>` with the owner of the
repository that holds the text, in any letter case, or the address
`github.com/<owner>/<repo>` with any owner. In a repository of the owner
`sealambda`, `sealambda/<repo>` and `Sealambda/<repo>` are names. A name
qualifies the citation that directly follows it, as in
`sealambda/<repo> ADR NNNN`, and every citation in the same Markdown link
or address. It doesn't qualify the other citations of the sentence. A GitHub
address that isn't a repository, such as `github.com/orgs/<org>`, isn't a
repository name. The repository that holds the text isn't another repository.
In Markdown and other prose files, a sentence ends at a full stop, a blank
line, a list item, a table row or a heading. In any other file, a line is one
sentence.

## Check

The flake check `decisions`, built with `lib.mkDecisionsCheck`, enforces this
page. [Adopt the hub](../how-to/adopt-the-hub.md#gate-the-decision-records)
shows how a repository adds it. The JSON Schemas of the front matter and of the
ledger are in `schemas/` in the hub. Each finding prints as
`path:line: message`, and one run prints all of them. The exit status is 0 when
nothing is wrong, 1 for findings, 2 for a usage error and 3 for an internal
error. An internal error is a bug in the tool: it prints the traceback to
standard error, and it's never a finding.

The check reports:

- A file or folder in `docs/decisions/` that isn't a record, `README.md` or
  the ledger, and a number that two records share.
- A record whose front matter breaks the schema, or that has none, and a
  record with no level-1 heading. A heading inside a fenced code block isn't
  the title. The front matter can use CRLF line ends and start with a UTF-8 byte
  order mark.
- A ledger entry that breaks the schema, repeats a number, names a number that
  has a record file, names a successor that isn't a record, or has a `path`
  whose file name doesn't start with its `number` and a dash and end in `.md`.
- A citation of a record, a spec or a page that doesn't resolve.
- A citation of a deleted record outside the ledger and its successor.

A range gives one finding for each problem, not one for each number. The
records of a range that exist nowhere share one finding, and so do the specs
that have no file. Runs of consecutive numbers collapse to `first to last`. The
runs are separated by commas and a last `and`. In this format, `NNNN` and
`MMMM` stand for four-digit numbers:

```text
path:line: decision records NNNN to MMMM, NNNN and NNNN to MMMM do not exist
path:line: specs NNNN to MMMM and NNNN have no file docs/specs/NNNN-*.md
```

When only one number of the range is missing, the finding is the one that a
single citation gets: `decision record NNNN does not exist` and
`spec NNNN has no file docs/specs/NNNN-*.md`. A deleted or a withdrawn record
inside the range keeps its own finding for each number, with the advice of a
single citation. A reversed range and a range past the budget keep their own
findings.

The check reads every text file of the repository. In a Git work tree it reads
the files that `git ls-files --cached --others --exclude-standard` lists: the
tracked files and the untracked files that `.gitignore` doesn't ignore, so
`.venv`, `node_modules` and `.direnv` stay out. Without a `.git` entry, as in
the sandbox of a Nix build, it reads every file below the root. If Git fails,
the check stops with an error instead of reading fewer files. It skips:

- Binary files, which hold a NUL byte in the first 8 KiB or aren't UTF-8, and
  files larger than 1 MiB.
- Lock files (`*.lock`, `package-lock.json`, `npm-shrinkwrap.json`,
  `pnpm-lock.yaml`), `CHANGELOG*.md` files and ignore-pattern files. An
  ignore-pattern file is a file whose name starts with a dot and ends in
  `ignore` in lowercase, such as `.gitignore`, `.dockerignore` or
  `.prettierignore`. Its lines are glob patterns, not citations. The rule has
  no other name: `CODEOWNERS` and `.gitattributes` are read.
- The ledger, symbolic links and `.git/`.
- The paths in the `exclude` list of the check. Each path is relative to the
  root and skips the file or the folder at that path. A path matches whole
  components: `a/b` skips `a/b/c.py` and doesn't skip `a/bc.py`. Use it for
  files that hold citations on purpose, such as test fixtures.

The same listing, before these skips, decides which files exist:

- The record folder is read from the listing and not from the disk, so a file
  that `.gitignore` hides, such as `.DS_Store`, isn't a stray file.
- A cited page exists when its path is in the listing. The comparison is
  case-sensitive on every file system, so a path in another letter case than
  the file name doesn't resolve on a Mac either. A page that `.gitignore` hides
  doesn't exist. A page that the scan skips, such as a `CHANGELOG*.md` file or a
  page below an `exclude` path, exists.
- The listing includes an untracked file that `.gitignore` doesn't ignore. A
  page that isn't added yet resolves in a local run, and it fails in
  `nix flake check`, which reads only the tracked files. Run `git add` on the
  page first.

## Permalink of a deleted record

The permalink of a deleted record is:

```text
https://github.com/<owner>/<repo>/blob/<commit>/docs/decisions/<file>
```

- `<owner>/<repo>` is the repository of the record.
- `<commit>` is the `commit` of the ledger entry.
- `docs/decisions/<file>` is the `path` of the entry. When the folder had
  another name at that commit, use the `path` as written.

Before the deletion, `git log -1 --format=%H origin/main -- <path>` prints the
commit of the last text of a record that reached `main`.
