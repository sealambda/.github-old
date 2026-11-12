"""The command line of the tool.

Usage:

    presetcompat check OLD NEW

OLD is version 1 of the Renovate preset and NEW is version 2. Exit status: 0
when NEW keeps every invariant of `presetcompat.compare`, 1 when it breaks one,
2 for a usage error or a file that cannot be read or isn't a JSON object, 3 for
an internal error. Each finding is printed to standard output as
`path:line: message`, all in one run.

What a clean run proves: NEW, read as JSON, keeps the values and the rules that
`presetcompat.compare` and `presetcompat.guards` list. It keeps every package
rule of OLD unchanged, the 7 day release age, the OSV alerts, the schedule of
the lock file maintenance, the top-level `schedule`, `rebaseWhen`, the rebase of
a rule that merges by itself, the rules for the tags of the hub, the two rules
that add the label `breaking`, and the merge rule of the hub input with its
source. It adds no rule that disables a package, shortens the age or merges a
major update, and sets no `ignorePresets`. It checks a fixed list of switches,
not every setting: the top-level `enabled`, `lockFileMaintenance.enabled`,
`nix.enabled`, `mise.enabled`, `ignorePresets`, and `enabled` in a rule that NEW
adds. The list is in `presetcompat.guards`, `_check_switches` and
`_added_rule_problems`. A switch that the list doesn't name, such as the
`enabled` key of another manager, isn't read.

What it does not prove: the tool doesn't run Renovate and doesn't evaluate the
package rules in the order in which Renovate applies them. A later rule can
still override an earlier one in a way that no invariant sees, except where an
invariant looks at the keys of one rule. It doesn't read the presets that NEW
extends, so it can't tell what `config:best-practices` sets.

An internal error is an exception that the tool does not expect, which means a
bug in the tool. The traceback goes to standard error. Status 1 stays reserved
for findings, so that a caller can tell a bug from a problem in the preset.
"""

import argparse
import json
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from presetcompat.compare import compare
from presetcompat.values import Preset

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3


class InputError(Exception):
    """The command line or an input file is wrong, not the preset."""


class _Parser(argparse.ArgumentParser):
    """An argument parser that raises `InputError` instead of exiting."""

    def error(self, message: str) -> NoReturn:
        """Raise `InputError` with the usage text and the problem."""
        raise InputError(f"{self.format_usage().strip()}\n{self.prog}: {message}")


def _parse(argv: Sequence[str]) -> tuple[Path, Path]:
    """Parse the arguments and return the paths of OLD and NEW.

    Raises:
        InputError: The command is missing or unknown, or a path is missing.
    """
    parser = _Parser(
        prog="presetcompat",
        description="Check that a new version of the Renovate preset keeps the "
        "guarantees of the old one.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="compare two versions of the preset")
    check.add_argument("old", type=Path, metavar="OLD", help="version 1")
    check.add_argument("new", type=Path, metavar="NEW", help="version 2")
    arguments = parser.parse_args(argv)
    old: Path = arguments.old
    new: Path = arguments.new
    return old, new


def _load(path: Path) -> Preset:
    """Read a preset file.

    Raises:
        OSError: The file cannot be read.
        InputError: The file isn't JSON, or its top level isn't an object.
    """
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:  # bad JSON, and bytes that aren't UTF-8
        raise InputError(f"{path} is not JSON: {error}") from error
    if not isinstance(value, dict):
        raise InputError(f"{path} is not a JSON object")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    """Compare two presets and return the exit status.

    Args:
        argv: The arguments after the program name. `None` reads `sys.argv`.

    Returns:
        `EXIT_CLEAN`, `EXIT_FINDINGS`, `EXIT_USAGE` or `EXIT_INTERNAL`. An
        exception that no other clause handles is a bug in the tool: its
        traceback goes to standard error and the status is `EXIT_INTERNAL`.
    """
    try:
        old, new = _parse(sys.argv[1:] if argv is None else argv)
        findings = compare(_load(old), _load(new), new.as_posix())
    except (InputError, OSError) as error:
        print(f"presetcompat: {error}", file=sys.stderr)
        return EXIT_USAGE
    except Exception:  # the last resort: report any bug with its trace
        traceback.print_exc()
        print("presetcompat: internal error, the traceback is above", file=sys.stderr)
        return EXIT_INTERNAL
    for finding in findings:
        print(finding.format())
    if findings:
        print(f"presetcompat: {len(findings)} finding(s)", file=sys.stderr)
        return EXIT_FINDINGS
    return EXIT_CLEAN
