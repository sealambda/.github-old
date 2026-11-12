"""Tests of the two series of tags of the hub and their rules.

The hub repository has the tags `v1.2.3` of the preset and `actions-v1.2.3` of
the actions series. Version 2 needs one rule for each series, and the rules
must not read each other's tags.
"""

import unittest

from presetcompat_fixtures import (
    actions_rule,
    hub_rule,
    messages_of,
    new_preset,
    old_preset,
    pin_rule,
)


class SeriesRulesTest(unittest.TestCase):
    """The rule of each series exists, is alone and reads only its series."""

    def test_the_order_of_the_rules_does_not_matter(self) -> None:
        """The rules are found by the tags that they match, not by position."""
        new = new_preset()
        new["packageRules"][-2:] = [actions_rule(), pin_rule()]
        self.assertEqual(messages_of(old_preset(), new), [])

    def test_a_rule_for_another_package_is_ignored(self) -> None:
        """Another package may have a rule that matches the same tags."""
        new = new_preset()
        other = pin_rule()
        other["matchPackageNames"] = ["example/other"]
        other["matchCurrentValue"] = "/./"
        new["packageRules"].append(other)
        self.assertEqual(messages_of(old_preset(), new), [])

    def test_a_missing_pin_versioning_is_a_finding(self) -> None:
        """The pin rule without `versioning` leaves the tag to the default."""
        new = new_preset()
        del new["packageRules"][-2]["versioning"]
        self.assertEqual(
            messages_of(old_preset(), new),
            ["the rule of the hub pin must set versioning to a regex: value, got None"],
        )

    def test_a_missing_actions_rule_is_a_finding(self) -> None:
        """No rule matches a tag of the actions series."""
        new = new_preset()
        del new["packageRules"][-1]
        messages = messages_of(old_preset(), new)
        self.assertEqual(len(messages), 1)
        self.assertIn("0 rules for sealambda/.github", messages[0])
        self.assertIn("actions-v1.2.3", messages[0])

    def test_overlapping_patterns_are_a_finding(self) -> None:
        """A pin pattern that also matches an actions tag makes two rules match."""
        new = new_preset()
        new["packageRules"][-2]["matchCurrentValue"] = "/v\\d/"
        messages = messages_of(old_preset(), new)
        self.assertEqual(len(messages), 1)
        self.assertIn("2 rules for sealambda/.github", messages[0])
        self.assertIn("actions-v1.2.3 of the actions series", messages[0])

    def test_a_pattern_that_is_not_a_regex_matches_nothing(self) -> None:
        """A glob in place of `/regex/` doesn't count as a rule for the series."""
        new = new_preset()
        new["packageRules"][-2]["matchCurrentValue"] = "v*"
        messages = messages_of(old_preset(), new)
        self.assertEqual(len(messages), 1)
        self.assertIn("0 rules for sealambda/.github", messages[0])

    def test_an_invalid_pattern_matches_nothing(self) -> None:
        """A `/regex/` that doesn't compile is a missing rule, not a crash."""
        new = new_preset()
        new["packageRules"][-2]["matchCurrentValue"] = "/(/"
        messages = messages_of(old_preset(), new)
        self.assertEqual(len(messages), 1)
        self.assertIn("0 rules for sealambda/.github", messages[0])


class VersioningTest(unittest.TestCase):
    """The versioning of each rule is a regex that reads only its series."""

    def test_a_versioning_that_is_not_regex_is_a_finding(self) -> None:
        """Another scheme can read the tag of the other series."""
        new = new_preset()
        new["packageRules"][-1]["versioning"] = "semver-coerced"
        self.assertEqual(
            messages_of(old_preset(), new),
            [
                "the rule of the actions series must set versioning to a "
                "regex: value, got 'semver-coerced'"
            ],
        )

    def test_a_versioning_that_reads_the_other_series_is_a_finding(self) -> None:
        """A regex with no `^v` anchor reads `actions-v1.2.3` as `1.2.3`."""
        new = new_preset()
        new["packageRules"][-2]["versioning"] = (
            "regex:(?<major>\\d+)\\.(?<minor>\\d+)\\.(?<patch>\\d+)$"
        )
        self.assertEqual(
            messages_of(old_preset(), new),
            [
                "the versioning of the hub pin reads actions-v1.2.3, "
                "a tag of the actions series"
            ],
        )

    def test_a_versioning_that_misses_its_own_tag_is_a_finding(self) -> None:
        """The pin regex must read `v1.2.3`."""
        new = new_preset()
        new["packageRules"][-2]["versioning"] = "regex:^release-(?<major>\\d+)$"
        self.assertEqual(
            messages_of(old_preset(), new),
            ["the versioning of the hub pin does not read v1.2.3"],
        )

    def test_a_versioning_that_is_not_a_regex_is_a_finding(self) -> None:
        """An invalid regex is a finding that names the error."""
        new = new_preset()
        new["packageRules"][-2]["versioning"] = "regex:^v(?<major>\\d+"
        messages = messages_of(old_preset(), new)
        self.assertEqual(len(messages), 1)
        self.assertIn("the versioning of the hub pin is not a regex", messages[0])

    def test_the_look_behind_syntax_is_not_rewritten(self) -> None:
        """Only `(?<name>` becomes `(?P<name>`: `(?<=` stays a look-behind."""
        new = new_preset()
        new["packageRules"][-2] = hub_rule(
            "/^v\\d/",
            "regex:^v(?<major>\\d+)\\.(?<minor>\\d+)\\.(?<patch>(?<=\\.)\\d+)$",
        )
        self.assertEqual(messages_of(old_preset(), new), [])


if __name__ == "__main__":
    unittest.main()
