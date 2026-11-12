"""Apply the rules to the files of a tree and report each leak as a finding."""

import codecs
from bisect import bisect_right
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from decisions.findings import Finding
from decisions.walk import SNIFF_BYTES, is_excluded, list_files
from leaks.rules import Policy, Rule, build_rules

_REPLACEMENT = "\N{REPLACEMENT CHARACTER}"
"""What a stray NUL byte of a text file becomes."""


def read_text(path: Path) -> str | None:
    """Read a file as text, or return `None` when it is binary.

    A file that starts with a UTF-16 byte order mark is text: a UTF-16 file
    has a NUL byte after each ASCII character, and a reader sees its text. Any
    other file with a NUL byte in its first `SNIFF_BYTES` bytes is binary, as
    an image is, the same rule as in `decisions.walk`. A NUL byte after that
    point is a stray byte in a text file, so the file is read and the byte
    becomes a replacement character: the rules use the NUL character as a
    placeholder. Every file is read whatever its size, and a byte that is not
    UTF-8 becomes a replacement character: a private fact is plain ASCII, so it
    stays readable next to such a byte.

    Args:
        path: The file to read.
    """
    data = path.read_bytes()
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        text = data.decode("utf-16", errors="replace")
    elif b"\0" in data[:SNIFF_BYTES]:
        return None
    else:
        text = data.decode("utf-8", errors="replace")
    return text.replace("\0", _REPLACEMENT)


def scan_text(text: str, path: str, rules: Sequence[Rule]) -> list[Finding]:
    """Return one finding for each leak that a rule finds in a text.

    Args:
        text: The text of one file.
        path: The path that the findings name.
        rules: The rules to apply.
    """
    line_starts = [0]
    line_starts.extend(index + 1 for index, char in enumerate(text) if char == "\n")
    findings = []
    for rule in rules:
        for leak in rule.find(text):
            line = bisect_right(line_starts, leak.offset)
            shown = leak.text.split("\n", 1)[0]
            findings.append(
                Finding(path, line, f"{rule.name}: `{shown}`. {rule.advice}")
            )
    return findings


def scan_tree(
    root: Path, policy: Policy, excludes: Sequence[PurePosixPath]
) -> list[Finding]:
    """Scan every text file of a tree and return the sorted findings.

    The scan reads every regular file that `decisions.walk.list_files` lists,
    lock files and ignore files included, and it does not follow a symbolic
    link. It skips an excluded path and a binary file.

    Args:
        root: The directory to scan.
        policy: The organization and the names that are public.
        excludes: The normalized path prefixes that the scan skips.

    Raises:
        OSError: A file cannot be listed or read.
    """
    rules = build_rules(policy)
    findings: list[Finding] = []
    for relative in list_files(root):
        path = root / relative
        if is_excluded(relative, excludes) or path.is_symlink() or not path.is_file():
            continue
        text = read_text(path)
        if text is not None:
            findings.extend(scan_text(text, relative.as_posix(), rules))
    return sorted(findings)
