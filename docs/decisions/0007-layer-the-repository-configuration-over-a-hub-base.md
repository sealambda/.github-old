---
status: proposed
date: 2026-11-12
decision-makers: Sealambda maintainers
---

# Layer the repository configuration over a hub base for the documentation tools

## Context and Problem Statement

[ADR 0001](0001-hub-as-single-source-of-standards.md) makes the hub the one
source of standards. The documentation tools Vale, markdownlint-cli2 and lychee
read their rules from files in the repository. The app `sync-config` therefore
copies the hub's file into each repository, and the check `config-in-sync`
fails when a copy differs. Each repository holds a copy of every rule, and a
change of a rule is a change in every repository.

Can the hub pass its own file to each tool and still let a repository add to it?
The hub checked this with the versions in its locked nixpkgs: Vale 3.25.1,
markdownlint-cli2 0.24.0 (markdownlint 0.42.0) and lychee 0.24.2. The tools
differ in how they take a second file:

- Vale reads a global configuration from `$XDG_CONFIG_HOME/vale/.vale.ini` and
  merges the project's `.vale.ini` over it. The option `--config` and the
  variable `VALE_CONFIG_PATH` name one file and don't merge.
- markdownlint-cli2 takes a base file with `--config` and merges the
  `.markdownlint-cli2.yaml` files of the directories over it.
- lychee takes `--config` more than once, merges the files in order, and the
  last value of a single option wins. An explicit `--config` turns the read of
  `lychee.toml` off.

## Decision Drivers

- One copy of each rule, in the hub.
- A change of a rule reaches every repository with the update of the hub input.
- A repository can add vocabulary, folder rules and exclusions.
- The same result in the flake check, in the dev shell and in CI.
- No dependency on a file in the home folder of the user for the flake check.
- A repository that keeps the synced copies gets the findings that it got
  before.

## Considered Options

- Keep `sync-config` as the only way to give the rules
- Wrap each tool and layer the repository's file over the hub's base
- Merge the hub's file and the repository's file with a script, and run the tool
  on the merged file

## Decision Outcome

Chosen option: "Wrap each tool and layer the repository's file over the hub's
base" because each tool has a documented way to read two files, so the hub needs
no merge code, and the tool does the merge that its own users expect.

The wrappers are in `nix/lib/docs.nix`. Each starts the tool of the hub's
nixpkgs with the hub's base in the Nix store:

- Vale: the wrapper sets `XDG_CONFIG_HOME` to a store folder that holds the
  base as the global `.vale.ini`. The base is `config/vale.ini` with two lines
  changed: `StylesPath` names a store folder with the hub's vocabulary, and
  `Vocab` lists only that vocabulary. The folder of the styles stays the one
  that `vale.withStyles` names in `VALE_STYLES_PATH`.
- markdownlint-cli2: `--config` names `config/markdownlint-cli2.yaml`.
- lychee: `--config lychee.toml`, when the file exists, and then
  `--config config/lychee.toml`. The hub's file comes last, so its single
  options win.

The base files are the files that `sync-config` copies, so the hub holds each
rule once. The docs gate needs no copy. `sync-config` and `config-in-sync` stay,
so a repository that keeps the copies gets the same findings: each copy equals
the base. The check `config-in-sync` compares five files, `.editorconfig` among
them, and fails when one is missing or differs, so a repository keeps the check
only while it keeps every copy unchanged. A repository that layers its own
configuration, or removes the copies, removes the check. No check then keeps its
`.editorconfig` equal to the hub's. The adoption page shows both shapes, and the
synthetic consumers `legacy` and `layered` build them.
[Wrapped documentation tools](../reference/wrapped-tools.md) states, for each
tool, what a repository can add and what it can't change.

### Consequences

- Good, because a repository with no configuration file gets the hub's rules,
  and a change of a rule needs no change in the repository.
- Good, because the flake check and the dev shell run the same wrappers.
- Good, because the hub writes no merge code.
- Bad, because the hub doesn't prevent a repository from switching a rule or a
  whole gate off: a Vale section, a markdownlint rule set to `false`, a
  markdownlint file that ignores every file and a lychee exclusion of every link
  all work. The review of the repository's file in its pull request is the
  control. The reference lists the settings.
- Bad, because Vale reads a `.vale.ini` in the home folder or in a folder above
  the repository when the repository has none. The wrapper removes
  `VALE_CONFIG_PATH` from the environment and can't remove those two sources.
  The flake check runs in the Nix sandbox, where neither exists, so the gate of
  record doesn't change.
- Bad, because the hub's markdownlint option `noInlineConfig` holds only while
  no repository file sets it, and a file named `.markdownlint.*` replaces the
  hub's `config` map for its directory.
- Bad, because markdownlint-cli2 replaces the options of a rule that a
  repository file lists: the file must repeat the options that it keeps.
- Bad, because the Vale base is a changed copy of `config/vale.ini`. The build
  fails when the hub's file stops holding the two lines that the wrapper
  changes.

### Confirmation

The flake check `check-docs-tests` runs a project with no configuration file, a
local vocabulary, a local Vale section and style, root and nested markdownlint
files, lychee exclusions and the legacy copies, in the Nix sandbox on Linux and
on macOS. One case compares the findings of a project with the copies and of a
project without them. Further cases cover the unset `VALE_CONFIG_PATH`, the Vale
files in the home folder and above the project, and the settings that switch a
gate off. The check `lib-functions` runs the layers through `lib.mkDocsCheck`.
The job `consumer` of the hub's `ci` workflow builds the checks of the legacy
fixture, which keeps the synced copies, and of the layered fixture, which holds
its own configuration files and no copy.

## Pros and Cons of the Options

### Keep `sync-config` as the only way to give the rules

- Good, because it needs no wrapper.
- Bad, because every repository holds a copy of each rule, and each rule change
  is a pull request in each repository.
- Bad, because a repository can edit its copy until the check complains, and
  it can't add a rule without editing the hub's file.

### Wrap each tool and layer the repository's file over the hub's base

- Good, because one copy of each rule is in the hub.
- Good, because the tools merge the files with their own rules.
- Bad, because each tool needs its own mechanism, and the mechanisms differ in
  what wins.

### Merge the hub's file and the repository's file with a script

- Good, because one merge rule would serve all three tools.
- Bad, because the hub owns a YAML, INI and TOML merge that three tools
  interpret differently.
- Bad, because a tool's own handling of nested files and relative paths isn't
  available on a merged file.

## More Information

- [Wrapped documentation tools](../reference/wrapped-tools.md)
- [Vale: the `.vale.ini` file](https://docs.vale.sh/topics/.vale.ini)
- [markdownlint-cli2](https://github.com/DavidAnson/markdownlint-cli2)
- [lychee](https://github.com/lycheeverse/lychee)
