"""Accept the expression form of `install_url` in the setup action of the hub.

A workflow must write the installer address of the manifest's version in full.
The composite action `setup-nix` serves every job of the hub, so it can't
repeat the number: it builds the address from the output of an earlier step.
This module accepts that one expression in that one file. The expression is
`EXPRESSION_URL`: the installer address in which the version is
`${{ steps.version.outputs.nix }}`.

The check holds the step `version` to a fixed shape: it must equal a constant.
The expression passes only when both conditions hold:

1. The file is `.github/actions/setup-nix/action.yml`, at that path from the
   checked root. No other file may use the expression.
2. Exactly one earlier step has the id `version`, and that step equals
   `READ_VERSION_STEP`, key for key and byte for byte. The step runs the file
   `read-version.sh` of the action folder on the `versions.json` at the root
   of the tree.

A step that equals the constant has no room for another command, another key
of the manifest, another file or a condition. The step holds no logic: the
logic is the file `read-version.sh`, which its own unit tests run against
manifests. So the check proves that the action runs that file on the root
manifest. It doesn't read the file, and it doesn't run the action.

The check holds only the step `version`. It doesn't read the other steps of
the action, such as one between that step and the installer, or the keys of
the installer step other than `install_url`. Review covers those. The job
`flake-check` of the hub's `ci.yml` asserts at run time that the installed
`nix` has the version of the manifest, and no other job asserts it.
"""

from decisions.findings import Finding
from decisions.workflow_files import ActionsFile, Location

SETUP_NIX_ACTION = ".github/actions/setup-nix/action.yml"
"""The one file that may use the expression form, relative to the checked root."""

EXPRESSION_URL = (
    "https://releases.nixos.org/nix/nix-${{ steps.version.outputs.nix }}/install"
)
"""The only expression that the installer step of that file may use."""

READ_VERSION_STEP: dict[object, object] = {
    "id": "version",
    "shell": "bash",
    "env": {"ACTION_DIR": "${{ github.action_path }}"},
    "run": ('bash "$ACTION_DIR/read-version.sh" "$ACTION_DIR/../../../versions.json"'),
}
"""The step that writes the output `nix`, as the check requires it.

`github.action_path` is the folder of the action, so `../../../versions.json`
from it is the manifest at the root of the repository that holds the action:
the file `SETUP_NIX_ACTION` is three folders below that root. The step has no
other key, so no `if`, `continue-on-error` or `working-directory` can change
what it does. To change the step, change this constant and the action file
together.
"""

_PRODUCER_ID = "version"


def is_expression_form(source: ActionsFile, install_url: object) -> bool:
    """Tell whether an `install_url` is the expression of the setup action.

    Args:
        source: The file that holds the installer step.
        install_url: The value of the `install_url` input of the step.

    Returns:
        `True` only for `EXPRESSION_URL` in the file `SETUP_NIX_ACTION`. The
        same text in any other file is a literal that differs from the
        installer address, so the caller reports it.
    """
    return install_url == EXPRESSION_URL and source.path == SETUP_NIX_ACTION


def check_producer(source: ActionsFile, location: Location) -> Finding | None:
    """Return a finding when the step before the installer isn't the canonical one.

    Args:
        source: The setup action file that holds the installer step.
        location: The location of the installer step: `runs`, `steps`, index.

    Returns:
        A finding on the `install_url` line, or `None` when exactly one earlier
        step has the id `version` and equals `READ_VERSION_STEP`.
    """
    problem = _producer_problem(source, location)
    if problem is None:
        return None
    return source.finding(
        [*location, "with", "install_url"],
        f"install_url reads the output nix of the step {_PRODUCER_ID}, but {problem}",
    )


def _producer_problem(source: ActionsFile, location: Location) -> str | None:
    """Return what is wrong with the earlier steps, or `None` when it's right."""
    producers = [
        step
        for step in _earlier_steps(source.document.data, location)
        if step.get("id") == _PRODUCER_ID
    ]
    if len(producers) != 1:
        return (
            f"{len(producers)} earlier steps have the id {_PRODUCER_ID}, "
            "and exactly one must"
        )
    differing = _differing_keys(producers[0])
    if not differing:
        return None
    return (
        f"the step {_PRODUCER_ID} isn't READ_VERSION_STEP of "
        f"nix/scripts/versions/action_output.py: it differs in "
        f"{', '.join(differing)}"
    )


def _differing_keys(step: dict[object, object]) -> list[str]:
    """Return the keys that the step and `READ_VERSION_STEP` don't share.

    A key counts when only one of them has it, or when the values differ. The
    result is sorted, so a finding reads the same on every run.
    """
    keys = step.keys() | READ_VERSION_STEP.keys()
    return sorted(
        str(key)
        for key in keys
        if key not in step
        or key not in READ_VERSION_STEP
        or step[key] != READ_VERSION_STEP[key]
    )


def _earlier_steps(data: object, location: Location) -> list[dict[object, object]]:
    """Return the step mappings that come before the step at `location`.

    The location ends with the index of the step in its `steps` list. The
    walk follows the keys of the location, so a shape that isn't a list gives
    no steps.
    """
    node = data
    for key in location[:-1]:
        if isinstance(node, dict) and isinstance(key, str):
            node = node.get(key)
        else:
            return []
    index = location[-1]
    if not isinstance(node, list) or not isinstance(index, int):
        return []
    return [step for step in node[:index] if isinstance(step, dict)]
