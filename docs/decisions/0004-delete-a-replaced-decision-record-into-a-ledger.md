---
status: accepted
date: 2026-11-12
decision-makers: Sealambda maintainers
---

# Delete a replaced decision record into a ledger

## Context and Problem Statement

Sealambda documents describe only the current state. A reader who opens the
decision folder, or follows a citation from code, must find only decisions that
hold today. When a new record replaces an old one, the old record stops being
true. What happens to it?

Every source that the hub surveyed keeps the old record and gives it the status
superseded. That keeps the history in the folder, and a reader sees a decision
that no longer applies unless they check its status.

## Decision Drivers

- A reader of the folder or of the code sees only records that are true today.
- The text of a replaced record stays reachable.
- An accepted record stays immutable: a changed decision is a new record.
- No tool or index that a maintainer must own.

## Considered Options

- Keep the record and mark it superseded
- Move the record to a subfolder for superseded records
- Delete the record and list it in a ledger

## Decision Outcome

Chosen option: "Delete the record and list it in a ledger" because the folder
and the code then hold only records in force, and git keeps every old text.

A record that a new record replaces is deleted in the pull request that adds
the new record. The new record restates the whole current decision, so a reader
needs no other record to understand it. The ledger
`docs/decisions/superseded.yaml` gets one entry for the deleted record: its
number, title, the commit of its last text, its path in that commit, its
successor and the date. The commit gives a permalink to the last text. A
decision that no longer applies and has no replacement is deleted the same way,
without a successor.

The [decision records reference](../reference/decision-records.md) defines the
format of the record, the ledger and the citations. The hub's
[CONTRIBUTING.md](../../CONTRIBUTING.md) states the rules.

No surveyed source deletes a record, so this is a deliberate deviation from
them. The deviation keeps their main rule, which is that an accepted record is
immutable. This record makes deletion the rule of every Sealambda repository.

### Consequences

- Good, because every file in the folder, and every record that code cites, is
  true today.
- Good, because the replaced text stays one permalink away, and a commit
  permalink doesn't change.
- Good, because the ledger adds no tool: it's one YAML file in the folder.
- Bad, because a search of the repository doesn't find the text of a replaced
  record. The reader follows the permalink.
- Bad, because the permalinks depend on GitHub and on the name of the
  repository.
- Bad, because a pull request that replaces a record also changes every file
  that cites it.
- Bad, because a tool that expects the status `superseded` finds none.

### Confirmation

A pull request that deletes a record also adds its ledger entry. The reviewer
opens the permalink and confirms that it shows the last text of the record, and
that no file cites the deleted record except the ledger and its successor.

## Pros and Cons of the Options

### Keep the record and mark it superseded

[MADR](https://adr.github.io/madr/) lists "superseded by" as a status.
[AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html)
says that an accepted ADR becomes immutable and that the new ADR supersedes
it. The
[Azure Well-Architected Framework](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record)
calls the log append-only.
[Michael Nygard](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
keeps the old record and marks it superseded. The
[GDS Way](https://gds-way.digital.cabinet-office.gov.uk/standards/architecture-decisions.html)
marks a replaced ADR superseded, and allows an update for a minor
clarification.

- Good, because it's the common practice, and tools support it.
- Good, because a search finds the old text, and no link changes.
- Bad, because a reader can take an old record for a decision that holds.
  Only its status line tells the difference.
- Bad, because the folder grows with records that describe no current
  decision.

### Move the record to a subfolder for superseded records

- Good, because the old text stays searchable and out of the main folder.
- Bad, because every link to the record breaks when it moves.
- Bad, because code can still cite a record that no longer holds.
- Bad, because the subfolder holds the same untrue text as the folder did.

### Delete the record and list it in a ledger

- Good, because the folder and the code hold only records that are true.
- Good, because git is the archive, and the ledger links each old text.
- Bad, because an old text is one permalink away, not one search away.

## More Information

- [Diátaxis](https://diataxis.fr/) allows history in explanation pages. The hub
  keeps decision history in records and in the ledger only.
- [ADR 0001](0001-hub-as-single-source-of-standards.md) makes the hub the one
  place for organization standards.
- Revisit this record if readers often need to search the text of replaced
  records.
