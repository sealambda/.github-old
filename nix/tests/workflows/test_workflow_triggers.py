"""Tests of the reader of the events of a workflow."""

import unittest

import yaml

from workflows.triggers import Trigger, read_triggers


def names(text: str) -> list[str]:
    """Return the event names that `read_triggers` finds in a workflow text."""
    return [trigger.name for trigger in read_triggers(yaml.safe_load(text))]


class ReadTriggersTest(unittest.TestCase):
    """`read_triggers` reads the three forms of `on`."""

    def test_plain_on_key_is_the_boolean_true_and_is_read(self) -> None:
        """PyYAML parses the key `on` as `True`; the reader must still find it."""
        document = yaml.safe_load("on: push\n")
        self.assertIn(True, document)
        self.assertEqual(read_triggers(document), [Trigger("push", ["on"])])

    def test_list_form_keeps_the_order_and_the_index_of_each_event(self) -> None:
        """Each event of a list is located by its index."""
        document = yaml.safe_load("on: [push, pull_request]\n")
        self.assertEqual(
            read_triggers(document),
            [Trigger("push", ["on", 0]), Trigger("pull_request", ["on", 1])],
        )

    def test_mapping_form_is_located_by_the_key(self) -> None:
        """Each event of a mapping is located by its key."""
        document = yaml.safe_load(
            "on:\n  push:\n  schedule:\n    - cron: '0 0 * * *'\n"
        )
        self.assertEqual(
            read_triggers(document),
            [Trigger("push", ["on", "push"]), Trigger("schedule", ["on", "schedule"])],
        )

    def test_quoted_key_is_read(self) -> None:
        """A quoted `"on"` parses to a string key."""
        self.assertEqual(names('"on": push\n'), ["push"])

    def test_values_of_other_shapes_give_no_event(self) -> None:
        """A number, a null and a list with a non-string item are skipped."""
        self.assertEqual(names("on: 5\n"), [])
        self.assertEqual(names("on:\n"), [])
        self.assertEqual(names("on: [push, 7, {a: b}]\n"), ["push"])

    def test_documents_without_a_mapping_or_without_on_give_no_event(self) -> None:
        """A list, a scalar, a null and a mapping without `on` have no events."""
        for document in (["on"], "on", None, {"name": "x"}):
            with self.subTest(document=document):
                self.assertEqual(read_triggers(document), [])
