# Wrapped documentation tools

The hub runs Vale, markdownlint-cli2 and lychee through wrappers. A wrapper is
a command with the name of its tool. It starts the tool of the hub's nixpkgs
with the hub's base configuration from the Nix store, and it lets the
repository's own configuration file add to that base. The `docs` check
(`lib.mkDocsCheck`) and the `docs` dev shell run the same three wrappers, so a
command in the shell gives the result of the check. The choice of this
mechanism is in
[ADR 0007](../decisions/0007-layer-the-repository-configuration-over-a-hub-base.md).

## Where the base comes from

The base of each tool is a file of the hub's `config/` folder:

| Tool | Base file | How the wrapper passes it |
| ---- | --------- | ------------------------- |
| Vale | `config/vale.ini`, with its `StylesPath` and `Vocab` lines changed | `XDG_CONFIG_HOME` names a store folder, so the base is Vale's global configuration |
| markdownlint-cli2 | `config/markdownlint-cli2.yaml` | `--config <file>` |
| lychee | `config/lychee.toml` | `--config <file>`, after the repository's `lychee.toml` |

`sync-config` copies the same files, and the file `.editorconfig`, into a
repository, so the hub keeps one copy of each rule. A repository that holds
those copies gets the findings of a repository without them, because each copy
equals the base. The docs check needs no copy: it reads the base from the Nix
store.

