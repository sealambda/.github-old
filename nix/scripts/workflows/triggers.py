"""Read the events that trigger a workflow."""

from dataclasses import dataclass

from decisions.workflow_files import Location

_ON_KEY = "on"


@dataclass(frozen=True)
class Trigger:
    """One event that triggers a workflow.

    Attributes:
        name: The name of the event, such as `pull_request`.
        location: The keys and indexes that lead from the root of the document
            to the event, for the line of a finding.
    """

    name: str
    location: Location


def read_triggers(document: object) -> list[Trigger]:
    """Return the events that the `on` key of a workflow names.

    GitHub reads `on` as a name (`on: push`), a list of names
    (`on: [push, pull_request]`) or a mapping that has one key for each name.
    PyYAML follows YAML 1.1, where the plain word `on` is the boolean true, so
    the parsed key of an unquoted `on` is `True` and the parsed key of a quoted
    `"on"` is a string. Both are read. A value of another shape gives no
    trigger: actionlint reports it.

    Args:
        document: The parsed workflow.

    Returns:
        The events in the order of the file, or an empty list.
    """
    if not isinstance(document, dict):
        return []
    for key, value in document.items():
        if key is True or key == _ON_KEY:
            return _triggers_of(value)
    return []


def _triggers_of(value: object) -> list[Trigger]:
    """Return the events of the value of the `on` key."""
    if isinstance(value, str):
        return [Trigger(value, [_ON_KEY])]
    if isinstance(value, list):
        return [
            Trigger(name, [_ON_KEY, index])
            for index, name in enumerate(value)
            if isinstance(name, str)
        ]
    if isinstance(value, dict):
        return [
            Trigger(name, [_ON_KEY, name]) for name in value if isinstance(name, str)
        ]
    return []
