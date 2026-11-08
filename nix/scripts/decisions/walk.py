"""Find the text files whose citations the checker reads."""

import fnmatch
import os
import shutil
import subprocess
from collections.abc import Iterator, Sequence
from pathlib import Path, PurePosixPath

MAX_FILE_BYTES = 1024 * 1024
"""A file larger than this is not read: it is generated or data, not prose."""

_SNIFF_BYTES = 8192
"""How many leading bytes are searched for a NUL byte to detect a binary file."""

_SKIPPED_DIRECTORY = ".git"
_LOCK_SUFFIX = ".lock"
_LOCK_NAMES = frozenset({"package-lock.json", "pnpm-lock.yaml", "npm-shrinkwrap.json"})
_CHANGELOG_PATTERN = "CHANGELOG*.md"

_IGNORE_FILE_PATTERN = ".*ignore"
"""The name of an ignore file: a dotfile whose name ends in `ignore`, such as
`.gitignore`, `.dockerignore`, `.prettierignore`, `.npmignore`, `.eslintignore`,
`.markdownlintignore`, `.helmignore`, `.vscodeignore` and `.ignore`.

Such a file lists patterns of paths, not citations. A pattern there often
names a file that does not exist on purpose, so reading it would give a false
finding for a page path. The rule needs the leading dot and
the exact lowercase ending, so `ignore.md`, `x.gitignore`, `.ignore.md` and
`.GITIGNORE` are read. `CODEOWNERS` and `.gitattributes` are read too: they
name real paths, and a stale one is a true finding."""


def parse_exclude(prefix: str) -> PurePosixPath:
    """Normalize one `exclude` path prefix.

    Args:
        prefix: A path relative to the checked root, such as `a/b` or `./a/b/`.

    Returns:
        The prefix as a path with no leading `./` and no trailing slash.

    Raises:
        ValueError: The prefix is empty, absolute, or leaves the root.
    """
    path = PurePosixPath(prefix)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"an exclude must be a path inside the root, not {prefix!r}")
    return path


def is_excluded(path: PurePosixPath, excludes: Sequence[PurePosixPath]) -> bool:
    """Tell whether `path` is one of the excluded paths or lies below one.

    A prefix matches whole path components: `a/b` excludes `a/b` and
    `a/b/c.py`, not `a/bc.py`.

    Args:
        path: A path relative to the checked root.
        excludes: The normalized prefixes.
    """
    return any(path.parts[: len(prefix.parts)] == prefix.parts for prefix in excludes)


def is_skipped_name(name: str) -> bool:
    """Tell whether a file name is a lock file, a changelog or an ignore file."""
    return (
        name.endswith(_LOCK_SUFFIX)
        or name in _LOCK_NAMES
        or fnmatch.fnmatchcase(name, _CHANGELOG_PATTERN)
        or fnmatch.fnmatchcase(name, _IGNORE_FILE_PATTERN)
    )


def list_files(root: Path) -> list[PurePosixPath]:
    """List the files of the tree at `root`, before any filter.

    The order is stable: the files of a folder come first, then its
    subfolders, each sorted by name.

    When `root` is a Git work tree and `git` is on the path, the listing is the
    files that Git names: the tracked files and the untracked files that
    `.gitignore` does not ignore. Folders such as `.venv`, `node_modules` and
    `.direnv` are then out, and so is a file that was deleted from the work
    tree. Otherwise, as in the sandbox of a Nix build where the source has no
    `.git`, the listing is all files below `root`, except those in `.git`.

    The listing keeps excluded paths, lock files, changelogs, ignore files and
    symbolic links: it tells what exists, and each check selects what it needs.
    `iter_candidate_files` selects the files to scan for citations,
    `collect_records` the record folder, and the check of a page path looks a
    path up.

    Args:
        root: The checked root.

    Returns:
        The path of each file, relative to `root`.

    Raises:
        OSError: `git` fails to list the files of the work tree.
    """
    listed = _list_git_files(root)
    if listed is None:
        return list(_walk_files(root))
    return [path for path in listed if os.path.lexists(root / path)]


def iter_candidate_files(
    root: Path, files: Sequence[PurePosixPath], excludes: Sequence[PurePosixPath]
) -> Iterator[PurePosixPath]:
    """Yield the files of a listing that may hold citations.

    The order of `files` stays. A file is left out when it is an excluded path,
    a lock file, a changelog, an ignore file or a symbolic link, or when it is
    not a regular file, as a folder that holds a submodule. No file is read:
    `read_text_file` decides whether a file is text.

    Args:
        root: The checked root.
        files: The listing that `list_files` returns for `root`.
        excludes: The normalized `exclude` prefixes.

    Yields:
        The path of each candidate, relative to `root`.
    """
    for relative in files:
        if is_skipped_name(relative.name) or is_excluded(relative, excludes):
            continue
        path = root / relative
        if path.is_file() and not path.is_symlink():
            yield relative


def _walk_files(root: Path) -> Iterator[PurePosixPath]:
    """Yield the files below `root`, without `.git`."""
    for folder, dirnames, filenames in os.walk(root):
        relative_folder = PurePosixPath(Path(folder).relative_to(root).as_posix())
        dirnames[:] = sorted(name for name in dirnames if name != _SKIPPED_DIRECTORY)
        for name in sorted(filenames):
            yield relative_folder / name


def _list_git_files(root: Path) -> list[PurePosixPath] | None:
    """List the files that Git knows in the work tree at `root`, or return `None`.

    The result is `None` when `root` has no `.git` entry or `git` is not on the
    path: the caller then walks the folders. The listing holds each tracked
    and each untracked, not ignored, file once, in the order of the walk. It can
    name a file that was deleted from the work tree or a folder that holds a
    submodule: the caller drops what is missing.

    Raises:
        OSError: `git ls-files` exits with an error. The message holds what
            Git printed, for example a refusal of an unsafe owner.
    """
    git = shutil.which("git")
    if git is None or not (root / ".git").exists():
        return None
    command = [git, "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
    result = subprocess.run(command, cwd=root, capture_output=True, check=False)
    if result.returncode != 0:
        detail = os.fsdecode(result.stderr).strip()
        raise OSError(f"git ls-files failed in {root}: {detail}")
    names = {
        PurePosixPath(name) for name in os.fsdecode(result.stdout).split("\0") if name
    }
    return sorted(names, key=_walk_order)


def _walk_order(path: PurePosixPath) -> tuple[tuple[int, str], ...]:
    """Return a sort key that puts a folder's files before its subfolders."""
    *folders, name = path.parts
    return (*((1, part) for part in folders), (0, name))


def read_text_file(path: Path) -> str | None:
    """Read a file as UTF-8 text, or return `None` when it is not text.

    A file is not text when it is larger than `MAX_FILE_BYTES`, holds a NUL
    byte in its first 8 KiB, or is not valid UTF-8.

    Args:
        path: The file to read.
    """
    if path.stat().st_size > MAX_FILE_BYTES:
        return None
    data = path.read_bytes()
    if b"\0" in data[:_SNIFF_BYTES]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None
