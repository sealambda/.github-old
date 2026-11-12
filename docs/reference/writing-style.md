# Writing style

A page states what's true now, in the house style of the hub. This page
defines the Vale rules that check both, and the places where they don't apply.
The rule that a document describes only the current state is in
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
| `Sealambda.HeadingCase` | warning | A heading that isn't in sentence case. |
| `Sealambda.HowToTitle` | warning | A page title that isn't a task. |
| `Sealambda.SentenceLength` | warning | A sentence of more than 25 words. |
| `Sealambda.ParagraphLength` | warning | A paragraph of more than 6 sentences. |
| `Sealambda.ListLength` | warning | A list of 1 item or of more than 7. |
| `Sealambda.StepLength` | warning | A numbered step of more than 20 words. |

The `docs` check runs Vale with `--minAlertLevel=error`. A finding of level
error fails the check. A finding of level warning or suggestion doesn't fail
it, and the check doesn't print it. It shows in an editor that runs Vale, and
in a run of Vale without that flag. A rule of level warning tells you what to
change, and it blocks no merge.

The hub's own pages trip the warning rules too, and the `docs` check stays
green because it reports errors only. Run `vale .` in the `docs` dev shell at
the root of the hub to print every finding of level warning and suggestion.

The length rules use the Vale extension point `metric`, which needs Vale 3.21
or later. The `docs` check and the `docs` dev shell pin a newer version. An
editor that runs its own Vale needs version 3.21 or later.

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
<!-- This sentence quotes the title of a talk. -->
<!-- vale Sealambda.OneSpelling = NO -->
The talk is titled "A work flow for small teams".
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

## Heading case

`Sealambda.HeadingCase` flags a heading that isn't in sentence case. In
sentence case, the first word and the proper names start with a capital letter,
and the other words don't. `Install the Git hooks` is in sentence case, and
`Install The Git Hooks` isn't.

One case for all headings makes the pages look alike, and it makes a proper name
stand out. The rule checks headings only, and it skips code in a heading.

The rule accepts these words with their own case:

- An acronym of two to six capital letters, such as `CI` or `AWS`.
- The names of the tools and products that the hub's pages mention, such as
  `GitHub`, `Nix`, `Renovate` and `Vale`. The list is in the key `exceptions`
  of the rule file.
- The names of tools that start with a lowercase letter, such as `lychee`.
- The six section headings of the MADR template for decision records, such as
  `Context and Problem Statement`. The template fixes their case.

A repository adds the proper names of its own to its `Repository` vocabulary,
and the rule reads that file. The rule flags a heading when fewer than 80
percent of its words are in the expected case, so a single name that the lists
don't know can pass in a long heading and fail in a short one.

The word after a colon starts a new sentence, so it takes a capital letter.
`Note: Install hooks` passes, and `Note: install hooks` is flagged.

The Microsoft style has a rule of the same kind, `Microsoft.Headings`, with
the level suggestion. Both rules report a heading that isn't in sentence case,
so one heading can get two findings. The two rules keep different lists of
names that keep their case, so a heading can pass one rule and fail the other.
The hub keeps its own rule for the level warning and for the names of its own
tools. A repository that wants no report of a heading turns off both rules.

### A true use of a heading in another case

A heading that quotes a title needs a Vale comment with the reason before it:

```markdown
<!-- This heading quotes the title of a standard. -->
<!-- vale Sealambda.HeadingCase = NO -->
## The Open Source Definition
<!-- vale Sealambda.HeadingCase = YES -->
```

## How-to titles

`Sealambda.HowToTitle` flags a page title that starts with a label, a question
or a gerund. The title of a how-to page starts with an imperative verb that
names the task, such as `Adopt the hub`. These openers are flagged:

- `How to`, `How do`, `How does`, `How can` and `How should`
- `Guide to`, `Introduction to` and `Tutorial`
- `Adding`, `Configuring`, `Creating`, `Deploying`, `Installing`, `Migrating`,
  `Running`, `Setting up` and `Using`

A reader scans a list of titles for the task to do, and a verb at the start
says what the page does.

### Where the rule is on

The hub's Vale base, `config/vale.ini`, turns `Sealambda.HowToTitle` off for
every page and on again in `docs/how-to/`. The folder can sit under another
folder, so `services/api/docs/how-to/` counts too. A reference page and an
explanation page aren't checked.

### What the rule can't tell

The rule flags an opener that no title needs, and it doesn't check that the
first word is a verb. The list of gerunds leaves out a word that's also a noun,
such as `Writing` in `Writing style`.

