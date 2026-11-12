"""Tests of `read-version.sh`, the script of the step `version` of the setup action.

The `versions` check requires the step to run this file on the root
`versions.json`, and it doesn't read the file. These tests run the real script
(`READ_VERSION_SCRIPT`, set by the flake check) with `bash` and `jq` against
manifests that the tests write, so the logic of the step has a test of its own.
"""

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from decisions.schemas import load_schema

SCRIPT = Path(os.environ["READ_VERSION_SCRIPT"])
"""The script under test."""


class ReadVersionScriptTest(unittest.TestCase):
    """The script writes the output `nix` once, or fails and writes nothing."""

    def setUp(self) -> None:
        """Create a temporary folder for the manifest and the output file."""
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.manifest = self.root / "versions.json"
        self.output = self.root / "github-output"

    def run_script(
        self, manifest: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run the script on a manifest, with `GITHUB_OUTPUT` set to the output file.

        Args:
            manifest: The path to pass. The default is the manifest of the test.

        Returns:
            The finished process, with text output.
        """
        return subprocess.run(
            ["bash", str(SCRIPT), str(manifest or self.manifest)],
            env={**os.environ, "GITHUB_OUTPUT": str(self.output)},
            capture_output=True,
            text=True,
            check=False,
        )

    def written(self) -> str:
        """Return the text that the script wrote to the output file."""
        return self.output.read_text(encoding="utf-8") if self.output.exists() else ""

    def assert_failure(
        self, result: subprocess.CompletedProcess[str], text: str
    ) -> None:
        """Assert status 1, an error annotation that holds `text`, and no output."""
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("::error title=setup-nix::", result.stdout)
        self.assertIn(text, result.stdout)
        self.assertEqual(self.written(), "")

    def test_version_of_the_manifest_is_the_only_output(self) -> None:
        """The value of `nix` is written once, as `nix=<value>`."""
        self.manifest.write_text('{"nix": "2.99.1", "other": "1.0.0"}\n')
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.written(), "nix=2.99.1\n")

    def test_value_of_another_key_is_not_read(self) -> None:
        """A manifest with a key `nix2` and no key `nix` fails."""
        self.manifest.write_text('{"nix2": "2.99.1"}\n')
        self.assert_failure(self.run_script(), "no string value for the key nix")

    def test_missing_manifest_fails(self) -> None:
        """A path that doesn't name a file fails with the path in the message."""
        missing = self.root / "absent.json"
        result = self.run_script(missing)
        self.assert_failure(result, f"not found at {missing}")

    def test_invalid_json_fails(self) -> None:
        """A file that isn't JSON fails."""
        self.manifest.write_text("nix = 2.99.1\n")
        self.assert_failure(self.run_script(), "or is not valid JSON")

    def test_value_that_is_not_a_string_fails(self) -> None:
        """A number, `null` or a list in place of the string fails."""
        for value in ("2.99", "null", '["2.99.1"]', '{"v": "2.99.1"}'):
            with self.subTest(value=value):
                self.manifest.write_text(f'{{"nix": {value}}}\n')
                self.assert_failure(self.run_script(), "no string value")

    def test_value_of_another_form_fails(self) -> None:
        """Only MAJOR.MINOR.PATCH passes, and no part has a leading zero."""
        for value in (
            "2.99",
            "2.99.1.1",
            "v2.99.1",
            "02.99.1",
            "2.99.1-rc1",
            "",
            " 2.99.1",
        ):
            with self.subTest(value=value):
                self.manifest.write_text(f'{{"nix": "{value}"}}\n')
                self.assert_failure(self.run_script(), "MAJOR.MINOR.PATCH")

    def test_value_with_a_newline_fails(self) -> None:
        """A value with a newline isn't a version, so it can't add a second output."""
        self.manifest.write_text('{"nix": "2.99.1\\nnix=2.18.0"}\n')
        self.assert_failure(self.run_script(), "MAJOR.MINOR.PATCH")

    def test_script_and_schema_agree_on_the_form(self) -> None:
        """The script accepts the values that `versions.schema.json` accepts.

        The script copies the `pattern` of `nix` from the schema, so a change
        of one without the other shows here. The samples hold valid versions
        and each kind of invalid one. A final line break isn't a sample: see
        `test_final_line_break_is_the_one_difference_from_the_schema`.
        """
        pattern = load_schema("versions.schema.json")["properties"]["nix"]["pattern"]
        samples = (
            "2.99.1",
            "0.0.0",
            "10.20.30",
            "2.99",
            "2.99.1.1",
            "v2.99.1",
            "02.99.1",
            "2.99.01",
            "2.99.1-rc1",
            "2.99.1+build",
            "",
            " 2.99.1",
            "2.99.1 ",
            "2.99.1\nnix=2.18.0",
        )
        for value in samples:
            with self.subTest(value=value):
                self.output.unlink(missing_ok=True)
                self.manifest.write_text(json.dumps({"nix": value}))
                script_accepts = self.run_script().returncode == 0
                schema_accepts = re.fullmatch(pattern, value) is not None
                self.assertEqual(script_accepts, schema_accepts)

    def test_final_line_break_is_the_one_difference_from_the_schema(self) -> None:
        """The script drops a final line break and accepts the version.

        The schema rejects such a value, and the `versions` check reports it, so
        the difference never reaches a run of a merged change. The test keeps the
        header of `read-version.sh` true.
        """
        self.manifest.write_text(json.dumps({"nix": "2.99.1\n"}))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.written(), "nix=2.99.1\n")

    def test_missing_argument_fails(self) -> None:
        """The script needs the path of the manifest."""
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            env={**os.environ, "GITHUB_OUTPUT": str(self.output)},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.written(), "")


if __name__ == "__main__":
    unittest.main()
