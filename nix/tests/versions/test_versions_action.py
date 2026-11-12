"""Tests of the expression form of `install_url` in the setup action.

The rule: a workflow writes the exact installer address. The hub's setup
action, `.github/actions/setup-nix/action.yml`, may build the address from the
output of an earlier step, and only when that step is the canonical step that
`versions.action_output` holds. The tests write small actions into a temporary
tree. Most of them are probes: each changes the step, or the place of the
action, in a way that installs another Nix version than `versions.json`, and
each must give one finding. The inline-script probes replace the call of
`read-version.sh` by a script of the action that writes another version than
the manifest holds. One test runs the real action of the hub
(`SETUP_NIX_ACTION`, set by the flake check) through the same check, so the
rule and the action can't drift apart.
"""

import os
import unittest
from pathlib import Path

from decisions.cli_common import EXIT_FINDINGS
from versions_fixtures import (
    INSTALL_URL,
    INSTALLER,
    MANIFEST,
    OTHER_URL,
    WORKFLOW_PATH,
    TreeTestCase,
    installer_step,
    line_of_text,
    workflow,
)

ACTION_PATH = ".github/actions/setup-nix/action.yml"
"""The one path where the expression form is allowed."""

URL_PREFIX = "https://releases.nixos.org/nix/nix-"
"""The part of the installer address before the version."""

EXPRESSION = f"{URL_PREFIX}${{{{ steps.version.outputs.nix }}}}/install"
"""The installer address that reads the output `nix` of the step `version`."""

CANONICAL_RUN = (
    'bash "$ACTION_DIR/read-version.sh" "$ACTION_DIR/../../../versions.json"'
)
"""The `run` line of the canonical step."""

CANONICAL_ENV = "${{ github.action_path }}"
"""The value of `ACTION_DIR` in the canonical step."""

INLINE_SCRIPT_ENV = "${{ github.action_path }}/../../../versions.json"
"""The manifest path that an inline script reads from the variable `MANIFEST`."""

DIFFERS = "isn't READ_VERSION_STEP of nix/scripts/versions/action_output.py: "
"""The start of the message for a step that isn't the canonical one."""


def producer_step(
    *,
    run: tuple[str, ...] = (CANONICAL_RUN,),
    step_id: str | None = "version",
    shell: str = "bash",
    env_name: str = "ACTION_DIR",
    env_value: str | None = CANONICAL_ENV,
    extra: tuple[str, ...] = (),
) -> str:
    """Return the step that reads the manifest, as text for `action_text`.

    The defaults give the canonical step.

    Args:
        run: The lines of the script. One line is a plain scalar, and more
            lines make a block scalar.
        step_id: The `id` of the step, or `None` for a step without one.
        shell: The value of the `shell` key.
        env_name: The name of the one `env` variable.
        env_value: The value of that variable, or `None` for a step without
            an `env` key.
        extra: More lines of the step, each already indented by 6 spaces.
    """
    lines = [f"    - shell: {shell}"]
    if step_id is not None:
        lines.append(f"      id: {step_id}")
    if env_value is not None:
        lines += ["      env:", f"        {env_name}: {env_value}"]
    lines += list(extra)
    if len(run) == 1:
        lines.append(f"      run: {run[0]}")
    else:
        lines.append("      run: |")
        lines += [f"        {line}" for line in run]
    return "\n".join(lines) + "\n"


def inline_script_step(*script: str) -> str:
    """Return a step that runs an inline script on the manifest in `MANIFEST`.

    The step has the id `version` and the shell `bash`, but its `env` and `run`
    keys differ from the canonical step.
    """
    return producer_step(run=script, env_name="MANIFEST", env_value=INLINE_SCRIPT_ENV)


def installer_in_action(url: str) -> str:
    """Return the installer step of an action, with the given `install_url`."""
    return f"    - uses: {INSTALLER}\n      with:\n        install_url: {url}\n"


def action_text(*steps: str) -> str:
    """Return a composite action that holds the given steps, as text."""
    header = "name: Setup\ndescription: Test\nruns:\n  using: composite\n  steps:\n"
    return header + "".join(steps)


