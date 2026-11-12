"""Tests that the pages which list the rules agree with the code.

`vocabulary.py` is the one source of the list of types and of the header limit.
`CONTRIBUTING.md` and `docs/reference/git-policy.md` state both for the reader.
A page that is wrong tells a contributor a rule that the tool does not enforce,
and no other check would notice. The flake check gives the paths of the two
pages in the environment variables `CONTRIBUTING_MD` and `GIT_POLICY_MD`.
"""

import os
import re
import unittest
from pathlib import Path

from gitpolicy.vocabulary import CHANGE_TYPES, HEADER_LIMIT

# The sentence of CONTRIBUTING.md that lists the types. It spans two lines.
_CONTRIBUTING_TYPES = re.compile(r"The type is (.*?), in lower case", re.DOTALL)

# The limit as CONTRIBUTING.md and the reference page write it.
_LIMIT = re.compile(r"at most (\d+) characters", re.IGNORECASE)

# One row of the table of types: the type in code quotes, then its use.
_TYPE_ROW = re.compile(r"^\| `([a-z]+)` \|", re.MULTILINE)


def read_page(variable: str) -> str:
    """Return the text of the page whose path the environment variable gives."""
    return Path(os.environ[variable]).read_text(encoding="utf-8")


def types_of_the_table(page: str) -> list[str]:
    """Return the types of the table that opens with `| Type | Use for |`.

    The table ends at the first line that is not a row. The table of commit
    rules that comes later has rows with other first cells and is not read.
    """
    _, _, after = page.partition("| Type | Use for |")
    table = after.split("\n\n", 1)[0]
    return _TYPE_ROW.findall(table)


class DocumentedRulesTest(unittest.TestCase):
    """The pages state the same types and the same limit as the code."""

    def test_contributing_lists_the_types_of_the_code(self) -> None:
        """The sentence of CONTRIBUTING.md names each type, in the order of the code."""
        match = _CONTRIBUTING_TYPES.search(read_page("CONTRIBUTING_MD"))
        self.assertIsNotNone(match, "the sentence 'The type is ...' is missing")
        assert match is not None  # for the type checker
        self.assertEqual(list(CHANGE_TYPES), re.findall(r"`([a-z]+)`", match[1]))

    def test_reference_table_lists_the_types_of_the_code(self) -> None:
        """The table of the reference page has one row for each type, in order."""
        listed = types_of_the_table(read_page("GIT_POLICY_MD"))
        self.assertEqual(list(CHANGE_TYPES), listed)

    def test_both_pages_state_the_header_limit_of_the_code(self) -> None:
        """Each page gives the limit of `HEADER_LIMIT` for the header."""
        for variable in ("CONTRIBUTING_MD", "GIT_POLICY_MD"):
            with self.subTest(variable):
                limits = [int(n) for n in _LIMIT.findall(read_page(variable))]
                self.assertIn(HEADER_LIMIT, limits)
                self.assertEqual({HEADER_LIMIT}, set(limits))

    def test_the_table_reader_returns_the_types_in_the_order_of_the_rows(self) -> None:
        """The reader returns what the rows hold, so a missing row shows up."""
        page = "| Type | Use for |\n| ---- | ---- |\n| `feat` | A. |\n| `fix` | B. |\n"
        self.assertEqual(["feat", "fix"], types_of_the_table(page))


if __name__ == "__main__":
    unittest.main()