The flake check `config-in-sync` compares five synced files with the hub's:
`.editorconfig`, `.markdownlint-cli2.yaml`, `.vale.ini`, the Vale vocabulary
`Sealambda` and `lychee.toml`. It fails when one is missing or differs, so a
local addition to a copy fails it. A repository keeps the check only while it
keeps every copy unchanged. A repository that layers its own configuration, or
removes the copies, removes the check. No check then keeps its `.editorconfig`
equal to the hub's: the docs tools don't read that file, and editors and the
shell formatter do. [Adopt the hub in a repository](../how-to/adopt-the-hub.md#set-up-the-tool-configuration)
shows both shapes.

A repository needs no configuration file of its own. With none, the hub's rules
apply alone. A repository adds a file to extend a tool, as the sections below
say.

## Configuration that the wrappers leave open

markdownlint-cli2 and lychee read no configuration file from the home folder
or from a folder above the repository. The test cases put a
`.markdownlint-cli2.yaml`, a `lychee.toml` and a `.lycheeignore` in both
places, and the findings stay the same.

Vale looks for the nearest `.vale.ini` from the working directory upward and
then in the home folder. The wrapper removes `VALE_CONFIG_PATH` from the
environment, because Vale reads the file that the variable names instead of the
repository's `.vale.ini`. Two sources remain that the wrapper can't remove:

- A `.vale.ini` in the home folder, `~/.vale.ini`.
- A `.vale.ini` in a folder above the repository.

Each of the two applies only when the repository has no `.vale.ini` of its own,
because Vale then takes the nearest file. A repository with its own `.vale.ini`
ignores both. Vale accepts other names for the file, such as `_vale.ini`
([Vale: the `.vale.ini` file](https://docs.vale.sh/topics/.vale.ini)).

The flake check `docs` runs in the Nix sandbox, where the home folder is the
empty build folder and the source sits in the Nix store with no `.vale.ini`
above it, so neither source affects the gate of record. A run outside the
sandbox, such as the dev shell in a checkout below a folder that holds a
`.vale.ini`, can differ from the check for a repository with no `.vale.ini` of
its own. A repository with a `.vale.ini` gets the same result in both.

## Vale

The wrapper sets `XDG_CONFIG_HOME`, and Vale reads the base from
`$XDG_CONFIG_HOME/vale/.vale.ini` as its global configuration. Vale then merges
the first `.vale.ini` that it finds from the working directory upward over it.
The base lists the vocabulary `Sealambda` and the styles Vale, Microsoft,
Readability and Sealambda. It turns `Sealambda.CurrentState` off for the
decision records and the specs.

A repository can add these in its `.vale.ini`:

- Vocabularies. `Vocab = Repository` makes Vale read the terms in
  `.vale/styles/config/vocabularies/Repository/accept.txt`, next to the hub's
  terms. The setting `StylesPath = .vale/styles` names the folder. Vale looks
  in the folder of the hub and in the folder of the repository.
- A `[glob]` section for a folder or a file, with a rule set to `NO` or a
  level. `[docs/**/*.md]` with `Microsoft.Contractions = NO` changes only the
  pages of `docs/`.
- A style of its own. A folder `.vale/styles/Project` with rule files, and
  `BasedOnStyles = Project` in the section `[*.md]`, run next to the styles of
  the hub: the entries of `BasedOnStyles` add to the hub's entries only in a
  section with the same glob as the hub's. A section for another glob, such as
  `[docs/**/*.md]`, replaces the list for the files that it matches, so the
  hub's styles stop running there. That section must repeat the hub's list,
  `Vale, Microsoft, Readability, Sealambda`, and add the style of its own.

A repository can't change these:

- The version of Vale and the rule files of the styles Microsoft, Readability
  and Sealambda. The hub's `flake.lock` pins them, and no run downloads a
  style.
- The alert level of the check. The check passes `--minAlertLevel=error`, and a
  `MinAlertLevel` in the file doesn't lower it.

A repository can switch a rule of the hub off. The section `[*.md]` with
`Sealambda.CurrentState = NO` makes every page pass that rule. A section for one
folder does the same for that folder, and a Vale comment in a page does it for
a passage.

Don't run Vale with `--no-global`. The flag makes Vale ignore the base and
`VALE_STYLES_PATH`, and it stops with an error when no `.vale.ini` exists. The
base's `StylesPath` holds only the vocabulary of the hub, and
`VALE_STYLES_PATH` holds the styles: the two folders must differ, or Vale
prefixes the rule names with a hash and a section that names a rule doesn't
match.

## markdownlint-cli2

The wrapper passes `--config` with the base file. markdownlint-cli2 merges the
`.markdownlint-cli2.yaml` file of the working directory over it, and the same
file of each directory that holds a Markdown file over that directory's pages.
The base sets `gitignore`, `noInlineConfig` and the `config` map of rules.

A repository can add these:

- A root `.markdownlint-cli2.yaml` that switches rules off or sets their
  options. The key `config` merges by rule: a rule that the file lists
  replaces the options of the base for that rule, and the other rules of the
  base stay. A file with `MD013: {line_length: 100}` drops the base's
  `tables: false` for MD013, so the file must repeat each option that it keeps.
- A `.markdownlint-cli2.yaml` in a directory, for the pages of that directory
  and its subdirectories.

A repository can't change the version of markdownlint-cli2 or the set of rules
that markdownlint provides.

Only the files named `.markdownlint-cli2.*` merge with the base. A file named
`.markdownlint.*`, without `cli2`, replaces the whole `config` map of the base
for its directory: the hub's `MD013` and `MD060` settings don't apply there.
Use the `.markdownlint-cli2.yaml` name.

A single option of the base, such as `noInlineConfig`, holds only while no file
of the repository sets it. A file with `noInlineConfig: false` lets a page
switch a rule off with a comment, and a file with `gitignore: false` makes the
tool lint ignored files. A file can also switch any rule off with
`<rule>: false`. These are the settings that the review of the file covers.

## lychee

lychee reads one `lychee.toml` from the working directory by default, and an
explicit `--config` turns that read off. The wrapper therefore passes the
`lychee.toml` of the working directory when it exists, and then the base file.
lychee reads the files in that order. The check passes only `--no-progress` and
the input pattern besides.

A repository can add these:

- Entries in a list option of its `lychee.toml`. The lists of the files join:
  `exclude_path = ["drafts"]` adds `drafts` to the hub's `.git` and
  `node_modules`, and `exclude` adds link patterns to the hub's.
- A `.lycheeignore` file in the working directory. Each line is a regular
  expression for the links to leave out.

A single option takes the value of the last file, which is the hub's, so these
hub values win over the repository's:

- `offline = true`. A repository can't make the check use the network.
- `include_fragments = "anchor-only"`. A repository can't turn the anchor check
  off with `include_fragments = "none"`.

An option that the base doesn't set takes the repository's value. A repository
can leave a link or a folder out of the check with the lists above, which also
hides a broken link in it. The review of the file covers that. lychee reads
only the `lychee.toml` of the working directory, and no file of a
subdirectory.

## What a repository can switch off

The hub doesn't prevent a repository from switching off a rule of the hub, or a
whole gate, with its own configuration file. Each setting below makes the tool
pass a page that breaks the hub's rules. The settings were run against the
tools that the hub pins.

| Tool | Setting in the repository's file | Effect |
| ---- | -------------------------------- | ------ |
| markdownlint-cli2 | `ignores: ["**"]` in `.markdownlint-cli2.yaml` | The tool lints no file. |
| markdownlint-cli2 | `config: {default: false}` in `.markdownlint-cli2.yaml` | Every rule is off. |
| markdownlint-cli2 | `default: false` in a `.markdownlint.yaml` | Every rule is off for its directory, and the base's `MD013` and `MD060` options don't apply there. |
| markdownlint-cli2 | `noInlineConfig: false` | A page switches a rule off with a comment. |
| Vale | `BlockIgnores = (?s).*` or `TokenIgnores = .+` in a `[*.md]` section | Vale checks no text. |
| Vale | `Vale = NO`, `Microsoft = NO`, `Readability = NO` and `Sealambda = NO` in a `[*.md]` section | Each style is off, so Vale reports nothing. One of them switches off one style. |
| Vale | `<Style>.<Rule> = NO` | One rule is off. |
| lychee | `exclude = [".*"]` in `lychee.toml` | lychee checks no link. |
| lychee | `exclude_path` with a folder | lychee skips the folder. |

The hub keeps what a file can't change: the versions of the tools, the Vale
alert level of the check, `offline` and `include_fragments` of lychee, and the
rule files of the styles.

The control is the review of the repository's pull request. A repository's
configuration file is a local exception, and the reviewer of the pull request
that adds or changes one decides whether it's acceptable. No hub check blocks
these settings.

## The dev shell

The `docs` dev shell has the three wrappers. Run a tool from the root of the
repository for the result that the check gives:

```console
nix develop .#docs
vale <file>
markdownlint-cli2 "**/*.md"
lychee --no-progress "**/*.md"
```

Vale finds the `.vale.ini` of the repository from any subfolder. lychee reads
its `lychee.toml` from the folder where it runs. A personal global Vale
configuration in the user's config folder has no effect, because the wrapper
replaces `XDG_CONFIG_HOME`, and `VALE_CONFIG_PATH` has no effect, because the
wrapper removes it from the environment. [Configuration that the wrappers leave
open](#configuration-that-the-wrappers-leave-open) lists the sources that still
apply.

## Where the tests are

The flake check `check-docs-tests` runs `nix/tests/check-docs.sh`. It builds
projects with no file, with a local vocabulary, with a Vale section, with
nested and root markdownlint files, with lychee exclusions and with the legacy
copies, and it compares the findings of a project that holds the copies with
those of a project that holds none. It also covers the vocabulary of the hub,
the `MinAlertLevel` setting that doesn't lower the alert level, the unset
`VALE_CONFIG_PATH`, a page that breaks only rules of the level warning and
still passes, the Vale files in the home folder and above the project, the
files above the project that markdownlint-cli2 and lychee ignore, and each
setting of the section
[What a repository can switch off](#what-a-repository-can-switch-off).
The flake check `lib-functions` runs
the same layers through `lib.mkDocsCheck`. The synthetic consumers `legacy` and
`layered` build the checks for the two shapes of
[Adopt the hub in a repository](../how-to/adopt-the-hub.md#set-up-the-tool-configuration).
The check `docs` of `layered` passes without the base too, so its check
`docs-hub-base` lints one page that breaks a rule of each tool's base and
passes only when the docs check fails on all three findings.
