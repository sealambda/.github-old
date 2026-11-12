"""Tests of the invariants about what version 2 may switch off.

Each test breaks one invariant of `presetcompat.guards` in a copy of the small
pair of presets and checks that the comparison reports it and nothing else.
"""

import unittest
from unittest import mock

from presetcompat import guards
from presetcompat_fixtures import (
    Preset,
    breaking_rule,
    hub_input_rule,
    messages_of,
    minor_zero_rule,
    new_preset,
    old_preset,
)


def rule_like(preset: Preset, template: Preset) -> Preset:
    """Return the rule of `preset` that equals `template`, so a test can change it."""
    rules: list[Preset] = preset["packageRules"]
    return rules[rules.index(template)]


class SwitchesTest(unittest.TestCase):
    """No setting turns Renovate, a preset or the lock file maintenance off."""

    def test_a_disabled_preset_is_a_finding(self) -> None:
        """`enabled: false` at the top level turns the whole preset off."""
        new = new_preset()
        new["enabled"] = False
        self.assertEqual(
            messages_of(old_preset(), new),
            ["enabled must not be false at the top level"],
        )

    def test_enabled_true_is_no_finding(self) -> None:
        """Only the value false is a problem."""
        new = new_preset()
        new["enabled"] = True
        self.assertEqual(messages_of(old_preset(), new), [])

    def test_ignore_presets_is_a_finding(self) -> None:
        """`ignorePresets` drops a preset that another preset extends."""
        new = new_preset()
        new["ignorePresets"] = ["config:best-practices"]
        self.assertEqual(
            messages_of(old_preset(), new), ["ignorePresets must not be set"]
        )

    def test_disabled_lock_file_maintenance_is_a_finding(self) -> None:
        """A schedule next to `enabled: false` still runs no maintenance."""
        new = new_preset()
        new["lockFileMaintenance"]["enabled"] = False
        self.assertEqual(
            messages_of(old_preset(), new),
            ["lockFileMaintenance.enabled must not be false"],
        )


class RebaseWhenTest(unittest.TestCase):
    """Renovate rebases a pull request only when it conflicts."""

    def test_another_value_is_a_finding(self) -> None:
        """`behind-base-branch` rebases every pull request after each merge."""
        new = new_preset()
        new["rebaseWhen"] = "behind-base-branch"
        self.assertEqual(
            messages_of(old_preset(), new),
            ["rebaseWhen must be \"conflicted\", got 'behind-base-branch'"],
        )

    def test_a_missing_value_is_a_finding(self) -> None:
        """The Renovate default isn't `conflicted`."""
        new = new_preset()
        del new["rebaseWhen"]
        self.assertEqual(
            messages_of(old_preset(), new),
            ['rebaseWhen must be "conflicted", got None'],
        )


class AddedRulesTest(unittest.TestCase):
    """A rule that version 2 adds keeps the release age and stays enabled."""

    def test_an_added_rule_with_a_short_age_is_a_finding(self) -> None:
        """A wait of 3 days is below 7 days."""
        new = new_preset()
        new["packageRules"].append(
            {"matchManagers": ["npm"], "minimumReleaseAge": "3 days"}
        )
        messages = messages_of(old_preset(), new)
        self.assertEqual(len(messages), 1)
        self.assertIn("sets minimumReleaseAge to '3 days', below 7 days", messages[0])

    def test_an_added_rule_without_an_age_is_a_finding(self) -> None:
        """`null` removes the wait, so it is below 7 days."""
        new = new_preset()
        new["packageRules"].append(
            {"matchManagers": ["npm"], "minimumReleaseAge": None}
        )
        messages = messages_of(old_preset(), new)
        self.assertEqual(len(messages), 1)
        self.assertIn("sets minimumReleaseAge to null", messages[0])

    def test_an_unreadable_age_is_a_finding(self) -> None:
        """An age that the tool can't read isn't proven to be 7 days."""
        for age in ("soon", "7", "7 fortnights", 7):
            with self.subTest(age=age):
                new = new_preset()
                new["packageRules"].append(
                    {"matchManagers": ["npm"], "minimumReleaseAge": age}
                )
                messages = messages_of(old_preset(), new)
                self.assertEqual(len(messages), 1)
                self.assertIn("which is no wait of 7 days", messages[0])

    def test_an_age_of_7_days_or_more_is_no_finding(self) -> None:
        """The units of Renovate that make at least 7 days pass."""
        for age in ("7 days", "1 week", "168 hours", "1 month", "1M", "2 weeks 1 day"):
            with self.subTest(age=age):
                new = new_preset()
                new["packageRules"].append(
                    {"matchManagers": ["npm"], "minimumReleaseAge": age}
                )
                self.assertEqual(messages_of(old_preset(), new), [])

    def test_a_minute_is_no_month(self) -> None:
        """A lower case `m` is a minute, so `1m` is far below 7 days."""
        new = new_preset()
        new["packageRules"].append(
            {"matchManagers": ["npm"], "minimumReleaseAge": "1m"}
        )
        self.assertEqual(len(messages_of(old_preset(), new)), 1)

    def test_an_added_disabled_rule_is_a_finding(self) -> None:
        """A rule that sets `enabled: false` switches a manager or package off."""
        new = new_preset()
        new["packageRules"].append({"matchManagers": ["npm"], "enabled": False})
        messages = messages_of(old_preset(), new)
        self.assertEqual(len(messages), 1)
        self.assertIn("an added rule sets enabled to false", messages[0])

    def test_a_rule_of_version_1_may_set_no_age(self) -> None:
        """The rule of version 1 that sets no age is no added rule."""
        self.assertIn(
            {"matchManagers": ["nix"], "minimumReleaseAge": None},
            new_preset()["packageRules"],
        )
        self.assertEqual(messages_of(old_preset(), new_preset()), [])

    def test_a_rule_on_the_allow_list_is_no_finding(self) -> None:
        """The allow-list names a rule by its description."""
        rule = {"description": "Allowed", "enabled": False}
        new = new_preset()
        new["packageRules"].append(rule)
        with mock.patch.object(guards, "ALLOWED_ADDED_RULES", {"Allowed": "a reason"}):
            self.assertEqual(messages_of(old_preset(), new), [])
        self.assertEqual(len(messages_of(old_preset(), new)), 1)


