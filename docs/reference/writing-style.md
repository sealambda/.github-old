# Writing style

A page states what's true now. This page defines the Vale rules that check
that, and the places where they don't apply. The rule that a document describes
only the current state is in
[CONTRIBUTING.md](../../CONTRIBUTING.md#current-state-only). Google's and
Microsoft's style guides give the same advice: write in the present tense.

The rules are the Vale style `Sealambda`. Its source is the folder
`vale/Sealambda` in the hub. The `docs` check runs it with the styles Microsoft
and Readability, as [Adopt the hub](../how-to/adopt-the-hub.md#gate-the-documentation)
shows. A repository can switch a rule off in its own `.vale.ini`, as
[Wrapped documentation tools](wrapped-tools.md#vale) states.

## Rules

| Rule | Level | What it flags |
| ---- | ----- | ------------- |
| `Sealambda.CurrentState` | error | A word of a plan or a gap. |
| `Sealambda.History` | suggestion | A word of a history. |
| `Sealambda.DefineAcronyms` | warning | An acronym with no definition. |
| `Sealambda.OneSpelling` | warning | The unused spelling of a word pair. |
| `Sealambda.FillerWords` | warning | A word that adds no fact. |

The `docs` check runs Vale with `--minAlertLevel=error`. A finding of level
error fails the check. A finding of level warning or suggestion doesn't fail
it, and the check doesn't print it. It shows in an editor that runs Vale, and
in a run of Vale without that flag. A rule of level warning tells you what to
change, and it blocks no merge.

No rule of this page checks code. A code span and a code block never match, so
a flag or a command in code font stays silent.

`Sealambda.CurrentState` and `Sealambda.History` match whole words in any
letter case.

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

The words `target` and `planned` aren't on the list. Each has a true present
meaning, such as a build target or a planned maintenance window, that a word
list can't tell from a plan.

### Where the rule is off

The hub's Vale base, `config/vale.ini`, turns `Sealambda.CurrentState` off in
two folders:

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

## Define acronyms

`Sealambda.DefineAcronyms` flags an acronym that has no definition earlier on
the page. An acronym is two to six capital letters as a whole word, such as
`SBOM`.

A reader can't look up an acronym that a page doesn't explain. Write the full
name at the first use, and the acronym after it in parentheses, as in
`software bill of materials (SBOM)`. The definition covers the rest of the
page. A plural such as `SBOMs` and a name in mixed case such as `NixOS` aren't
acronyms, and the rule is case-sensitive.

The rule skips these acronyms:

- The well-known ones that its file lists in the key `exceptions`, such as
  `API`, `CI`, `JSON` and `URL`.
- The terms of the Vale vocabularies. A repository adds an acronym of its own
  to its `Repository` vocabulary, and the hub adds its acronyms to the
  `Sealambda` vocabulary.

Microsoft's style has a rule of the same purpose, `Microsoft.Acronyms`, with
the level suggestion. It needs a definition whose words start with capital
letters. Both rules report an undefined acronym.

### A true use of an undefined acronym

An acronym that a page can't define, for example in a quotation, needs a Vale
comment with the reason before it:

```markdown
<!-- This section quotes the wording of the standard. -->
<!-- vale Sealambda.DefineAcronyms = NO -->
The standard names the SBOM as the output.
<!-- vale Sealambda.DefineAcronyms = YES -->
```

## One spelling

`Sealambda.OneSpelling` flags the unused spelling of a word that people write in
two ways. These are the pairs, with the spelling to use second:

- `e-mail` and `email`
- `web site` and `website`
- `data base` and `database`
- `meta-data` and `metadata`
- `time-out` and `timeout`
- `tool-chain` and `toolchain`
- `work flow` and `workflow`

A page that mixes two spellings makes a reader wonder if they mean two things,
and a search for one spelling misses the other. The rule matches a capital at
the start of a sentence, and it gives the suggestion the same case. It doesn't
match part of a longer word.

The list has only pairs where one spelling is plain wrong. A pair that splits by
part of speech isn't on it: `set up` is a verb and `setup` is a noun, and
`log in` is a verb and `login` is a noun. A pair that the hub's own pages write
both ways isn't on it either, such as `file name` and `filename`. A brand name
such as `GitHub` isn't on it, because the suggestion takes the case of the
match.

### A true use of the unused spelling

A quotation or the name of a product can use the unused spelling. Turn the rule
off for the passage, with the reason in a comment before it:

```markdown
<!-- This sentence quotes the title of a book. -->
<!-- vale Sealambda.OneSpelling = NO -->
The book is called "The Work Flow".
<!-- vale Sealambda.OneSpelling = YES -->
```

## Filler words

`Sealambda.FillerWords` flags these words and phrases:

- `just`, `simply`, `basically`, `actually`
- `obviously`, `clearly`, `of course`, `literally`
- `merely`, `essentially`, `needless to say`
- `please note that`, `it should be noted that`, `it is important to note that`

A filler word adds length and no fact. Words such as `simply` and `obviously`
also tell a reader who struggles that the step is easy. Delete the word. The
sentence keeps its meaning.

The rule matches whole words in any letter case. It doesn't flag the term
`just-in-time`. The Microsoft style already flags `very`, `really` and
`in order to`, so the list leaves them out.

### A true use of a filler word

Some listed words have a true meaning. In `a just cause`, `just` means fair,
and in a quotation the wording isn't yours. Turn the rule off for the passage,
with the reason in a comment before it:

```markdown
<!-- This sentence names the principle of a just cause. -->
<!-- vale Sealambda.FillerWords = NO -->
The charter requires a just cause for a dismissal.
<!-- vale Sealambda.FillerWords = YES -->
```

## Test the rules

The cases of each rule are in the file `vale/Sealambda/<Rule>.test.yml`. The
hub's flake check `vale-style-tests` runs them with `vale test --coverage`, so a
rule without a case fails the check. To run one rule against a text, add a case
to its file.
