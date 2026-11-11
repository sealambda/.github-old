"""Tests of the tag series: parsing, ordering and the next version."""

import unittest

from release.tags import (
    FIRST_VERSION,
    Version,
    highest_release,
    lowest_release,
    next_version,
    parse_tag,
)


class ParseTagTest(unittest.TestCase):
    """Only the strict form `v<number>.<number>.<number>` is a release tag."""

    def test_release_tag_gives_its_numbers(self) -> None:
        """A strict tag name parses to its three numbers."""
        self.assertEqual(parse_tag("v1.12.3"), Version(1, 12, 3))

    def test_other_names_are_not_release_tags(self) -> None:
        """Each name that differs from the strict form gives `None`."""
        malformed = [
            "1.2.3",
            "V1.2.3",
            "v1.2",
            "v1.2.3.4",
            "v1.2.3-rc1",
            "v1.2.3\n",
            "v1.x.3",
            "v1.2.-3",
            "v1..3",
            "v01.2.3",
            "v1.02.3",
            "v1.2.03",
            "v1.2.00",
            "v00.0.0",
            "latest",
            "",
        ]
        for name in malformed:
            with self.subTest(name=name):
                self.assertIsNone(parse_tag(name))

    def test_a_single_zero_is_a_number_but_a_leading_zero_is_not(self) -> None:
        """`0` is valid in each position, and `10` and `100` stay valid."""
        self.assertEqual(parse_tag("v0.0.0"), Version(0, 0, 0))
        self.assertEqual(parse_tag("v1.0.10"), Version(1, 0, 10))
        self.assertEqual(parse_tag("v10.100.0"), Version(10, 100, 0))

    def test_tag_property_round_trips(self) -> None:
        """The tag of a version parses back to the same version."""
        version = Version(1, 20, 300)
        self.assertEqual(version.tag, "v1.20.300")
        self.assertEqual(parse_tag(version.tag), version)


class HighestReleaseTest(unittest.TestCase):
    """The previous release is the highest version, by number."""

    def test_numbers_compare_as_numbers_not_as_text(self) -> None:
        """`v1.10.0` is higher than `v1.9.0`, and `v1.2.10` than `v1.2.9`."""
        self.assertEqual(highest_release(["v1.9.0", "v1.10.0"]), Version(1, 10, 0))
        self.assertEqual(highest_release(["v1.2.9", "v1.2.10"]), Version(1, 2, 10))

    def test_malformed_names_are_ignored(self) -> None:
        """A name that is not a release tag never wins, however high it reads."""
        names = ["v9.9", "latest", "v1.0.0", "v2.0.0-rc1"]
        self.assertEqual(highest_release(names), Version(1, 0, 0))

    def test_no_release_tag_gives_none(self) -> None:
        """An empty list and a list of other names have no highest release."""
        self.assertIsNone(highest_release([]))
        self.assertIsNone(highest_release(["latest", "v1.2"]))


class LowestReleaseTest(unittest.TestCase):
    """The covering release is the lowest version, by number."""

    def test_numbers_compare_as_numbers_not_as_text(self) -> None:
        """`v1.9.0` is lower than `v1.10.0`, although it sorts higher as text."""
        self.assertEqual(lowest_release(["v1.10.0", "v1.9.0"]), Version(1, 9, 0))

    def test_malformed_names_are_ignored(self) -> None:
        """A name that is not a release tag never wins, however low it reads."""
        names = ["v0.0", "v01.0.0", "latest", "v1.4.0", "v1.0.0-rc1"]
        self.assertEqual(lowest_release(names), Version(1, 4, 0))

    def test_no_release_tag_gives_none(self) -> None:
        """An empty list and a list of other names have no lowest release."""
        self.assertIsNone(lowest_release([]))
        self.assertIsNone(lowest_release(["latest", "v1.2"]))


class NextVersionTest(unittest.TestCase):
    """A change of the rules raises the minor number, any other the patch."""

    def test_first_release_is_1_0_0_whatever_the_answer(self) -> None:
        """Without a previous release the version is `v1.0.0`."""
        self.assertEqual(next_version(None, True), FIRST_VERSION)
        self.assertEqual(next_version(None, False), FIRST_VERSION)
        self.assertEqual(FIRST_VERSION.tag, "v1.0.0")

    def test_changed_rules_raise_minor_and_reset_patch(self) -> None:
        """`v1.2.5` with changed rules gives `v1.3.0`."""
        self.assertEqual(next_version(Version(1, 2, 5), True), Version(1, 3, 0))

    def test_unchanged_rules_raise_patch(self) -> None:
        """`v1.2.5` with unchanged rules gives `v1.2.6`."""
        self.assertEqual(next_version(Version(1, 2, 5), False), Version(1, 2, 6))
