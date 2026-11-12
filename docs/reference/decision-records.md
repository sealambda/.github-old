# Decision records

A decision record states one architecturally significant decision. This page
defines the file name, the front matter, the ledger of deleted records and the
permalink of a deleted record. People write and review these files. No tool
validates them. The rules that say when to write, change or delete a record are
in [CONTRIBUTING.md](../../CONTRIBUTING.md#decision-records). The reasons for
deleting a replaced record are in
[ADR 0004](../decisions/0004-delete-a-replaced-decision-record-into-a-ledger.md).

## File name

| Part   | Rule                                                                                      |
| ------ | ----------------------------------------------------------------------------------------- |
| Folder | `docs/decisions/`                                                                         |
| Name   | `NNNN-slug.md`: four digits, a dash, and a lowercase slug with dashes.                    |
| Number | Unique in the repository. A number is never reused, not even after the record is deleted. |
| Format | [MADR 4.0.0](https://adr.github.io/madr/). Start from `templates/adr.md.tmpl`.            |

The folder holds the records, an optional `README.md`, and the ledger
`superseded.yaml`.

## Front matter

Every record starts with a YAML block.

| Key               | Required | Value                                              |
| ----------------- | -------- | -------------------------------------------------- |
| `status`          | Yes      | `proposed`, `accepted` or `rejected`.              |
| `date`            | Yes      | `YYYY-MM-DD`. The day the record was last updated. |
| `decision-makers` | Yes      | A name or a list of names.                         |
| `consulted`       | No       | The people whose opinion was sought.               |
| `informed`        | No       | The people who are kept up to date.                |

A record may hold other keys, such as `domain`.

### Status

| Value      | Meaning                                      |
| ---------- | -------------------------------------------- |
| `proposed` | The decision is open for review.             |
| `accepted` | The decision holds. The record is immutable. |
| `rejected` | The decision was considered and refused.     |

There is no `superseded` status. A replaced record is deleted and listed in the
ledger.

### Changes to an accepted record

An accepted record changes only in these ways:

- Its `status` changes, for example from `proposed` to `accepted`.
- A correction keeps the decision and updates `date`. A renamed path and a
  removed example are corrections.
- A new record replaces it, and the pull request deletes it.

A `rejected` record stays only while it holds reasoning that no other record
holds.

## Ledger

`docs/decisions/superseded.yaml` lists each record that a pull request deleted.
The first deletion creates the file. It holds a YAML list with one entry for
each deleted record, in the order of deletion. The author of the deletion writes
the entry, and the reviewer opens its permalink.

```yaml
- number: "NNNN"
  title: The title of the record at its last text
  commit: <the full 40-character hash of the last commit on main that changed the file>
  path: docs/decisions/NNNN-slug.md
  successor: "NNNN"
  date: YYYY-MM-DD
```

| Field       | Required                           | Value                                                                                                                                                                                                                         |
| ----------- | ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `number`    | Yes                                | The number of the deleted record, as a quoted string so that YAML keeps the leading zeros. Four digits.                                                                                                                       |
| `title`     | Yes                                | The title of the record at its last text.                                                                                                                                                                                     |
| `commit`    | Yes                                | The full 40-character hash of the last commit on `main` that changed the file. That commit holds the last text of the record.                                                                                                 |
| `path`      | Yes                                | The path of the record in that commit. The folder can differ from `docs/decisions/` when the folder had another name then. The file name is the `number`, a dash and a slug, and ends in `.md`: `NNNN-slug.md`.               |
| `successor` | Yes, except for a withdrawn record | The number of the record in force that replaced this one. When several records took over parts, the one that took over the decision. A record that no longer applies, and has no replacement, omits the key: it is withdrawn. |
| `date`      | Yes                                | `YYYY-MM-DD`. The day the record was replaced or withdrawn.                                                                                                                                                                   |

Rules for the entries:

- A number in the ledger has no record file in the folder.
- The file name of the `path` starts with the `number` of its entry and a dash.
  A typo there would make a permalink to another record.
- A successor is a record in force. When the successor is replaced in turn, the
  entries that name it name its successor.
- Only the ledger and the successor of a deleted record cite its number.

The fields are the same as those of the ledger in the `sealambda/infra`
repository, so an entry written there stays valid here.

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
commit of the last text of a record that reached `main`. Run `git fetch origin`
first, because the command reads the local `origin/main`.