A how-to page whose title starts with a listed gerund has two choices. Rename
the title to start with a verb, or turn the rule off for it:

```markdown
<!-- vale Sealambda.HowToTitle = NO -->
# Using the hub
<!-- vale Sealambda.HowToTitle = YES -->
```

## Sentence length

`Sealambda.SentenceLength` flags a sentence of more than 25 words. A long
sentence holds several ideas, and a reader must keep them all in mind to reach
the end. Cut the sentence in two, or delete the words that carry no fact.

The rule counts words in prose, in list items and in table cells. It doesn't
count code spans and code blocks. The Microsoft style has a rule of the same
purpose, `Microsoft.SentenceLength`, with the level suggestion and the limit of
30 words.

Vale finds the end of a sentence with a heuristic. A period inside an
abbreviation such as `e.g.` doesn't end a sentence. A sentence that ends with a
file name such as `CONTRIBUTING.md` joins the next sentence, and the rule can
report the pair as one long sentence. Put the file name in a code span, or end
the sentence with another word.

### A true use of a long sentence

A long sentence can be right, for example a quotation or a legal clause that
must keep its wording. Turn the rule off for the passage, with the reason in a
comment before it:

```markdown
<!-- This sentence quotes a clause of the licence word for word. -->
<!-- vale Sealambda.SentenceLength = NO -->
The clause states that the licence grants to each recipient a worldwide,
royalty-free, non-exclusive and irrevocable right to use, copy, change and
share the work in any medium.
<!-- vale Sealambda.SentenceLength = YES -->
```

## Paragraph length

`Sealambda.ParagraphLength` flags a paragraph of more than 6 sentences. A long
paragraph hides where one idea ends and the next begins. Split it where the
idea changes, or turn a series of parallel facts into a list.

The rule counts the sentences of a paragraph of prose. A list, a table and a
code block aren't paragraphs, so the rule doesn't check them. A paragraph of
many lines that holds one sentence is clean. The rule finds sentences with the
heuristic that the section on sentence length describes.

### A true use of a long paragraph

Turn the rule off for a paragraph that must stay whole, for example a quotation,
with the reason in a comment before it:

```markdown
<!-- This paragraph quotes the abstract of a paper. -->
<!-- vale Sealambda.ParagraphLength = NO -->
One. Two. Three. Four. Five. Six. Seven.
<!-- vale Sealambda.ParagraphLength = YES -->
```

## List length

`Sealambda.ListLength` flags a list of one item and a list of more than seven
items. A list of one item is a sentence, and it reads better as text. A reader
can't scan more than seven items, so group them under headings or split the
list.

The rule checks bulleted and numbered lists. A nested list counts on its own,
and its items don't count for the list around it. The finding is at the first
item of the list.

### A true use of a short or long list

A list can be right at its length, for example a closed set of options that has
eight members. Turn the rule off for the list, with the reason in a comment
before it:

```markdown
<!-- These are the eight levels of the scale. -->
<!-- vale Sealambda.ListLength = NO -->
- One
- Two
- Three
- Four
- Five
- Six
- Seven
- Eight
<!-- vale Sealambda.ListLength = YES -->
```

## Step length

`Sealambda.StepLength` flags a step of a numbered list that has more than 20
words. A reader who follows the steps holds one step in mind while they act, so
a step names one action. Split a long step into two steps, and move the
explanation out of the step.

The rule counts the words of each item of a numbered list, and it doesn't count
code. It counts the first paragraph of a step. A second paragraph and a nested
list under a step aren't counted. A bulleted list isn't checked.

The hub's Vale base, `config/vale.ini`, turns the rule off for every page and
on again in `docs/how-to/`, as it does for `Sealambda.HowToTitle`. A numbered
list on another page isn't checked.

### A true use of a long step

A step can need more words, for example a command that the step quotes in
prose. Turn the rule off for the list, with the reason in a comment before it:

```markdown
<!-- This step quotes the output of the tool word for word. -->
<!-- vale Sealambda.StepLength = NO -->
1. Read the line that says one two three four five six seven eight nine ten
   eleven twelve thirteen fourteen fifteen sixteen seventeen.
2. Stop.
<!-- vale Sealambda.StepLength = YES -->
```

## Test the rules

The cases of each rule are in the file `vale/Sealambda/<Rule>.test.yml`. The
hub's flake check `vale-style-tests` runs them with `vale test --coverage`, so a
rule without a case fails the check. To run one rule against a text, add a case
to its file.
