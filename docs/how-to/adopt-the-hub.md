# Adopt the hub in a repository

Use the hub's parts in a Sealambda repository. Adopt the parts the repository
needs. The sections that add a check or run a hub app use the hub input of
[Add the toolchain](#add-the-toolchain). The community files need no step,
because GitHub applies them.

The hub builds the snippets of this page as a flake, the
[synthetic consumer](run-the-synthetic-consumer.md). A change to a snippet
changes `nix/tests/consumers/legacy/flake.nix` in the same commit.

## Add the toolchain

Add the hub as a flake input that the repository's nixpkgs follows, so that
every repository evaluates one nixpkgs revision.

1. Add the hub input, the development shell, the formatter and the formatting
   check to the repository's `flake.nix`. Replace `node` with a dev shell from
   [Toolchain versions](../reference/versions.md). Put the repository's own
   treefmt-nix modules in the list that `mkTreefmt` takes.

   The snippet defines every output for the three systems that the hub
   supports. `forAllSystems` applies a function to the package set of each
   system, and the later snippets of this page add their checks to the set that
   `checks` builds with it. CI runs `nix flake check` on Linux, so a check that
   only `aarch64-darwin` defines doesn't run there.

   ```nix
   {
     inputs = {
       hub.url = "github:sealambda/.github";
       nixpkgs.follows = "hub/nixpkgs";
     };

     outputs =
       {
         self,
         nixpkgs,
         hub,
         ...
       }:
       let
         systems = [
           "x86_64-linux"
           "aarch64-linux"
           "aarch64-darwin"
         ];
         forAllSystems =
           f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
         treefmtFor = forAllSystems (pkgs: hub.lib.mkTreefmt pkgs [ ]);
       in
       {
         devShells = forAllSystems (pkgs: {
           default = pkgs.mkShell {
             inputsFrom = [ hub.devShells.${pkgs.stdenv.hostPlatform.system}.node ];
           };
         });
         formatter = forAllSystems (
           pkgs: treefmtFor.${pkgs.stdenv.hostPlatform.system}.config.build.wrapper
         );
         checks = forAllSystems (pkgs: {
           formatting = treefmtFor.${pkgs.stdenv.hostPlatform.system}.config.build.check self;
         });
       };
   }
   ```

2. Run `nix flake lock`, then `nix flake check`.

The repository's `flake.lock` pins the hub. To take a newer hub revision, run
`nix flake update hub`. Renovate opens the same update as a pull request.

## Take the standards in one call

`lib.mkStandards` gives the checks `formatting`, `docs`, `decisions`,
`workflows`, `pre-commit` and `renovate-config`, the formatter and the hub's
commands from one call. It replaces the calls that the sections below add one
by one, and it returns what those calls return. Use it when the repository
takes all the standards and holds no synced copy of the tool configuration. The
separate functions stay valid: a repository that keeps the synced copies, or
that wants only some checks, follows the sections below.
[Standards contract](../reference/standards-contract.md) defines the arguments
and the result. The synthetic consumer `nix/tests/consumers/standards` has this
shape.

1. Add the hub input, as [Add the toolchain](#add-the-toolchain) shows, and
   call the function once for each system. Set `name` to the name of the
   repository on GitHub, without the owner.

   ```nix
   {
     inputs = {
       hub.url = "github:sealambda/.github";
       nixpkgs.follows = "hub/nixpkgs";
     };

     outputs =
       {
         self,
         nixpkgs,
         hub,
         ...
       }:
       let
         systems = [
           "x86_64-linux"
           "aarch64-linux"
           "aarch64-darwin"
         ];
         forAllSystems =
           f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
         standardsFor = forAllSystems (
           pkgs:
           hub.lib.mkStandards {
             inherit pkgs;
             src = self;
             name = "<repo>";
           }
         );
       in
       {
         formatter = forAllSystems (pkgs: standardsFor.${pkgs.stdenv.hostPlatform.system}.formatter);
         checks = forAllSystems (pkgs: standardsFor.${pkgs.stdenv.hostPlatform.system}.checks);
       };
   }
   ```

2. Run `nix flake lock`, then `nix flake check`. Fix the findings of the first
   run, as the sections [Gate the documentation](#gate-the-documentation),
   [Gate the decision records](#gate-the-decision-records) and
   [Gate the workflows](#gate-the-workflows) say for each check.
3. Optional: add the commands to a dev shell with
   `packages = builtins.attrValues standardsFor.<system>.packages;`.
4. Optional: install the Git hooks. The function installs nothing. To opt in,
   put the `shellHook` of the result in a dev shell of its own that no other
   shell includes, and add `.pre-commit-config.yaml` to the `.gitignore`, as
   [Install the Git hooks](#install-the-git-hooks) explains:

   ```nix
   devShells.hooks = pkgs.mkShell {
     inherit (standardsFor.${pkgs.stdenv.hostPlatform.system}.hooks) shellHook;
   };
   ```

To add to the rules, pass the optional arguments. `treefmtModules` adds the
repository's treefmt-nix modules. `decisions.exclude` lists the paths that the
citation scan skips. `extraHooks` adds hooks of the repository, and `scanner`
replaces the secret scanner. `renovateConfig = false` leaves the check
`renovate-config` out. The repository's own `.vale.ini`,
`.markdownlint-cli2.yaml` or `lychee.toml` layers over the hub's base, as
[Layer your own configuration](#layer-your-own-configuration) says.

`mkStandards.checks` has no secrets gate. The check `pre-commit` runs the hook
`secrets-scan` on a tree with nothing staged, so it scans nothing. The argument
`scanner` reaches the hook and the command `secrets-scan`, and it doesn't reach
the reusable workflow `secrets.yml`. To gate secrets in CI, follow
[Call the reusable workflow](#call-the-reusable-workflow), or run
`secrets-scan history` in a CI step as
[Scan the staged changes](#scan-the-staged-changes) describes.

## Run a hub app

The hub offers the apps `sync-config` and `decisions`. Run an app in the
repository, with the option `--inputs-from .`:

```sh
nix run --inputs-from . hub#<app>
```

The option makes `hub` mean the hub revision that the repository's `flake.lock`
pins, so the app is the version that the checks run. The address
`github:sealambda/.github#<app>` without the option runs the latest `main` of
the hub, which can differ from the pinned revision.

The command needs the `hub` input and its lock, which
[Add the toolchain](#add-the-toolchain) creates. A repository without a `hub`
input has no pinned revision, and Nix stops with the error `cannot find flake
'flake:hub' in the flake registries`. Add the input first. The `decisions` app also
runs from a named hub commit, as
[Retire a decision record](retire-a-decision-record.md) shows.

## Extend the Renovate preset

Renovate resolves `github>sealambda/.github` to `default.json` at the root of
the hub.

1. Extend the preset in the repository's `renovate.json`:

   ```json
   {
     "$schema": "https://docs.renovatebot.com/renovate-schema.json",
     "extends": ["github>sealambda/.github"]
   }
   ```

2. Keep the repository's own `enabledManagers`, `constraints` and
   `packageRules` in the same file. Don't repeat a setting that the
   [preset](../reference/renovate-preset.md) already sets. To change one, such
   as the `schedule`, set it in the repository.

## Set up the tool configuration

The documentation tools take the hub's rules from the hub, with no copy in the
repository, as [Gate the documentation](#gate-the-documentation) says. A
repository sets up its own configuration files in one of two shapes. The
shapes differ in whether the repository holds copies of the hub's files, and
that decides whether the check `config-in-sync` applies.

The check `config-in-sync` (`lib.mkConfigCheck`) compares five files with the
hub's: `.editorconfig`, `.markdownlint-cli2.yaml`, `.vale.ini`, the Vale
vocabulary `Sealambda` and `lychee.toml`. It fails when one is missing or
differs, so a local addition to a copy fails it. A repository keeps the check
only while it keeps every copy unchanged.

### Layer your own configuration

This shape is the recommended one. The repository holds no copy of the hub's
files. It holds only what it adds to the hub's rules, and it has no
`config-in-sync` check. The synthetic consumer `nix/tests/consumers/layered`
has this shape.

1. Add the `docs` check next to `formatting` in the set that `checks` defines
   through `forAllSystems` ([Add the toolchain](#add-the-toolchain)), and no
   `config-in-sync`:

   ```nix
   checks = forAllSystems (pkgs: {
     formatting = treefmtFor.${pkgs.stdenv.hostPlatform.system}.config.build.check self;
     docs = hub.lib.mkDocsCheck pkgs self;
   });
   ```

2. Add the files that the repository needs: a `.vale.ini`, a
   `.markdownlint-cli2.yaml`, a `lychee.toml` or a `.lycheeignore`.
   [Wrapped documentation tools](../reference/wrapped-tools.md) says what each
   file can add. A `.vale.ini` that lists a vocabulary starts with
   `StylesPath = .vale/styles` and `Vocab = Repository`. The vocabulary is the
   file `.vale/styles/config/vocabularies/Repository/accept.txt`, with one term
   per line. Vale stops with an error when a listed vocabulary is missing.
3. Don't run `sync-config` in this repository. The app overwrites `.vale.ini`,
   `.markdownlint-cli2.yaml` and `lychee.toml` with the hub's copies and drops
   the repository's additions.

Editors and the shell formatter read `.editorconfig` from the repository. The
hub's file is `config/editorconfig`. No check keeps a repository's
`.editorconfig` equal to it when the repository has no `config-in-sync` check,
so the repository copies the file again when it takes a hub revision that
changes it.

To relax a markdownlint rule for one directory, add a `.markdownlint-cli2.yaml`
to it. markdownlint-cli2 merges that file with the hub's base, as the hub does
in `.github`.

### Keep the synced copies

This shape is for a repository that keeps every copy exactly as the hub writes
it. The `sync-config` app copies the hub's version of each file into the
repository, and the check `config-in-sync` keeps the copies equal to it. A
repository that holds the copies gets the same findings as one that doesn't.

1. Run `nix run --inputs-from . hub#sync-config` in the repository root, as
   [Run a hub app](#run-a-hub-app) explains. Commit the files that it writes.
2. Create the `Repository` Vale vocabulary,
   `.vale/styles/config/vocabularies/Repository/accept.txt`, with one term per
   line. An empty file is valid. The synced `.vale.ini` lists this vocabulary,
   and Vale stops with an error when a listed vocabulary is missing.
3. To fail CI when a copy differs from the hub, add this attribute next to
   `formatting` in the set that `checks` defines through `forAllSystems`
   ([Add the toolchain](#add-the-toolchain)):

   ```nix
   config-in-sync = hub.lib.mkConfigCheck pkgs self;
   ```

The check compares the copies with the hub revision that `flake.lock` pins. To
take a newer revision, run `nix flake update hub`, then `sync-config`.

A repository that adds a term to a copy of `.vale.ini`, changes another copy,
or removes one, fails `config-in-sync`. It removes the attribute, as the
layered shape does, and keeps its additions in its own files.

### Run Vale in the dev shell

Both shapes use the same wrapper. The `vale` of the hub's `docs` dev shell
starts a Vale that has the Microsoft, Readability and Sealambda styles in the
Nix store and the hub's base configuration. The project `StylesPath`,
`.vale/styles`, holds only the tracked vocabularies and the styles of the
repository. Don't run `vale sync`: the configuration lists no packages. Don't
pass `--no-global`: that flag makes Vale ignore the base and the styles, and
Vale then stops with an error.

To reproduce the gate, run `nix build .#checks.<system>.docs -L`, as
[Gate the documentation](#gate-the-documentation) describes. For an interactive
run, enter the dev shell and run Vale on a file, with no flags:

```sh
nix develop .#docs
vale <file>
```

Define the repository's own `docs` shell with `inputsFrom =
[ hub.devShells.<system>.docs ]`, or add the three wrapped tools to it.

If an earlier `vale sync` left a style directory such as
`.vale/styles/Microsoft`, delete each style directory but keep `config`:
`rm -rf -- .vale/styles/Microsoft .vale/styles/Readability`. Vale takes a rule
from the Nix style when both paths hold a rule of the same name, but a stale
rule that only the old directory has still runs. Keep, or add, these two rules
in the repository's `.gitignore`, so that nobody commits a leftover style
directory:

```gitignore
.vale/styles/*
!.vale/styles/config/
```

Outside `nix develop` or direnv, for example in an editor extension, Vale finds
no styles and reports the same error. Start the editor from the dev shell, or
use direnv with the flake.

## Gate the documentation

The `docs` check lints every Markdown file with markdownlint-cli2, lychee and
Vale. Where the Nix sandbox is enabled, which it always is on Linux CI, the
check reads no personal configuration and needs no network. Each tool starts
with the hub's base configuration from the Nix store, so a repository needs no
configuration file to pass the hub's rules, and the check needs no synced copy
and no `config-in-sync` check. To add to the rules, put a file in the
repository: a `.vale.ini` with the repository's vocabulary or a section for a
folder, a `.markdownlint-cli2.yaml`, a `lychee.toml` or a `.lycheeignore`.
[Set up the tool configuration](#set-up-the-tool-configuration) shows the two
shapes of these files.
[Wrapped documentation tools](../reference/wrapped-tools.md) states what each
file can add and what it can't change, and that the hub doesn't prevent a file
from switching a rule off, so the review of the file is the control.

1. Add the check to the set that `checks` defines through `forAllSystems` in the
   repository's `flake.nix`. Pass `self`, not a list of Markdown files, because
   lychee also checks links to files that aren't Markdown.

   ```nix
   docs = hub.lib.mkDocsCheck pkgs self;
   ```

2. Run `nix flake check`. To run only this check, run
   `nix build .#checks.<system>.docs -L`, with your system for `<system>`, such
   as `aarch64-darwin`. CI needs no separate job: the
   job that runs `nix flake check` runs this check too.
3. If the repository called the hub's earlier `docs.yml` workflow, remove that
   call. The hub no longer offers the workflow.
   - Delete the `docs` job and its entry in the `needs` of the `ci` job.
   - Update any branch protection or ruleset that requires the status check of
     the `docs` job.
   - Replace each documented docs command, for example in `AGENTS.md`, with
     `nix flake check`.

The check builds its tools from the hub's own nixpkgs, whatever nixpkgs the
repository follows, as the `decisions` check does. Every repository then runs
the same version of each tool and of each Vale style, and `nix flake update hub`
updates them. The repository needs no `nixpkgs.follows = "hub/nixpkgs"` for this
check, and no hub package set that it passes by hand.

For an interactive run or an editor, use the `docs` dev shell. It has the same
three wrapped tools as the check, so a command in the shell gives the result of
the check, and no personal Vale configuration changes it.

### Write the current state

The Vale style `Sealambda` keeps a page in the present tense and in the house
style. [Writing style](../reference/writing-style.md) defines its rules:

- `Sealambda.CurrentState` has the level error. It fails the check on a word of
  a plan or a gap, such as `currently` or `will be`.
- `Sealambda.History` has the level suggestion. The check doesn't report it. It
  shows in an editor that runs Vale.
- The other rules of the style have the level warning. They don't fail the
  check, and the check doesn't print them. They show in an editor that runs
  Vale and in a run of Vale without `--minAlertLevel=error`, for example
  `vale .` in the `docs` dev shell. A hub revision that adds a warning rule
  leaves the result of the check unchanged. The table in
  [Writing style](../reference/writing-style.md#rules) lists them.
- The length rules need Vale 3.21 or later. The `docs` check and the `docs`
  dev shell pin a newer version. An editor that runs its own Vale needs
  version 3.21 or later.

The hub's Vale configuration turns `Sealambda.CurrentState` off for
`docs/decisions/` and `docs/specs/`. It turns `Sealambda.HowToTitle` and
`Sealambda.StepLength` on for `docs/how-to/` only. To keep a listed word that's
true in one passage, turn the rule off for that passage with a Vale comment, as
the reference shows.

The hub's lychee configuration also checks the anchors of local links. A link
such as `page.md#heading`, or `#heading` in the same file, fails when the page
has no such heading.

### Take the hub revision with the style

A hub revision that adds the style `Sealambda` and the anchor check breaks a
repository whose pages break them.

1. Run `nix flake update hub`. If the repository keeps the synced copies, run
   `nix run --inputs-from . hub#sync-config` and commit the files that it
   writes.
2. Run `nix build .#checks.<system>.docs -L`. Change each page that
   `Sealambda.CurrentState` flags to state what's true now. Move a plan or an
   open question into an issue. Fix each link that the anchor check reports.
3. Remove the hub package set that the repository's `mkDocsCheck` call passed
   by hand, if there is one. The old call `hub.lib.mkDocsCheck pkgs self` still
   works.

## Gate the decision records

The `decisions` check validates the front matter of the decision records and
the ledger of deleted records, and it fails on a citation of a record, a spec or
a page that doesn't resolve. [Decision records](../reference/decision-records.md)
defines each rule. The check reads no network and no personal configuration.

1. Add the check to the set that `checks` defines through `forAllSystems` in the
   repository's `flake.nix`. Pass `self`, because the check reads every text
   file. Set `repository` to the name of the repository on GitHub. The check
   uses it to tell a citation of this repository from a citation of another one.

   ```nix
   decisions = hub.lib.mkDecisionsCheck pkgs self {
     repository = "sealambda/<repo>";
     exclude = [ ];
   };
   ```

2. Run `nix build .#checks.<system>.decisions -L`. Each finding is a line
   `path:line: message`. CI needs no separate job: the job that runs
   `nix flake check` runs this check too.
3. Fix the findings of the first run. A record often has the status
   `superseded` or `deprecated`, which the schema doesn't allow: delete a
   replaced record and list it in the ledger, as the reference says.
4. Add a path to `exclude` for a file that holds citations on purpose, such as a
   test fixture. The path is relative to the root of the repository.
5. To delete a replaced record later, run the hub's `decisions` app, as
   [Retire a decision record](retire-a-decision-record.md) shows. No flake
   change is needed.

The check builds its tool from the hub's own nixpkgs, whatever nixpkgs the
repository follows. Every repository then runs the same version of the tool, and
`nix flake update hub` updates it. [ADR 0005](../decisions/0005-check-decision-records-with-a-hermetic-flake-check.md)
gives the reasons.

## Gate the workflows

The `workflows` check fails when a job that doesn't call a reusable workflow has
no `timeout-minutes`, and when a workflow that a pull request event triggers has
no `concurrency` group. [Workflow checks](../reference/workflow-checks.md)
defines each rule.

1. Add the check to the set that `checks` defines through `forAllSystems` in the
   repository's `flake.nix`. Pass `self`, because the check reads the workflow
   files of the whole tree.

   ```nix
   workflows = hub.lib.mkWorkflowsCheck pkgs self;
   ```

2. Run `nix build .#checks.<system>.workflows -L`. Each finding is a line
   `path:line: message`. CI needs no separate job: the job that runs
   `nix flake check` runs this check too.
3. Fix the findings of the first run. Set `timeout-minutes` on each job to
   several times the longest run that the job has had. Set a top-level
   `concurrency` group on each pull request workflow.

The check has no option and no exclusion. It builds its tool from the hub's own
nixpkgs, whatever nixpkgs the repository follows, so every repository runs the
same version.

The bound of 360 minutes covers the numbers that a workflow file writes. It
doesn't cover an expression, because the check doesn't read its value, and it
doesn't cover the jobs of a called workflow. [Call the reusable
workflow](#call-the-reusable-workflow) says what that means for `secrets.yml`.

## Gate the commits and branches

The `gitpolicy` tool checks that each commit header is a Conventional Commit and
that a branch name is `<type>/<slug>`. A flake check sees no Git history, so the
tool runs in CI and in the Git hooks of the hub, not in `nix flake check`.
[Git policy](../reference/git-policy.md) defines the rules.

1. Run the tool from the hub input. The command needs no flake output of the
   repository:

   ```console
   nix run --inputs-from . hub#gitpolicy -- range origin/main..HEAD
   nix run --inputs-from . hub#gitpolicy -- branch
   ```

   To put the tool in a dev shell, add `hub.lib.mkGitPolicyTool pkgs` to the
   packages of the shell.

2. Optional: run the commit and branch checks in Git hooks. The hub's hooks do
   so, and [Install the Git hooks](#install-the-git-hooks) adds them. A person
   can skip a hook, so keep the CI job of the next step.
3. Add a job to the repository's pull request workflow. Fetch the whole history
   and check the range from the base commit to the head commit, as the `git-policy`
   job of the hub's `.github/workflows/ci.yml` does. Pass the commits and the
   branch name through `env`, not through the script text, and put `--` before
   the branch name: `gitpolicy branch -- "$HEAD_REF"`. Add the job to the
   `needs` of the `ci` job. A job that runs on pull requests only is skipped on
   a push, so the `ci` job must accept that skip on a push and on no other
   event. The hub's `ci` job shows the `jq` expression.
4. Fix the findings of the first run. The command prints one line for each
   problem, and it exits with status 1 when a commit or a branch breaks a rule.
   A commit that's already on `main` can't change, so check the range from the
   base of the pull request, not the whole history.

The tool builds from the hub's own nixpkgs, whatever nixpkgs the repository
follows. A change of a rule reaches the repository with `nix flake update hub`.
[ADR 0006](../decisions/0006-check-commits-and-branches-with-a-hub-tool.md)
gives the reasons.

## Install the Git hooks

The hub's hooks run its tools on the machine of the person who commits: the
formatter, the documentation check, the workflow checks and the secrets scan
before a commit, the commit message check at the `commit-msg` stage, and the
branch name check before a push. A hook shows a problem sooner, and it gates
nothing, because a person can skip it. Keep the flake checks and the CI jobs
that the sections above add. [Git hooks](../reference/hooks.md) lists what runs
at each stage and what the installer does.

1. Build the hooks in the repository's `flake.nix`, with the formatter that the
   repository already uses for `nix fmt`. Define `hooksFor` in the `let` block
   after `treefmtFor`:

   ```nix
   hooksFor = forAllSystems (
     pkgs:
     hub.lib.mkHooks {
       inherit pkgs;
       src = self;
       treefmt = treefmtFor.${pkgs.stdenv.hostPlatform.system};
     }
   );
   ```

2. Put the `shellHook` in a dev shell of its own that no other shell includes
   with `inputsFrom`, and add the check. A separate shell keeps the installer
   out of the shell that people and CI jobs enter today:

   ```nix
   hooks = pkgs.mkShell {
     inputsFrom = [ hub.devShells.${pkgs.stdenv.hostPlatform.system}.node ];
     inherit (hooksFor.${pkgs.stdenv.hostPlatform.system}) shellHook;
   };
   ```

   ```nix
   pre-commit = hooksFor.${pkgs.stdenv.hostPlatform.system};
   ```

   The first snippet goes next to `default` in the set that `devShells`
   defines, and it includes the same hub shell as `default`. The second snippet
   goes in the set that `checks` defines.

3. Add `.pre-commit-config.yaml` to the `.gitignore`. The shell links the
   configuration under that name.
4. Run `nix build .#checks.<system>.pre-commit -L`. The check runs every
   `pre-commit` hook on all the files, so fix its findings before the first
   commit.
5. Enter the shell with `nix develop .#hooks`, once in each clone. The shell
   installs the hooks. It replaces a `core.hooksPath` that the clone sets, so
   hooks that live in another folder, such as a husky folder, stop running. A
   hook of another tool in `.git/hooks` moves to a `.legacy` file and still
   runs. A global or system `core.hooksPath` makes the shell print a message
   and exit with status 1, and it installs nothing. The
   [reference page](../reference/hooks.md#an-earlier-corehookspath) shows the
   repair.
6. The variable `SKIP` names hooks to leave out of one command, for example
   `SKIP=docs git commit`. A skipped hook moves its failure to CI, and the
   [reference page](../reference/hooks.md#skip-one-hook) states the rule of the
   hub for a commit that a hook refuses.

Pass `extraHooks` to `mkHooks` to add a hook of the repository. A name that a
hub hook uses is an error. A repository that
[takes the standards in one call](#take-the-standards-in-one-call) already has
the hooks as `standards.hooks` and passes the extra hooks as `extraHooks`.

## Call the reusable workflow

The hub offers the reusable workflow `secrets.yml`. It runs its tool from the
repository's flake. The comment at the top of the workflow file states what the
flake must expose.

1. Call the workflow from a job. Pin it to a commit SHA, which Renovate bumps.
   The `runs-on` input is optional. It takes JSON. The `timeout-minutes` input
   is optional too. It takes a whole number of minutes.

   ```yaml
   jobs:
     secrets:
       uses: sealambda/.github/.github/workflows/secrets.yml@<sha>
       permissions:
         contents: read
       with:
         runs-on: '["ubuntu-24.04-arm"]'
         timeout-minutes: 15
   ```

2. List the job in the `needs` of the repository's `ci` job, as the hub's
   `.github/workflows/ci.yml` does.

A job that calls a reusable workflow can't set `timeout-minutes`, so the
workflow sets the limit of its own job from the input `timeout-minutes`. The
default is 360 minutes, the limit that GitHub gives a job that sets none, so a
caller that passes nothing gets that limit. Pass a limit of several times
the longest scan of the repository, as [Gate the workflows](#gate-the-workflows)
advises for a job.

The input accepts any number that a caller passes, a value above 360 included.
The 1 to 360 rule of the `workflows` check covers the workflows of the checked
repository only, so it doesn't judge the value of the input.

## Scan the staged changes

The workflow scans the history in CI. To catch a secret before the commit, run
the hub's `secrets-scan` command in a hook.

1. Get the command from the hub. The `base` dev shell of the hub holds it, and
   a flake can build it with `hub.lib.mkSecretsScan { inherit pkgs; }`.
2. Run `secrets-scan staged` in a `pre-commit` hook. The hub's hooks do so:
   [Install the Git hooks](#install-the-git-hooks). The command exits with
   status 1 when a staged change holds a secret, and it prints the rule, the
   file and the line without the secret.
3. To suppress a finding that isn't a secret, add its fingerprint on its own
   line to `.gitleaksignore`, or put `gitleaks:allow` in a comment on the line.
   The hub's base configuration is the only one, so a `.gitleaks.toml` in the
   repository has no effect on the command. The workflow reads that file, so
   before the hook goes live, move each `[allowlist]` entry that you still need
   to fingerprints in `.gitleaksignore`, which both the workflow and the
   command read. Otherwise the hook reports a finding that the workflow
   accepts.

A repository can also run `secrets-scan history` in its own CI step. The
workflow runs gitleaks alone, so a secret in a file with the attribute `-diff`
or a NUL byte, in a merge commit, or in a history that Git can't read passes
the workflow, and the command stops it.
[Secrets scan](../reference/secrets-scan.md#the-workflow-and-the-command) lists
each case and shows the step. That scan needs the whole history, so the
checkout step sets `fetch-depth: 0`. The
[exit statuses](../reference/secrets-scan.md#exit-status) say what each result
of the command means, and the page lists the limits and how to replace the
scanner.
