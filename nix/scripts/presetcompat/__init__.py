"""Check that a new version of the Renovate preset keeps the old guarantees.

The hub ships `default.json` (version 1) and `v2.json` (version 2) side by
side, and a repository moves from one to the other when it chooses. Version 2
may change behavior on purpose, but it must not lose a guarantee of version 1 by
accident. `presetcompat.compare` holds the invariants and `presetcompat.cli` is
the command line. The contract is in `docs/reference/renovate-preset.md`.
"""
