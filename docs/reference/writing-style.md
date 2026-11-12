# Writing style

A page states what's true now. This page defines the Vale rules that check
that, and the places where they don't apply. The rule that a document describes
only the current state is in
[CONTRIBUTING.md](../../CONTRIBUTING.md#current-state-only). Google's
style guide gives the same advice: write in the present tense.

The rules are the Vale style `Sealambda`. Its source is the folder
`vale/Sealambda` in the hub. The `docs` check runs it with the style Google,
as [Adopt the hub](../how-to/adopt-the-hub.md#gate-the-documentation)
shows.

## Rules

| Rule | Level | What it flags |
| ---- | ----- | ------------- |
| `Sealambda.CurrentState` | error | A word of a plan or a gap. |
| `Sealambda.History` | suggestion | A word of a history. |

The `docs` check runs Vale with `--minAlertLevel=error`. A finding of level
error fails the check. A finding of level suggestion shows in an editor that
runs Vale, and in a run of Vale without that flag.

Both rules match whole words in any letter case. They skip code spans and code
blocks, so a flag or a command in code font never matches.

## Current state

`Sealambda.CurrentState` flags these words:

- `currently`
- `for now`
- `in the future`
- `will be`
- `phase 2`
- `TODO`
- `FIXME`

These words mark a plan or a gap. A page that has them describes a system that
doesn't exist yet. Write what's true today, and open an issue for the rest.
The rule is the same as the rule of the `sealambda/infra` repository.

The words `target` and `planned` aren't on the list. Each has a true present
meaning, such as a build target or a planned maintenance window, that a word
list can't tell from a plan.

### Where the rule is off

`config/vale.ini` turns `Sealambda.CurrentState` off in two folders:

- `docs/decisions/`, because a decision record states what a decision changes.
- `docs/specs/`, because a design spec describes work that isn't built yet.

The folders can sit under another folder. A path such as `services/api/docs/specs/`
counts too.

### A true use of a listed word

When a listed word is true, turn the rule off for the passage. Put the reason
in a comment before it:

```markdown
<!-- This section quotes the wording of the vendor contract. -->
<!-- vale Sealambda.CurrentState = NO -->
The vendor will be paid on the first day of the month.
<!-- vale Sealambda.CurrentState = YES -->
```

## History

`Sealambda.History` flags these words:

- `previously`
- `formerly`
- `no longer`
- `used to`
- `superseded`
- `was renamed`

These words describe the past of the system. History lives in git and in
decision records, and a page states the current rationale. The level is
suggestion, because a word of the list can have a true present meaning. An
example is the sentence `The script is used to run the tests`. Change a
flagged sentence when it tells a history. Leave it when it states a fact.
