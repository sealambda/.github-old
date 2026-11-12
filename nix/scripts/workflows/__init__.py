"""Check that the workflows of a tree bound their cost.

A job has a time limit, and a workflow that a pull request triggers has a
concurrency group, so that a runaway job or a burst of pushes can't spend
runner minutes without bound. `workflows.triggers` reads the events of a
workflow, `workflows.rules` holds the two rules, `workflows.check` applies them
to a tree and `workflows.cli` is the command line. The contract is in
`docs/reference/workflow-checks.md`.
"""
