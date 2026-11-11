"""Release the hub: one tag and one GitHub release for each merge to `main`.

The tag series, the rule for the answer `rules changed: yes|no` and the limits
are in `docs/reference/hub-releases.md`. The modules split the work in pure
functions and a thin layer for the tools:

- `release.tags` parses tag names and computes the next version.
- `release.paths` decides from changed paths whether the rules changed.
- `release.notes` renders the text of a release.
- `release.runner` runs `git` and `gh` as child processes.
- `release.repo` asks git the questions that the plan needs.
- `release.plan` combines them into a `Plan` without a side effect.
- `release.publish` creates the GitHub release for a `Plan`.
- `release.cli` is the command line.
"""
