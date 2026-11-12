"""Tests of the invariants that version 2 keeps from version 1.

Each test breaks one invariant in a copy of the small pair of presets and
checks that the comparison reports it and nothing else.
"""

import unittest

from presetcompat_fixtures import messages_of, new_preset, old_preset


class BaselineTest(unittest.TestCase):
    """The pair that every other test starts from."""

    def test_the_baseline_pair_has_no_finding(self) -> None:
        """Version 2 may drop the approval and still keep every invariant."""
        self.assertEqual(messages_of(old_preset(), new_preset()), [])

    def test_version_2_may_extend_and_add_more(self) -> None:
        """An added `extends` item and an added rule that groups break nothing."""
        new = new_preset()
        new["extends"].append(":label(dependencies)")
        new["packageRules"].append({"matchManagers": ["npm"], "groupName": "npm"})
        self.assertEqual(messages_of(old_preset(), new), [])


class RulesKeptTest(unittest.TestCase):
    """Every package rule of version 1 is in version 2, unchanged."""

    def test_a_missing_rule_is_a_finding(self) -> None:
        """Removing rule 1 of version 1 from version 2 names the rule."""
        new = new_preset()
        del new["packageRules"][0]
        messages = messages_of(old_preset(), new)
        self.assertEqual(len(messages), 1)
        self.assertIn("lacks rule 1 of version 1", messages[0])

    def test_a_changed_rule_is_a_finding(self) -> None:
        """A rule with one value changed is not the rule of version 1."""
        new = new_preset()
        new["packageRules"][1]["groupName"] = "Other"
        messages = messages_of(old_preset(), new)
        self.assertEqual(len(messages), 1)
        self.assertIn("lacks rule 2 of version 1", messages[0])

    def test_the_message_shows_the_description_of_the_rule(self) -> None:
        """A rule with a description is named by it, cut at 60 characters."""
        old = old_preset()
        old["packageRules"][0]["description"] = "x" * 80
        # The new rule 1 differs from the old one, so it also counts as added.
        messages = [
            message
            for message in messages_of(old, new_preset())
            if "lacks rule" in message
        ]
        self.assertIn("x" * 57 + "...", messages[0])
        self.assertNotIn("x" * 58, messages[0])

    def test_no_rules_in_version_2_is_a_finding_for_each_rule(self) -> None:
        """A version 2 that has no `packageRules` lacks all the rules."""
        new = new_preset()
        del new["packageRules"]
        lacking = [m for m in messages_of(old_preset(), new) if "lacks rule" in m]
        self.assertEqual(len(lacking), 2)


class ReleaseAgeTest(unittest.TestCase):
    """The wait before a release is proposed stays 7 days."""

    def test_three_days_is_a_finding(self) -> None:
        """A shorter wait breaks the invariant."""
        new = new_preset()
        new["minimumReleaseAge"] = "3 days"
        self.assertEqual(
            messages_of(old_preset(), new),
            ["minimumReleaseAge must be \"7 days\", got '3 days'"],
        )

    def test_a_missing_age_is_a_finding(self) -> None:
        """No `minimumReleaseAge` means no wait."""
        new = new_preset()
        del new["minimumReleaseAge"]
        self.assertEqual(
            messages_of(old_preset(), new),
            ['minimumReleaseAge must be "7 days", got None'],
        )


class VulnerabilityAlertsTest(unittest.TestCase):
    """The alerts from the OSV database stay on."""

    def test_a_missing_key_is_a_finding(self) -> None:
        """Dropping `osvVulnerabilityAlerts` turns the alerts off."""
        new = new_preset()
        del new["osvVulnerabilityAlerts"]
        self.assertEqual(
            messages_of(old_preset(), new), ["osvVulnerabilityAlerts must be true"]
        )

    def test_false_and_a_string_are_findings(self) -> None:
        """Only the boolean `true` keeps the alerts on."""
        for value in (False, "true"):
            with self.subTest(value=value):
                new = new_preset()
                new["osvVulnerabilityAlerts"] = value
                self.assertEqual(
                    messages_of(old_preset(), new),
                    ["osvVulnerabilityAlerts must be true"],
                )


class ExtendsKeptTest(unittest.TestCase):
    """Every `extends` item of version 1 is in version 2, but the allowed one."""

    def test_missing_best_practices_is_a_finding(self) -> None:
        """Removing `config:best-practices` drops the digest pinning."""
        new = new_preset()
        new["extends"].remove("config:best-practices")
        self.assertEqual(
            messages_of(old_preset(), new),
            ["extends lacks 'config:best-practices', which version 1 extends"],
        )

    def test_another_removed_item_is_a_finding(self) -> None:
        """Only the items on the allowed list may go."""
        old = old_preset()
        old["extends"].append(":semanticCommits")
        self.assertEqual(
            messages_of(old, new_preset()),
            ["extends lacks ':semanticCommits', which version 1 extends"],
        )

    def test_the_approval_may_go(self) -> None:
        """Version 2 drops `:approveMajorUpdates` on purpose."""
        self.assertNotIn(":approveMajorUpdates", new_preset()["extends"])
        self.assertEqual(messages_of(old_preset(), new_preset()), [])


class LockFileScheduleTest(unittest.TestCase):
    """The lock file maintenance has a schedule."""

    def test_a_missing_block_is_a_finding(self) -> None:
        """No `lockFileMaintenance` means no schedule."""
        new = new_preset()
        del new["lockFileMaintenance"]
        self.assertEqual(
            messages_of(old_preset(), new),
            ["lockFileMaintenance.schedule must be a list of rules"],
        )

    def test_an_empty_schedule_is_a_finding(self) -> None:
        """An empty schedule runs the maintenance at any time."""
        new = new_preset()
        new["lockFileMaintenance"]["schedule"] = []
        self.assertEqual(
            messages_of(old_preset(), new),
            ["lockFileMaintenance.schedule must be a list of rules"],
        )


if __name__ == "__main__":
    unittest.main()
