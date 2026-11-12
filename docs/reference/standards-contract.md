# Standards contract

The function `lib.mkStandards` gives a repository all the standards of the hub
in one call: the five flake checks, the formatter and the commands of the hub.
It adds no rule and no tool. It calls `lib.mkTreefmt`, `lib.mkDocsCheck`,
`lib.mkDecisionsCheck`, `lib.mkWorkflowsCheck`, `lib.mkSecretsScan`,
`lib.mkGitPolicyTool` and `lib.mkHooks` with the arguments that you pass, so the
result is the one that a call of each function by hand gives. A change of a
rule happens in one place, and every repository that calls `mkStandards` gets
it with `nix flake update hub`.

[Adopt the hub in a repository](../how-to/adopt-the-hub.md#take-the-standards-in-one-call)
shows the steps. This page defines the arguments, the result and the limits.

## Call

Call the function once for each system, with the package set of that system:

```nix
standards = hub.lib.mkStandards {
  inherit pkgs;
  src = self;
  name = "quints";
};
```

## Arguments

The argument set has exactly these names. A name that isn't in the table is an
error.

| Argument | Type | Meaning | Default |
| -------- | ---- | ------- | ------- |
| `pkgs` | Package set | The package set of one system. Only its system is used for the tools, and the formatter modules evaluate with it. | Required. |
| `src` | Path, absolute path string or set with `outPath` | The source tree, normally the `self` of the flake. Every check reads all of it. A string works when it holds an absolute path, such as `"${self}"`. A relative string is an error. | Required. |
| `name` | String | The name of the repository on GitHub, without the owner: 1 to 100 letters, digits, `.`, `-` and `_`, and not `.` or `..`. The name `.github` is valid. The repository is `sealambda/<name>`, and the check `decisions` treats a citation of it as a citation of this repository. | Required. |
| `treefmtModules` | List of modules | treefmt-nix modules of the repository. They add to the organization's formatter in `formatter`, in `checks.formatting` and in the hook `treefmt`. | `[ ]` |
| `decisions` | Set | `{ exclude = [ "<path>" ]; }`, the paths that the citation scan of the check `decisions` skips. A path is relative to the root of the repository. No other key is valid. | `{ exclude = [ ]; }` |
| `hooks` | Set | Hooks of the repository, in the format of git-hooks.nix. They add to the hooks of the hub, as `extraHooks` does in `lib.mkHooks`. | `{ }` |
| `scanner` | Package | The secret scanner of `packages.secrets-scan` and of the hook `secrets-scan`. It needs `meta.mainProgram`, and [Secrets scan](secrets-scan.md) lists what else it must support. | gitleaks of the hub's nixpkgs |

## Result

The result is a set with four attributes:

| Attribute | Content |
| --------- | ------- |
| `checks` | The derivations `formatting`, `docs`, `decisions`, `workflows` and `pre-commit`. |
| `formatter` | The treefmt wrapper, for the output `formatter`. |
| `packages` | The commands `vale`, `markdownlint-cli2`, `lychee`, `secrets-scan`, `gitpolicy` and `workflows`. Each one has `meta.mainProgram`. |
| `hooks` | The evaluation that `lib.mkHooks` returns. |

The checks are the checks of the functions that the page of each tool defines:

| Check | Function | Page |
| ----- | -------- | ---- |
| `formatting` | `lib.mkTreefmt` | [Adopt the hub](../how-to/adopt-the-hub.md#add-the-toolchain) |
| `docs` | `lib.mkDocsCheck` | [Wrapped documentation tools](wrapped-tools.md) |
| `decisions` | `lib.mkDecisionsCheck` | [Decision records](decision-records.md) |
| `workflows` | `lib.mkWorkflowsCheck` | [Workflow checks](workflow-checks.md) |
| `pre-commit` | `lib.mkHooks` | [Git hooks](hooks.md) |

The result has no `config-in-sync` check. A repository that calls `mkStandards`
holds no copy of the hub's tool configuration, and its own files layer over the
hub's base, as
[ADR 0007](../decisions/0007-layer-the-repository-configuration-over-a-hub-base.md)
says. A repository that keeps the synced copies calls the separate functions, as
[Keep the synced copies](../how-to/adopt-the-hub.md#keep-the-synced-copies)
shows.

The tools of the checks `docs`, `decisions` and `workflows`, the commands in
`packages`, the tools of the hooks and the default `scanner` come from the
hub's own nixpkgs, whatever nixpkgs the calling flake uses, so every repository
runs the same version of them. The formatter is the exception. treefmt-nix
evaluates with the `pkgs` that you pass, so the formatter programs, such as
`nixfmt` and `shellcheck`, follow the nixpkgs of the calling flake, in
`formatter`, in `checks.formatting` and in the hook `treefmt` of the check
`pre-commit`. A repository that wants the formatter versions of the hub sets
`nixpkgs.follows = "hub/nixpkgs"`, as the standards consumer does. A `scanner`
that you pass is your own package.

### The check `pre-commit` runs three rules again

The check `pre-commit` runs the hooks `treefmt`, `docs` and `workflows` on every
file. So a run of `nix flake check` runs the formatter, the documentation tools
and the workflow check twice: once in the check of that name and once in
`pre-commit`. The hub keeps both on purpose:

- The check of each name reports one gate, and a branch protection can require
  it by name.
- The check `pre-commit` shows that the hook set builds and passes on the tree,
  with the hooks that the repository adds through `hooks`. Only this check runs
  a hook of the repository.

Removing the hooks from the check would drop that proof, and removing the other
checks would drop the named gates, so the function keeps all five. The cost is
the run time of the three tools. To avoid it, drop the check `pre-commit`, as
the section Limits shows. The hooks still install through the shell that holds
`standards.hooks.shellHook`, but no flake check builds them or runs the hooks
of the repository.

## Put the result in the outputs

```nix
{
  formatter = forAllSystems (pkgs: standardsFor.${pkgs.stdenv.hostPlatform.system}.formatter);
  checks = forAllSystems (pkgs: standardsFor.${pkgs.stdenv.hostPlatform.system}.checks);
}
```

`standardsFor` is `forAllSystems (pkgs: hub.lib.mkStandards { ... })`. The
`packages` go in a dev shell or in the `packages` output.

## Install the hooks

The function installs no hook. The attribute `hooks` holds the `shellHook` that
installs them, and a repository opts in by putting that text in the `shellHook`
of a dev shell of its own, which keeps the installer out of the shell that
people and CI jobs enter today:

```nix
devShells.hooks = pkgs.mkShell {
  inherit (standards.hooks) shellHook;
};
```

Without that line, the repository gets the check `pre-commit` and no installed
hook. A repository that calls the function and doesn't opt in sees no change on
a machine, as
[ADR 0008](../decisions/0008-offer-git-hooks-through-git-hooks-nix.md) states
for the hooks. [Git hooks](hooks.md#install) says which shell can hold the line
and what the installer does.

## Errors

The function checks its argument set before it builds anything. One wrong call
stops the evaluation with one message. The first line is
`mkStandards: the arguments are wrong.`, and each problem follows on its own
line, so one evaluation shows every mistake.

| Situation | Problem line |
| --------- | ------------ |
| An unknown name | ``Unknown arguments: `foo`. The arguments are `decisions`, `hooks`, `name`, `pkgs`, `scanner`, `src`, `treefmtModules`.`` |
| A required argument is missing | ``Missing required arguments: `name`.`` |
| `pkgs` isn't a package set | `` `pkgs` must be a package set, got `set`. `` |
| `src` isn't a path, an absolute path string or a set with `outPath` | `` `src` must be a path, an absolute path string or a set with `outPath`, such as `self`, got `int`. `` |
| `name` isn't a string | `` `name` must be a string, got `int`. `` |
| `name` isn't a repository name: it's empty, longer than 100 characters, `.` or `..`, or it holds a character that a name can't hold | `` `name` must be a repository name of 1 to 100 letters, digits, `.`, `-` and `_`, and not `.` or `..`, got "a b". `` |
| `treefmtModules` isn't a list | `` `treefmtModules` must be a list of modules, got `set`. `` |
| `hooks` isn't a set | `` `hooks` must be a set of hooks, got `list`. `` |
| `decisions` isn't a set | `` `decisions` must be a set, got `list`. `` |
| `decisions` has another key | `` `decisions` has the unknown keys `include`. Its only key is `exclude`. `` |
| `decisions.exclude` isn't a list of strings | `` `decisions.exclude` must be a list of strings, got `list`. `` |
| `scanner` isn't a package | `` `scanner` must be a package, got `string`. `` |
| `scanner` has no `meta.mainProgram` | `` `scanner` must have `meta.mainProgram`, so that `lib.getExe` finds its command. `` |

Two errors come from the functions that `mkStandards` calls. A name in `hooks`
that a hub hook uses stops the evaluation with the message of `lib.mkHooks`,
which lists the names. A module in `treefmtModules` that treefmt-nix rejects
stops it with the message of treefmt-nix.

## Limits

- The function has no switch that turns a part off. The result always holds the
  five checks, the formatter and the six commands. To drop a part, remove it
  from the set before you use it, for example
  `removeAttrs standards.checks [ "pre-commit" ]`.
- The check `pre-commit` doesn't scan for secrets. It runs the hook
  `secrets-scan`, which reads the staged changes, but the check commits the
  source before the run, so nothing is staged and the hook passes. A probe with
  a secret in the tree gave `secrets-scan Passed` with no ignore file, with a
  `.gitleaksignore` fingerprint, and with a `.gitleaks.toml` that holds
  `[allowlist]` or `[extend]`. So no file of the repository changes the result
  of this check, because the check has no result to change.
- `mkStandards` has no secrets gate. A repository adds one with the reusable
  workflow `secrets.yml` or with a CI step that runs `secrets-scan history`,
  and [The workflow and the command](secrets-scan.md#the-workflow-and-the-command)
  compares the two. The argument `scanner` reaches the hook and
  `packages.secrets-scan`, and it doesn't reach `secrets.yml`. [Ways a
  repository switches the scan off](secrets-scan.md#ways-a-repository-switches-the-scan-off)
  lists which files can silence the scan.
- The attribute `hooks` of the call adds hooks. It can't replace a hub hook or
  switch one off, as the options of [Git hooks](hooks.md#options) say.
- The owner of the repository is `sealambda`, and the argument `name` has no
  place for another owner.
- The check of the arguments reads the shape of each value. It doesn't read the
  modules of `treefmtModules` or the hooks of `hooks`: treefmt-nix and
  git-hooks.nix check them when the function builds the result.
- `pkgs` must be the package set of one system. A call for another system needs
  another call, which `forAllSystems` makes.

## How the hub tests it

- The flake check `lib-functions` has the cases `standards-*` in
  `nix/tests/lib/standards.nix`. They cover the attributes of the result, that
  each check is the real check, each optional argument, which parts follow the
  `pkgs` of the caller, and the text of each message in the table above.
- The consumer `nix/tests/consumers/standards` calls only `mkStandards`, with
  the three required arguments, and the CI job `consumer` builds its checks. The
  checks that start with `variant-` call it again with one optional argument
  each, as
  [Run the synthetic consumer](../how-to/run-the-synthetic-consumer.md) says.