class BreakingLabelsTest(unittest.TestCase):
    """The two rules that add the label `breaking` stay in version 2."""

    def test_a_missing_is_breaking_rule_is_a_finding(self) -> None:
        """Without the rule, no versioning labels a breaking update."""
        new = new_preset()
        new["packageRules"].remove(breaking_rule())
        messages = messages_of(old_preset(), new)
        self.assertEqual(len(messages), 1)
        self.assertIn("where matchIsBreaking is true", messages[0])

    def test_a_missing_minor_zero_rule_is_a_finding(self) -> None:
        """Without the rule, a minor version of `0.x` stays unlabelled."""
        new = new_preset()
        new["packageRules"].remove(minor_zero_rule())
        messages = messages_of(old_preset(), new)
        self.assertEqual(len(messages), 1)
        self.assertIn("a minor update of a version 0.x", messages[0])

    def test_a_narrowed_minor_zero_rule_is_a_finding(self) -> None:
        """A second matcher makes the rule skip some packages."""
        new = new_preset()
        rule = rule_like(new, minor_zero_rule())
        rule["matchManagers"] = ["npm"]
        self.assertEqual(len(messages_of(old_preset(), new)), 1)

    def test_a_wrong_regex_is_a_finding(self) -> None:
        """Each regex that misses `0.1.0` or `v0.1.0`, or hits `10.0.0`, fails."""
        for pattern in ("/^0\\./", "/^v0\\./", "/0\\./", "/^v?1\\./", "0.x"):
            with self.subTest(pattern=pattern):
                new = new_preset()
                rule = rule_like(new, minor_zero_rule())
                rule["matchCurrentVersion"] = pattern
                self.assertEqual(len(messages_of(old_preset(), new)), 1)

    def test_another_update_type_is_a_finding(self) -> None:
        """A rule for `patch` only leaves the minor version unlabelled."""
        new = new_preset()
        rule = rule_like(new, minor_zero_rule())
        rule["matchUpdateTypes"] = ["patch"]
        self.assertEqual(len(messages_of(old_preset(), new)), 1)

    def test_another_label_is_a_finding(self) -> None:
        """The rule must add the label `breaking`."""
        new = new_preset()
        rule = rule_like(new, minor_zero_rule())
        rule["addLabels"] = ["minor"]
        self.assertEqual(len(messages_of(old_preset(), new)), 1)


class HubInputMergeTest(unittest.TestCase):
    """The hub input never merges a major update by itself."""

    def test_the_baseline_rule_is_no_finding(self) -> None:
        """The rule of the fixture lists `digest`, `patch` and `minor`."""
        self.assertIn(hub_input_rule(), new_preset()["packageRules"])
        self.assertEqual(messages_of(old_preset(), new_preset()), [])

    def test_major_in_the_list_is_a_finding(self) -> None:
        """A list with `major` merges a major update."""
        new = new_preset()
        rule = rule_like(new, hub_input_rule())
        rule["matchUpdateTypes"].append("major")
        messages = messages_of(old_preset(), new)
        self.assertEqual(len(messages), 1)
        self.assertIn("without major", messages[0])

    def test_no_list_is_a_finding(self) -> None:
        """A rule without `matchUpdateTypes` covers every update type."""
        new = new_preset()
        rule = rule_like(new, hub_input_rule())
        del rule["matchUpdateTypes"]
        self.assertEqual(len(messages_of(old_preset(), new)), 1)

    def test_another_input_may_merge_every_type(self) -> None:
        """The invariant is about the input named `hub` only."""
        new = new_preset()
        new["packageRules"].append(
            {"matchManagers": ["nix"], "matchDepNames": ["other"], "automerge": True}
        )
        self.assertEqual(messages_of(old_preset(), new), [])


if __name__ == "__main__":
    unittest.main()