class ExpressionInSetupActionTest(TreeTestCase):
    """The setup action may read the Nix version through the canonical step."""

    def setUp(self) -> None:
        """Write a valid manifest."""
        super().setUp()
        self.write("versions.json", MANIFEST)

    def check_action(self, text: str, path: str = ACTION_PATH) -> list[str]:
        """Write the action at `path`, run the check and return the lines."""
        self.write(path, text)
        return self.run_cli()[1]

    def assert_one_finding(
        self, text: str, message: str, path: str = ACTION_PATH
    ) -> None:
        """Assert that the action has one finding, on its line, with a message."""
        lines = self.check_action(text, path)
        line = line_of_text(text, "install_url")
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(f"{path}:{line}: "), lines)
        self.assertIn(message, lines[0])

    def assert_step_differs(self, step: str, keys: str) -> None:
        """Assert one finding that names the keys in which the step differs."""
        text = action_text(step, installer_in_action(EXPRESSION))
        self.assert_one_finding(text, f"{DIFFERS}it differs in {keys}")

    def test_real_action_of_the_hub_is_clean(self) -> None:
        """The action that the hub's jobs call passes the rule as written."""
        real = Path(os.environ["SETUP_NIX_ACTION"]).read_text(encoding="utf-8")
        self.assertEqual(self.check_action(real), [])

    def test_canonical_step_before_the_installer_is_clean(self) -> None:
        """The canonical step and the expression pass in the setup action."""
        text = action_text(producer_step(), installer_in_action(EXPRESSION))
        self.assertEqual(self.check_action(text), [])

    def test_literal_address_stays_clean_in_the_setup_action(self) -> None:
        """The exact address passes there, as in a workflow."""
        text = action_text(installer_in_action(INSTALL_URL))
        self.assertEqual(self.check_action(text), [])

    def test_literal_address_of_another_version_is_a_finding(self) -> None:
        """The expression form doesn't relax the literal."""
        text = action_text(installer_in_action(OTHER_URL))
        self.assert_one_finding(
            text, f"install_url is {OTHER_URL}; set it to {INSTALL_URL}"
        )

    def test_scripts_that_install_another_version_are_findings(self) -> None:
        """Each inline script writes a version other than the one in the manifest.

        The scripts read another key, change the value, write the output twice,
        ignore the manifest or hardcode a version. Each one must differ from
        the canonical step in `env` and `run`, so the rule names both keys.
        """
        probes = {
            "reads the key nix2": (
                'version="$(jq -er .nix2 "$MANIFEST")"',
                'echo "nix=$version" >> "$GITHUB_OUTPUT"',
            ),
            "post-processes the value with sed": (
                'version="$(jq -er .nix "$MANIFEST" | sed s/2.99.1/2.20.0/)"',
                'echo "nix=$version" >> "$GITHUB_OUTPUT"',
            ),
            "writes the output a second time": (
                'echo "nix=$(jq -er .nix "$MANIFEST")" >> "$GITHUB_OUTPUT"',
                'echo "nix=2.20.0" >> "$GITHUB_OUTPUT"',
            ),
            "hardcodes the version and only mentions the manifest": (
                ': "$MANIFEST"',
                'echo "nix=2.20.0" >> "$GITHUB_OUTPUT"',
            ),
            "runs jq on /dev/null": (
                'version="$(jq -er .nix /dev/null || echo 2.20.0)"',
                'echo "nix=$version" >> "$GITHUB_OUTPUT"',
            ),
            "hardcodes another version": (
                'echo "nix=2.18.0" >> "$GITHUB_OUTPUT"  # $MANIFEST',
            ),
        }
        for name, script in probes.items():
            with self.subTest(probe=name):
                self.assert_step_differs(inline_script_step(*script), "env, run")

    def test_canonical_run_with_a_changed_step_is_a_finding(self) -> None:
        """A key that the canonical step lacks, or a changed one, is named."""
        probes = {
            "a condition": (producer_step(extra=("      if: ${{ false }}",)), "if"),
            "a working directory": (
                producer_step(extra=("      working-directory: /tmp",)),
                "working-directory",
            ),
            "an ignored failure": (
                producer_step(extra=("      continue-on-error: true",)),
                "continue-on-error",
            ),
            "another shell": (producer_step(shell="sh"), "shell"),
            "a folder above the action": (
                producer_step(env_value="${{ github.action_path }}/.."),
                "env",
            ),
            "the workspace in place of the action": (
                producer_step(env_value="${{ github.workspace }}"),
                "env",
            ),
            "no env": (producer_step(env_value=None), "env"),
            "another script file": (
                producer_step(run=(CANONICAL_RUN.replace("read-version", "other"),)),
                "run",
            ),
            "another manifest": (
                producer_step(run=(CANONICAL_RUN.replace("../../../versions", "v"),)),
                "run",
            ),
            "a second command": (
                producer_step(run=(CANONICAL_RUN + " && true",)),
                "run",
            ),
        }
        for name, (step, keys) in probes.items():
            with self.subTest(probe=name):
                self.assert_step_differs(step, keys)

    def test_step_without_an_id_is_a_finding(self) -> None:
        """A step that has no id can't be the source of the output."""
        text = action_text(producer_step(step_id=None), installer_in_action(EXPRESSION))
        self.assert_one_finding(text, "0 earlier steps have the id version")

    def test_canonical_step_after_the_installer_is_a_finding(self) -> None:
        """The output must exist before the installer step runs."""
        text = action_text(installer_in_action(EXPRESSION), producer_step())
        self.assert_one_finding(text, "0 earlier steps have the id version")

    def test_two_steps_with_the_id_are_a_finding(self) -> None:
        """A second step with the id could be the one that GitHub reads."""
        text = action_text(
            producer_step(),
            producer_step(run=('echo "nix=2.20.0" >> "$GITHUB_OUTPUT"',)),
            installer_in_action(EXPRESSION),
        )
        self.assert_one_finding(text, "2 earlier steps have the id version")

    def test_expression_in_another_file_is_a_finding(self) -> None:
        """The canonical step doesn't make another file the setup action."""
        paths = (
            ".github/actions/other/action.yml",
            ".github/actions/setup-nix/action.yaml",
            ".github/actions/setup-nix/nested/action.yml",
            "templates/x/.github/actions/setup-nix/action.yml",
            "action.yml",
        )
        text = action_text(producer_step(), installer_in_action(EXPRESSION))
        for path in paths:
            with self.subTest(path=path):
                self.assert_one_finding(
                    text,
                    f"install_url is {EXPRESSION}; set it to {INSTALL_URL}; "
                    f"only {ACTION_PATH} may use that expression",
                    path,
                )
                (self.root / path).unlink()

    def test_other_shapes_of_the_expression_are_a_finding(self) -> None:
        """Only the exact text of the expression passes."""
        urls = (
            f"{URL_PREFIX}${{{{ inputs.version }}}}/install",
            f"{URL_PREFIX}${{{{ steps.other.outputs.nix }}}}/install",
            f"{URL_PREFIX}${{{{ steps.version.outputs.other }}}}/install",
            f"{URL_PREFIX}${{{{steps.version.outputs.nix}}}}/install",
            f"{EXPRESSION}?x=1",
            "https://example.org/nix-${{ steps.version.outputs.nix }}/install",
            "${{ steps.version.outputs.nix }}",
        )
        for url in urls:
            with self.subTest(url=url):
                text = action_text(producer_step(), installer_in_action(url))
                self.assert_one_finding(
                    text, f"install_url is {url}; set it to {INSTALL_URL}"
                )


class ExpressionInWorkflowTest(TreeTestCase):
    """A workflow never gets the expression form, even with the canonical step."""

    def test_expression_in_a_workflow_is_a_finding(self) -> None:
        """The producer is right, and the file is a workflow, so the step fails."""
        self.write("versions.json", MANIFEST)
        producer = (
            "      - id: version\n"
            "        shell: bash\n"
            "        env:\n"
            f"          ACTION_DIR: {CANONICAL_ENV}\n"
            f"        run: {CANONICAL_RUN}\n"
        )
        text = workflow(producer, installer_step(install_url=EXPRESSION))
        self.write(WORKFLOW_PATH, text)
        status, lines, _ = self.run_cli()
        self.assertEqual(status, EXIT_FINDINGS)
        line = line_of_text(text, "install_url")
        self.assertEqual(
            lines,
            [
                f"{WORKFLOW_PATH}:{line}: install_url is {EXPRESSION}; "
                f"set it to {INSTALL_URL}; only {ACTION_PATH} may use that "
                "expression"
            ],
        )


if __name__ == "__main__":
    unittest.main()
