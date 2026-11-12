# Writing style

A page states what is true now. This page defines the Vale rules that check
that, and the places where they do not apply. The rule that a document describes
only the current state is in
[CONTRIBUTING.md](../../CONTRIBUTING.md#current-state-only). Google's style
guide gives the same advice. Write in the present tense.

The rules are the Vale style `Sealambda`. Its source is the folder
`vale/Sealambda` in the hub. The `docs` check runs it with the style Google, as
[Adopt the hub](../how-to/adopt-the-hub.md#gate-the-documentation) shows.

## Rules

| Rule                       | Level      | What it flags                        |
| -------------------------- | ---------- | ------------------------------------ |
| `Sealambda.CurrentState`   | error      | A word of a plan or a gap.           |
| `Sealambda.History`        | suggestion | A word of a history.                 |
| `Sealambda.Contractions`   | error      | A contraction, such as `isn't`.      |
| `Sealambda.SentenceLength` | error      | A sentence of more than 25 words.    |
| `Sealambda.Filler`         | error      | A filler word, such as `simply`.     |
| `Google.Will`              | error      | The future tense, such as `will do`. |

The `docs` check runs Vale with `--minAlertLevel=error`. A finding of level
error fails the check. A finding of level suggestion shows in an editor that
runs Vale, and in a run of Vale without that flag.

The rules match whole words in any letter case. They skip code spans and code
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
does not exist yet. Write what is true today, and open an issue for the rest.
The rule is the same as the rule of the `sealambda/infra` repository.

The words `target` and `planned` are not on the list. Each has a true present
meaning, such as a build target or a planned maintenance window, that a word
list cannot tell from a plan.

### Where the rule is off

`config/vale.ini` turns `Sealambda.CurrentState` and `Google.Will` off in two
folders:

- `docs/decisions/`, because a decision record states what a decision changes.
- `docs/specs/`, because a design spec describes work that is not built yet.

The folders can sit under another folder. A path such as
`services/api/docs/specs/` counts too.

### A true use of a listed word

When a listed word is true, turn the rule off for the passage. Put the reason in
a comment before it:

```markdown
<!-- This section quotes the wording of the vendor contract. -->
<!-- vale Sealambda.CurrentState = NO -->
The vendor will be paid on the first day of the month.
<!-- vale Sealambda.CurrentState = YES -->
```

## Full forms

`Sealambda.Contractions` flags a contraction, such as `isn't` or `it's`. Write
the full form: `is not`, `it is`. The rule applies to Markdown and to the
comments of code files (Python, Elixir, TypeScript, JavaScript, Go and Rust).
`Google.Contractions` is off, because it asks for the opposite.

## Sentence length

`Sealambda.SentenceLength` flags a sentence of more than 25 words. Split it into
two sentences. The rule skips table cells, code spans and code blocks. It does
not check the comments of code files, because they do not match the `sentence`
scope of Vale.

## Filler words

`Sealambda.Filler` flags `simply`, `actually`, `really` and `just`. Delete the
word: it adds no fact. The rule allows `just-in-time`, `just before` and
`just now`, and it skips table cells and headings. It also checks the comments
of code files.

## Future tense

`Google.Will` flags the word `will`, because a page states what is true now.
Write the verb in the present tense: `works`, not `will work`. The rule is off
in the folders listed in [Where the rule is off](#where-the-rule-is-off).

## Line length

Prettier wraps the prose of a Markdown file at 80 columns. Run `nix fmt` to wrap
it. The `formatting` check fails on a file that Prettier would change.
markdownlint checks the structure of a page and not the length of a line.

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
example is the sentence `The script is used to run the tests`. Change a flagged
sentence when it tells a history. Leave it when it states a fact.
