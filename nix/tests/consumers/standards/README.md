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
check that must fail without it.
