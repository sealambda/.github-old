"""Tests of the tag series: parsing, ordering and the next version."""

import unittest

from release.tags import (
    ACTIONS_PREFIX,
    FIRST_VERSION,
    HUB_PREFIX,
    Bump,
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
        self.assertEqual(parse_tag("v1.12.3", HUB_PREFIX), Version(1, 12, 3))

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
                self.assertIsNone(parse_tag(name, HUB_PREFIX))

    def test_a_single_zero_is_a_number_but_a_leading_zero_is_not(self) -> None:
        """`0` is valid in each position, and `10` and `100` stay valid."""
        self.assertEqual(parse_tag("v0.0.0", HUB_PREFIX), Version(0, 0, 0))
        self.assertEqual(parse_tag("v1.0.10", HUB_PREFIX), Version(1, 0, 10))
        self.assertEqual(parse_tag("v10.100.0", HUB_PREFIX), Version(10, 100, 0))

    def test_hub_tag_round_trips(self) -> None:
        """The tag of a version parses back to the same version."""
        version = Version(1, 20, 300)
        tag = version.tag_with(HUB_PREFIX)
        self.assertEqual(tag, "v1.20.300")
        self.assertEqual(parse_tag(tag, HUB_PREFIX), version)


class HighestReleaseTest(unittest.TestCase):
    """The previous release is the highest version, by number."""

    def test_numbers_compare_as_numbers_not_as_text(self) -> None:
        """`v1.10.0` is higher than `v1.9.0`, and `v1.2.10` than `v1.2.9`."""
        self.assertEqual(
            highest_release(["v1.9.0", "v1.10.0"], HUB_PREFIX), Version(1, 10, 0)
        )
        self.assertEqual(
            highest_release(["v1.2.9", "v1.2.10"], HUB_PREFIX), Version(1, 2, 10)
        )

    def test_malformed_names_are_ignored(self) -> None:
        """A name that is not a release tag never wins, however high it reads."""
        names = ["v9.9", "latest", "v1.0.0", "v2.0.0-rc1"]
        self.assertEqual(highest_release(names, HUB_PREFIX), Version(1, 0, 0))

    def test_no_release_tag_gives_none(self) -> None:
        """An empty list and a list of other names have no highest release."""
        self.assertIsNone(highest_release([], HUB_PREFIX))
        self.assertIsNone(highest_release(["latest", "v1.2"], HUB_PREFIX))


class LowestReleaseTest(unittest.TestCase):
    """The covering release is the lowest version, by number."""

    def test_numbers_compare_as_numbers_not_as_text(self) -> None:
        """`v1.9.0` is lower than `v1.10.0`, although it sorts higher as text."""
        self.assertEqual(
            lowest_release(["v1.10.0", "v1.9.0"], HUB_PREFIX), Version(1, 9, 0)
        )

    def test_malformed_names_are_ignored(self) -> None:
        """A name that is not a release tag never wins, however low it reads."""
        names = ["v0.0", "v01.0.0", "latest", "v1.4.0", "v1.0.0-rc1"]
        self.assertEqual(lowest_release(names, HUB_PREFIX), Version(1, 4, 0))

    def test_no_release_tag_gives_none(self) -> None:
        """An empty list and a list of other names have no lowest release."""
        self.assertIsNone(lowest_release([], HUB_PREFIX))
        self.assertIsNone(lowest_release(["latest", "v1.2"], HUB_PREFIX))


class NextVersionTest(unittest.TestCase):
    """A minor bump raises the minor number, a patch bump the patch number."""

    def test_first_release_is_1_0_0_whatever_the_bump(self) -> None:
        """Without a previous release the version is `v1.0.0`."""
        self.assertEqual(next_version(None, Bump.MINOR), FIRST_VERSION)
        self.assertEqual(next_version(None, Bump.PATCH), FIRST_VERSION)
        self.assertEqual(FIRST_VERSION.tag_with(HUB_PREFIX), "v1.0.0")

    def test_minor_bump_raises_minor_and_resets_patch(self) -> None:
        """`v1.2.5` with a minor bump gives `v1.3.0`."""
        self.assertEqual(next_version(Version(1, 2, 5), Bump.MINOR), Version(1, 3, 0))

    def test_patch_bump_raises_patch(self) -> None:
        """`v1.2.5` with a patch bump gives `v1.2.6`."""
        self.assertEqual(next_version(Version(1, 2, 5), Bump.PATCH), Version(1, 2, 6))

    def test_no_release_has_no_version(self) -> None:
        """`Bump.NONE` is an error, with or without a previous release."""
        with self.assertRaises(ValueError):
            next_version(Version(1, 2, 5), Bump.NONE)
        with self.assertRaises(ValueError):
            next_version(None, Bump.NONE)


class ActionsSeriesTest(unittest.TestCase):
    """The actions series has the form `actions-v<number>.<number>.<number>`."""

    def test_actions_tag_gives_its_numbers_with_the_actions_prefix(self) -> None:
        """A strict actions tag parses to its three numbers."""
        self.assertEqual(
            parse_tag("actions-v1.12.3", ACTIONS_PREFIX), Version(1, 12, 3)
        )

    def test_other_names_are_not_actions_tags(self) -> None:
        """Each name that differs from the strict form gives `None`."""
        for name in (
            "actions-v1.2",
            "actions-v01.2.3",
            "actions-v1.2.3-rc1",
            "actions-v1.2.3\n",
            "actions-1.2.3",
            "Actions-v1.2.3",
            "actions-v1.2.3.4",
            "xactions-v1.2.3",
            "v1.2.3",
            "",
        ):
            with self.subTest(name=name):
                self.assertIsNone(parse_tag(name, ACTIONS_PREFIX))

    def test_a_hub_tag_is_never_an_actions_tag_and_the_reverse(self) -> None:
        """`v1.2.3` and `actions-v1.2.3` belong to one series each."""
        self.assertEqual(parse_tag("v1.2.3", HUB_PREFIX), Version(1, 2, 3))
        self.assertIsNone(parse_tag("actions-v1.2.3", HUB_PREFIX))
        self.assertIsNone(parse_tag("v1.2.3", ACTIONS_PREFIX))

    def test_a_name_that_only_ends_like_a_hub_tag_is_not_one(self) -> None:
        """The prefix `v` must start the name: `myv1.2.3` and `x-v1.2.3` are none."""
        for name in ("myv1.2.3", "x-v1.2.3", "actions-v1.2.3-v1.2.3"):
            with self.subTest(name=name):
                self.assertIsNone(parse_tag(name, HUB_PREFIX))

    def test_mixed_tags_each_series_reads_only_its_own(self) -> None:
        """The highest and the lowest release of a series ignore the other."""
        names = ["v1.0.0", "actions-v1.0.0", "v1.7.0", "actions-v2.1.0", "latest"]
        self.assertEqual(highest_release(names, HUB_PREFIX), Version(1, 7, 0))
        self.assertEqual(lowest_release(names, HUB_PREFIX), Version(1, 0, 0))
        self.assertEqual(highest_release(names, ACTIONS_PREFIX), Version(2, 1, 0))
        self.assertEqual(lowest_release(names, ACTIONS_PREFIX), Version(1, 0, 0))

    def test_a_list_without_a_tag_of_the_series_has_no_release(self) -> None:
        """Only the other series is present: the answer is `None`."""
        self.assertIsNone(highest_release(["actions-v1.0.0"], HUB_PREFIX))
        self.assertIsNone(lowest_release(["v1.0.0"], ACTIONS_PREFIX))

    def test_tag_with_prefix_round_trips(self) -> None:
        """The tag of a version parses back to the same version in each series."""
        version = Version(1, 20, 300)
        self.assertEqual(version.tag_with(ACTIONS_PREFIX), "actions-v1.20.300")
        self.assertEqual(
            parse_tag(version.tag_with(ACTIONS_PREFIX), ACTIONS_PREFIX), version
        )
