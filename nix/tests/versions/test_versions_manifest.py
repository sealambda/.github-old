"""Tests of the manifest: reading `versions.json` and the installer address."""

import unittest

from versions.manifest import MANIFEST_NAME, install_url, read_manifest
from versions_fixtures import INSTALL_URL, MANIFEST, NIX_VERSION, TreeTestCase


class ManifestTest(TreeTestCase):
    """What `read_manifest` accepts and how it reports the rest."""

    def messages(self) -> list[tuple[int, str]]:
        """Return the line and message of each finding of the manifest."""
        return [(f.line, f.message) for f in read_manifest(self.root).findings]

    def test_valid_manifest_gives_the_version(self) -> None:
        """A manifest with `$schema` and `nix` is valid."""
        self.write(MANIFEST_NAME, MANIFEST)
        manifest = read_manifest(self.root)
        self.assertEqual((manifest.nix_version, manifest.findings), (NIX_VERSION, []))

    def test_manifest_without_schema_key_is_valid(self) -> None:
        """Only `nix` is required."""
        self.write(MANIFEST_NAME, '{"nix": "0.0.1"}')
        self.assertEqual(read_manifest(self.root).nix_version, "0.0.1")

    def test_missing_file_is_a_finding(self) -> None:
        """A tree without the file has no version."""
        manifest = read_manifest(self.root)
        self.assertIsNone(manifest.nix_version)
        self.assertEqual(
            [(f.path, f.line) for f in manifest.findings], [(MANIFEST_NAME, 1)]
        )
        self.assertIn("missing", manifest.findings[0].message)

    def test_file_that_is_not_utf8_is_a_finding(self) -> None:
        """Bytes that aren't UTF-8 are reported, not raised."""
        self.write(MANIFEST_NAME, f'{{"nix": "{NIX_VERSION}"}}'.encode() + b"\xff")
        self.assertEqual(self.messages(), [(1, "the file isn't UTF-8 text")])

    def test_file_that_is_not_json_names_the_line(self) -> None:
        """A syntax error sits on the line that the JSON parser reports."""
        self.write(MANIFEST_NAME, '{\n  "nix": 2.35.4\n}\n')
        [(line, message)] = self.messages()
        self.assertEqual(line, 2)
        self.assertTrue(message.startswith("the file isn't valid JSON: "), message)

    def test_json_that_yaml_does_not_accept_still_validates(self) -> None:
        """A JSON file indented with a tab is valid JSON, whatever PyYAML says."""
        self.write(MANIFEST_NAME, f'{{\n\t"nix": "{NIX_VERSION}"\n}}\n')
        self.assertEqual(read_manifest(self.root).nix_version, NIX_VERSION)

    def test_schema_violations_are_findings_on_the_key(self) -> None:
        """Each violation of the schema is a finding, on the line of its key."""
        header = '{\n  "$schema": "./schemas/versions.schema.json",\n'
        cases = {
            "a missing nix key": (header + '  "other": "1"\n}\n', 1, "required"),
            "a version without a patch": (header + '  "nix": "2.35"\n}\n', 3, "match"),
            "a leading v": (header + '  "nix": "v2.35.4"\n}\n', 3, "match"),
            "a leading zero": (header + '  "nix": "2.035.4"\n}\n', 3, "match"),
            "a number": (header + '  "nix": 2\n}\n', 3, "type"),
            "an array": ("[]\n", 1, "type"),
        }
        for name, (text, line, word) in cases.items():
            with self.subTest(name):
                self.write(MANIFEST_NAME, text)
                self.assertIsNone(read_manifest(self.root).nix_version)
                lines = [number for number, _ in self.messages()]
                self.assertIn(line, lines)
                self.assertIn(word, " ".join(text for _, text in self.messages()))

    def test_unknown_key_is_a_finding(self) -> None:
        """Another tool in the file is a violation: nixpkgs pins the others."""
        self.write(MANIFEST_NAME, f'{{"nix": "{NIX_VERSION}", "node": "26.0.0"}}\n')
        self.assertIsNone(read_manifest(self.root).nix_version)
        self.assertIn("Additional properties", self.messages()[0][1])

    def test_version_with_a_line_break_is_a_finding(self) -> None:
        """A final newline passes a pattern that ends in `$` in some validators.

        The schema also excludes every line break, so that all JSON Schema
        implementations agree. The check runs through the real validator.
        """
        for name, escaped in {
            "a final newline": "\\n",
            "a final carriage return": "\\r",
            "a final CRLF": "\\r\\n",
        }.items():
            with self.subTest(name):
                self.write(MANIFEST_NAME, f'{{"nix": "{NIX_VERSION}{escaped}"}}\n')
                self.assertIsNone(read_manifest(self.root).nix_version)
                lines = [text for _, text in self.messages()]
                self.assertTrue(lines, "a finding is expected")
                self.assertTrue(all(text.startswith("nix: ") for text in lines), lines)

    def test_version_with_a_line_break_inside_is_a_finding(self) -> None:
        """A line break before or inside the version fails too."""
        for escaped in ("\\n2.99.1", "2.99\\n.1"):
            with self.subTest(escaped=escaped):
                self.write(MANIFEST_NAME, f'{{"nix": "{escaped}"}}\n')
                self.assertIsNone(read_manifest(self.root).nix_version)

    def test_repeated_key_is_a_finding_on_the_second_line(self) -> None:
        """A parser keeps the last value, so a repeated key hides the first."""
        text = f'{{\n  "nix": "2.30.0",\n  "nix": "{NIX_VERSION}"\n}}\n'
        self.write(MANIFEST_NAME, text)
        manifest = read_manifest(self.root)
        self.assertIsNone(manifest.nix_version)
        self.assertEqual(
            [(f.line, f.message) for f in manifest.findings],
            [(3, 'the key "nix" appears more than once in an object')],
        )

    def test_repeated_key_on_one_line_is_a_finding_on_line_one(self) -> None:
        """The line of a repeat on the same line as the first key is that line."""
        self.write(MANIFEST_NAME, '{"nix": "2.30.0", "nix": "2.30.1"}\n')
        self.assertEqual(
            [(f.line, f.message) for f in read_manifest(self.root).findings],
            [(1, 'the key "nix" appears more than once in an object')],
        )

    def test_repeated_key_in_a_nested_object_is_a_finding(self) -> None:
        """The reader refuses a repeat at any depth, before the schema runs."""
        self.write(
            MANIFEST_NAME, f'{{"nix": "{NIX_VERSION}", "x": {{"a": 1, "a": 2}}}}'
        )
        manifest = read_manifest(self.root)
        self.assertIsNone(manifest.nix_version)
        self.assertIn(
            'the key "a" appears more than once', manifest.findings[0].message
        )

    def test_same_value_under_different_keys_is_not_a_repeat(self) -> None:
        """Only a repeated key is refused: the schema alone judges the rest."""
        self.write(
            MANIFEST_NAME, f'{{"$schema": "{NIX_VERSION}", "nix": "{NIX_VERSION}"}}'
        )
        manifest = read_manifest(self.root)
        self.assertEqual((manifest.nix_version, manifest.findings), (NIX_VERSION, []))


class InstallUrlTest(unittest.TestCase):
    """The address that pins the installer action."""

    def test_install_url_names_the_release(self) -> None:
        """The address is the release's installer, as the action builds it."""
        self.assertEqual(install_url(NIX_VERSION), INSTALL_URL)
