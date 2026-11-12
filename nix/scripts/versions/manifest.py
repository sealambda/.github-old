"""Read `versions.json` and derive from it what the workflows must install."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import Node

from decisions.findings import Finding
from decisions.schemas import load_schema, validate_document
from decisions.yamlio import YamlDocument, parse_yaml

MANIFEST_NAME = "versions.json"
"""File name of the manifest, at the root of the checked tree."""

SCHEMA_NAME = "versions.schema.json"
"""File name of the schema of the manifest, in the schema directory."""

_INSTALL_URL = "https://releases.nixos.org/nix/nix-{version}/install"


@dataclass(frozen=True)
class Manifest:
    """The outcome of reading the manifest.

    Attributes:
        nix_version: The Nix version, `None` when the manifest has a finding.
        findings: What is wrong with the file, empty when it is valid.
    """

    nix_version: str | None
    findings: list[Finding]


def install_url(nix_version: str) -> str:
    """Return the installer address of a Nix release.

    This is the value of `install_url` that pins `cachix/install-nix-action`
    to the release. It is the address that the action uses by default, with
    the version written out.

    Args:
        nix_version: A version as `versions.json` holds it, such as `2.35.4`.
    """
    return _INSTALL_URL.format(version=nix_version)


class _UnreadableManifest(Exception):
    """The file can't be turned into JSON data: a problem of the file itself.

    Attributes:
        finding: The finding that reports the problem.
    """

    def __init__(self, line: int, message: str) -> None:
        """Keep the finding at `line` with `message`."""
        super().__init__(message)
        self.finding = Finding(MANIFEST_NAME, line, message)


class _DuplicateKeyError(ValueError):
    """A JSON object holds the same key twice.

    Attributes:
        key: The repeated key.
    """

    def __init__(self, key: str) -> None:
        """Keep the repeated `key`."""
        super().__init__(key)
        self.key = key


def read_manifest(root: Path) -> Manifest:
    """Read `versions.json` in `root` and validate it against its schema.

    Every problem is a finding at the line of the offending key. A file that
    isn't JSON has the line of the syntax error. A file that repeats a key in
    one object is a finding, because a JSON parser keeps only the last value
    and a reader could take the other one.

    Args:
        root: The checked tree.

    Raises:
        OSError: The file exists and can't be read, or the schema is missing.
    """
    try:
        text = _read_text(root)
        data = _parse_json(text)
    except _UnreadableManifest as error:
        return Manifest(None, [error.finding])
    document = YamlDocument(data=data, root=_line_marks(text))
    findings = validate_document(MANIFEST_NAME, document, load_schema(SCHEMA_NAME))
    if findings:
        return Manifest(None, findings)
    return Manifest(data["nix"], [])


def _read_text(root: Path) -> str:
    """Return the text of the manifest.

    Raises:
        _UnreadableManifest: The file is missing or isn't UTF-8 text.
        OSError: The file exists and can't be read.
    """
    try:
        return (root / MANIFEST_NAME).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise _UnreadableManifest(
            1, "the file is missing; it holds the Nix version"
        ) from None
    except UnicodeDecodeError:
        raise _UnreadableManifest(1, "the file isn't UTF-8 text") from None


def _parse_json(text: str) -> Any:
    """Parse the manifest text as JSON and refuse a repeated key.

    The result is `Any`: the schema validation that follows decides its shape.

    Raises:
        _UnreadableManifest: The text isn't JSON, or an object repeats a key.
    """
    try:
        return json.loads(text, object_pairs_hook=_object_without_duplicates)
    except json.JSONDecodeError as error:
        raise _UnreadableManifest(
            error.lineno, f"the file isn't valid JSON: {error.msg}"
        ) from None
    except _DuplicateKeyError as error:
        raise _UnreadableManifest(
            _line_of_repeat(text, error.key),
            f'the key "{error.key}" appears more than once in an object',
        ) from None


def _object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Build a JSON object from its pairs, or raise when a key repeats.

    Raises:
        _DuplicateKeyError: Two pairs have the same key.
    """
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(key)
        result[key] = value
    return result


def _line_of_repeat(text: str, key: str) -> int:
    """Return the number of the second line that holds the quoted `key`.

    The JSON parser doesn't say where a repeated key is, so the search is
    textual. It looks for the key between quotes, as `json.dumps` writes it,
    which means without JSON escapes. The search also matches a value that is
    equal to the key.

    Returns:
        The number of the second line that holds the quoted key. When only one
        line holds it, because both keys sit on one line, that line. When no
        line holds it as written, for example because the file spells it with
        a JSON escape, 1.
    """
    quoted = json.dumps(key, ensure_ascii=False)
    lines = [
        number
        for number, line in enumerate(text.splitlines(), start=1)
        if quoted in line
    ]
    if len(lines) >= 2:
        return lines[1]
    return lines[0] if lines else 1


def _line_marks(text: str) -> Node | None:
    """Return the YAML node tree of JSON text, which holds the line of each key.

    JSON is a subset of YAML, and the schema validation reports a violation at
    the line of its key from the node tree. A text that PyYAML can't read, for
    example a JSON file indented with tabs, has no node tree, and its
    violations sit at line 1.
    """
    try:
        return parse_yaml(text).root
    except yaml.YAMLError:
        return None
