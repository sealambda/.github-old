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

`sync-config` copies the same files into a repository, so the hub keeps one
copy of each rule. A repository that holds those copies gets the findings of a
repository without them, because each copy equals the base. The flake check
`config-in-sync` keeps the copies equal to the hub.

A repository needs no configuration file of its own. With none, the hub's rules
apply alone. A repository adds a file to extend a tool, as the sections below
say. No wrapper reads a configuration file from the home folder of the user.

The hub doesn't prevent a repository from switching off a rule of the hub where
the tool allows it. Each tool section names the setting. The review of the
repository's configuration file is the control, so a pull request that adds one
of these settings needs a reviewer's attention.

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
  `BasedOnStyles = Project` in a section, run next to the styles of the hub.
  The entries of `BasedOnStyles` add to the hub's entries.

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
configuration has no effect, because the wrapper replaces `XDG_CONFIG_HOME`.

## Where the tests are

The flake check `check-docs-tests` runs `nix/tests/check-docs.sh`. It builds
projects with no file, with a local vocabulary, with a Vale section, with
nested and root markdownlint files, with lychee exclusions and with the legacy
copies, and it compares the findings of a project that holds the copies with
those of a project that holds none. The flake check `lib-functions` runs the
same layers through `lib.mkDocsCheck`.
