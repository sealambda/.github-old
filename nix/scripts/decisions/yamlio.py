"""Load YAML so that dates stay strings, and find the line of a value."""

from collections.abc import Sequence
from dataclasses import dataclass

import yaml
from yaml.nodes import MappingNode, Node, SequenceNode

_TIMESTAMP_TAG = "tag:yaml.org,2002:timestamp"


class _TextDatesLoader(yaml.SafeLoader):
    """A safe YAML loader that does not turn `2026-11-08` into a `date`.

    The schemas say that a date is a string, and a record writes its date
    without quotes. Removing the implicit timestamp rule keeps the text.
    """


_TextDatesLoader.yaml_implicit_resolvers = {
    first_char: [(tag, pattern) for tag, pattern in resolvers if tag != _TIMESTAMP_TAG]
    for first_char, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


@dataclass(frozen=True)
class YamlDocument:
    """A parsed YAML document with the node tree that holds the line marks.

    Attributes:
        data: The Python value of the document, `None` for an empty document.
        root: The root node, `None` for an empty document.
    """

    data: object
    root: Node | None


def parse_yaml(text: str) -> YamlDocument:
    """Parse one YAML document.

    Args:
        text: The YAML text.

    Returns:
        The value and the node tree of the document.

    Raises:
        yaml.YAMLError: The text is not valid YAML, or holds several documents.
    """
    loader = _TextDatesLoader(text)
    try:
        root = loader.get_single_node()
        data = loader.construct_document(root) if root is not None else None
    finally:
        loader.dispose()
    return YamlDocument(data=data, root=root)


def describe_error(error: yaml.YAMLError) -> tuple[int, str]:
    """Return the 1-based line and the problem text of a YAML syntax error.

    Args:
        error: The error that `parse_yaml` raised.

    Returns:
        The line that PyYAML marks, or 1 when it marks none, and its problem
        text, or a generic text when it gives none.
    """
    mark = getattr(error, "problem_mark", None)
    line = mark.line + 1 if mark is not None else 1
    problem = getattr(error, "problem", None) or "the YAML is invalid"
    return line, str(problem)


def line_of(root: Node | None, path: Sequence[str | int]) -> int:
    """Return the 1-based line of the value at `path`, relative to the text.

    A step is a mapping key or a sequence index. The walk stops at the
    deepest node that exists, so a missing key gives the line of its parent.
    The line of a mapping key is the line of the key, not of its value.

    Args:
        root: The root node of the document, or `None` for an empty document.
        path: The keys and indexes that lead to the value.

    Returns:
        The line of the node that the path reaches, or 1 for an empty document.
    """
    if root is None:
        return 1
    node = root
    line = root.start_mark.line + 1
    for step in path:
        found = _step(node, step)
        if found is None:
            break
        node, line = found
    return line


def _step(node: Node, step: str | int) -> tuple[Node, int] | None:
    """Return the child of `node` that `step` names, with its line."""
    if isinstance(node, SequenceNode) and isinstance(step, int):
        if 0 <= step < len(node.value):
            child = node.value[step]
            return child, child.start_mark.line + 1
    elif isinstance(node, MappingNode) and isinstance(step, str):
        for key_node, value_node in node.value:
            if key_node.value == step:
                return value_node, key_node.start_mark.line + 1
    return None
