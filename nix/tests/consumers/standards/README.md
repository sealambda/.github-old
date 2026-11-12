# Standards consumer

This folder is a repository that takes all the standards of the hub with one
call. Its flake calls only `lib.mkStandards`, with the three required
arguments, and it holds no tool configuration and no `config-in-sync` check.
The checks `formatting`, `docs`, `decisions`, `workflows` and `pre-commit`
come from that call. The `default` shell only puts the commands of the hub on
`PATH`. The `hooks` shell opts in to the Git hooks, and the file `.gitignore`
lists the link that this shell writes.

The checks that start with `variant-` call the function again, one for each
optional argument, on a copy of this folder with one more file. Each argument
has a check that passes with it and, where the argument changes a verdict, a
check that must fail without it. The check `variant-treefmt-modules` passes
because a module keeps a badly formatted file out of the formatter, and
`variant-decisions-exclude` passes because the folder `fixtures` is out of the
citation scan. The checks `variant-treefmt-modules-needed` and
`variant-decisions-exclude-needed` pass only when the same files fail without
the argument. The check `variant-hooks` passes only when a hook of the
repository fails the check `pre-commit`, and `variant-scanner` passes only when
`secrets-scan` runs the scanner that the repository gives.
