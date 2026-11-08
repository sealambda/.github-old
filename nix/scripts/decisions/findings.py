"""The result type of every check: one problem at one place."""

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Finding:
    """One problem that a check found.

    Findings sort by path, then line, then message, so the output of a run is
    stable. A finding about a whole file has line 1.

    Attributes:
        path: The file, relative to the checked root, with `/` separators.
        line: The 1-based line of the problem.
        message: What is wrong, in one sentence.
    """

    path: str
    line: int
    message: str

    def format(self) -> str:
        """Return the finding as `path:line: message`."""
        return f"{self.path}:{self.line}: {self.message}"
