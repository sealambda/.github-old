---
status: accepted
date: 2026-11-08
decision-makers: Sealambda maintainers
---

# Check decision records with a hermetic flake check

## Context and Problem Statement

[ADR 0004](0004-delete-a-replaced-decision-record-into-a-ledger.md) deletes a
replaced record into a ledger. After a deletion, no file may cite the old
number, except the ledger and the successor. Documents also cite specs and
pages, and a spec or a page is deleted when it dies. lychee in offline mode
catches a Markdown link to a deleted file. It doesn't catch a plain-text
citation of a record or a spec by its number, or a bare path in a code
comment. Those citations go stale without a failing check. How does a
repository find them, and how does it keep its records and its ledger valid?

## Decision Drivers

- A citation of a deleted record, spec or page fails at its file and line, in
  prose, code and configuration alike.
- The same result locally and in CI, with no network.
- The front matter and the ledger are valid against a standard schema that
  editors can read.
- Little code that a maintainer must own, and that code is typed and tested.
- Every Sealambda repository runs one version of the tool.

## Considered Options

- Python with JSON Schema, in a flake check of the hub
- Extend the bash script of `sealambda/infra`
- `adrs` or `adr-tools`
- lychee and Vale only

## Decision Outcome

Chosen option: "Python with JSON Schema, in a flake check of the hub" because
it checks everything that the drivers name, with a language that has YAML,
JSON Schema and regular expressions in its libraries, and with unit tests and a
type checker.

The hub exports `lib.mkDecisionsCheck pkgs src { repository, exclude }`. The
tool is the Python package in `nix/scripts/decisions`. It uses PyYAML and
`jsonschema` from the hub's nixpkgs. The schemas
`schemas/decision-record.schema.json` and `schemas/superseded.schema.json`
define the front matter and the ledger. The
[decision records reference](../reference/decision-records.md) defines the
checks, the citation forms and the files that the check skips.

Three further choices:

- **The check reads the working tree, not the Git history.** A flake source has
  no history, so the check doesn't verify that the commit of a ledger entry
  exists or that it holds the record. The reviewer opens the permalink, as the
  confirmation of ADR 0004 says. In a Git work tree, the check lists the files
  with `git ls-files`, so `.gitignore` keeps `.venv` and `node_modules` out. In
  the sandbox of a Nix build there is no `.git`, and the check walks the
  folders.
- **No generated index.** The listing of `docs/decisions/` is the index of the
  records in force, and the ledger lists the deleted records. A generated index
  is a second source that must stay in step with them.
- **The tool comes from the hub's own nixpkgs.** `mkDecisionsCheck` takes only
  the system from the `pkgs` that the caller passes, and builds the tool from
  the hub's nixpkgs. Every repository then runs one version of Python, PyYAML
  and `jsonschema`, whatever nixpkgs it follows, and a change to the checker
  reaches a repository by a bump of the hub in `flake.lock`.

### Consequences

- Good, because a citation of a deleted record, spec or page fails at
  `path:line`, in any text file, and one run lists every finding.
- Good, because editors can use the two JSON Schemas, and the ledger entries of
  `sealambda/infra` stay valid.
- Good, because the check needs no network and no configuration of the user.
- Good, because a repository adds it with one line in its flake.
- Bad, because the hub owns a Python package with tests, a type check and a
  linter. The hub's `check-decisions-tests` and `python-quality` checks cover
  them.
- Bad, because the citation forms are patterns on text. A text that uses a form
  with another meaning is a finding, and the `exclude` list is the way out.
- Bad, because the forms use the English words `ADR`, `decision record` and
  `spec`.
- Bad, because a repository can't pin the tool apart from the hub. The tool
  changes with the hub revision in `flake.lock`.

### Confirmation

The flake check `check-decisions-tests` runs the unit tests of every finding,
every citation form, the excludes, the skipped files and the exit statuses. The
check `python-quality` runs ruff and `mypy --strict`. The hub's `decisions`
check runs the tool on the hub itself.

## Pros and Cons of the Options

### Python with JSON Schema, in a flake check of the hub

- Good, because PyYAML, `jsonschema`, `re` and `unittest` cover every need
  without a new dependency of the build.
- Good, because the schemas are declarative files and not code.
- Good, because the hub's check pattern, a derivation that runs one command, is
  the same as `mkDocsCheck`.
- Bad, because it's a new language in a hub that has shell and Nix.

### Extend the bash script of `sealambda/infra`

The `sealambda/infra` repository has `scripts/decisions-index.sh`, a bash
script of about 600 lines. It checks the front matter and the ledger, checks
the citations of records, and writes an index.

- Good, because it exists, it works in infra, and it also checks the commit of
  each ledger entry in the Git history.
- Bad, because it needs `git`, `yq`, `check-jsonschema` and Prettier from a dev
  shell, so it isn't a derivation that a repository adds to its flake checks.
- Bad, because it has no check for specs and for bare `docs/` paths.
- Bad, because a bash script of this size is hard to test and to change, and
  more citation forms make it larger.

### `adrs` or `adr-tools`

Both tools create, number and link the files of records.

- Good, because they're maintained and known.
- Bad, because neither has a ledger of deleted records, so neither checks the
  rule that only the successor cites a deleted record.
- Bad, because neither reads citations in other files, so they can't find a
  stale citation in code or in another page.
- Bad, because they don't validate the front matter against a schema that the
  hub owns.

### lychee and Vale only

- Good, because both are in the hub already, and they need no new code.
- Bad, because lychee checks links and not plain-text citations. A bare path in
  a code comment isn't a link.
- Bad, because Vale checks the style of prose. It doesn't look at the file
  system, so it can't tell whether a record, a spec or a page exists.
- Bad, because neither validates front matter or a ledger.

## More Information

- [Adopt the hub in a repository](../how-to/adopt-the-hub.md#gate-the-decision-records)
  shows how a repository adds the check.
- [ADR 0003](0003-gate-documentation-with-a-flake-check.md) makes the same kind
  of gate for documentation.
- [JSON Schema](https://json-schema.org/)
- [MADR](https://adr.github.io/madr/)
