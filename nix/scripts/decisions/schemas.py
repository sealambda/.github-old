"""Load the JSON Schemas and report how a YAML document breaks them."""

import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from decisions.findings import Finding
from decisions.yamlio import YamlDocument, line_of

SCHEMA_DIR_ENV = "DECISIONS_SCHEMA_DIR"
"""Environment variable that names the directory of the schema files."""

RECORD_SCHEMA = "decision-record.schema.json"
"""File name of the schema for the front matter of a record."""

LEDGER_SCHEMA = "superseded.schema.json"
"""File name of the schema for the ledger."""


def schema_dir() -> Path:
    """Return the directory that holds the schema files.

    The Nix wrapper sets `DECISIONS_SCHEMA_DIR` to a store path. Without it,
    the directory is `schemas/` at the root of the hub checkout that holds this
    package, which lets a maintainer run the tool from the source tree.
    """
    configured = os.environ.get(SCHEMA_DIR_ENV)
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "schemas"


def load_schema(name: str) -> dict[str, Any]:
    """Read the schema file `name` from the schema directory.

    Raises:
        OSError: The file is missing or unreadable.
        ValueError: The file is not valid JSON.
    """
    with (schema_dir() / name).open(encoding="utf-8") as handle:
        schema: dict[str, Any] = json.load(handle)
    return schema


def validate_document(
    path: str,
    document: YamlDocument,
    schema: Mapping[str, Any],
    line_offset: int = 0,
) -> list[Finding]:
    """Validate a parsed YAML document and return one finding per violation.

    The finding for a violation sits on the line of the offending key or item.
    A missing required key sits on the line of its parent.

    Args:
        path: The file that holds the document, for the findings.
        document: The parsed document.
        schema: The JSON Schema (Draft 2020-12).
        line_offset: The number of lines before the document in the file, for
            a document inside Markdown front matter.

    Returns:
        The findings, in document order.
    """
    validator = Draft202012Validator(
        schema, format_checker=Draft202012Validator.FORMAT_CHECKER
    )
    findings = []
    for error in validator.iter_errors(document.data):
        error_path = list(error.absolute_path)
        line = line_offset + line_of(document.root, error_path)
        findings.append(Finding(path, line, _describe(error_path, error.message)))
    return findings


def _describe(error_path: Sequence[str | int], message: str) -> str:
    """Prefix a schema message with the path of the value, if there is one."""
    if not error_path:
        return message
    return f"{_format_path(error_path)}: {message}"


def _format_path(error_path: Sequence[str | int]) -> str:
    """Write a path as `[2].successor`: indexes in brackets, keys after dots."""
    parts: list[str] = []
    for step in error_path:
        if isinstance(step, int):
            parts.append(f"[{step}]")
        else:
            parts.append(f".{step}" if parts else step)
    return "".join(parts)
