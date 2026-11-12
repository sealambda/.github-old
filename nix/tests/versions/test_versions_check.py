"""Tests of the check of a tree and of the command line of the version check."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from decisions.cli_common import EXIT_CLEAN, EXIT_FINDINGS, EXIT_INTERNAL, EXIT_USAGE
from versions.cli import main
from versions_fixtures import (
    INSTALL_URL,
    MANIFEST,
    OTHER_URL,
    WORKFLOW_PATH,
    TreeTestCase,
    installer_step,
    job,
    jobs_workflow,
    line_of_text,
    run_step,
    workflow,
)


class InstallUrlTest(TreeTestCase):
    """The rule for each `cachix/install-nix-action` step."""

    def setUp(self) -> None:
        """Write a valid manifest."""
        super().setUp()
        self.write("versions.json", MANIFEST)

    def test_step_with_the_right_address_is_clean(self) -> None:
        """A step that sets the address of the manifest's version has no finding."""
        self.write(WORKFLOW_PATH, workflow(installer_step(install_url=INSTALL_URL)))
        self.assertEqual(self.run_cli(), (EXIT_CLEAN, [], ""))

    def test_tree_without_installer_is_clean(self) -> None:
        """A workflow that doesn't install Nix has nothing to check."""
        self.write(WORKFLOW_PATH, workflow("      - run: echo hello\n"))
        self.assertEqual(self.run_cli()[0], EXIT_CLEAN)

    def test_other_version_is_a_finding_on_the_install_url_line(self) -> None:
        """An address of another release fails and names both addresses."""
        text = workflow(installer_step(install_url=OTHER_URL))
        self.write(WORKFLOW_PATH, text)
        status, lines, stderr = self.run_cli()
        self.assertEqual(status, EXIT_FINDINGS)
        line = line_of_text(text, "install_url")
        expected = (
            f"{WORKFLOW_PATH}:{line}: install_url is {OTHER_URL}; "
            f"set it to {INSTALL_URL}"
        )
        self.assertEqual(lines, [expected])
        self.assertIn("1 finding(s)", stderr)

    def test_missing_address_is_a_finding_on_the_uses_line(self) -> None:
        """The default of the action is a version that the manifest doesn't hold."""
        text = workflow(installer_step(install_url=None))
        self.write(WORKFLOW_PATH, text)
        status, lines, _ = self.run_cli()
        self.assertEqual(status, EXIT_FINDINGS)
        line = line_of_text(text, "install-nix-action")
        self.assertTrue(lines[0].startswith(f"{WORKFLOW_PATH}:{line}: "), lines)
        self.assertIn(f"has no install_url; set it to {INSTALL_URL}", lines[0])

    def test_expression_is_not_the_address(self) -> None:
        """An expression can't be read, so only the exact address passes."""
        self.write(
            WORKFLOW_PATH,
            workflow(installer_step(install_url="${{ inputs.install-url }}")),
        )
        self.assertEqual(self.run_cli()[0], EXIT_FINDINGS)

    def test_address_with_a_trailing_part_is_a_finding(self) -> None:
        """The match is exact: a query string or a slash fails."""
        for suffix in ("?x=1", "/", " "):
            with self.subTest(suffix=suffix):
                step = installer_step(install_url=f'"{INSTALL_URL}{suffix}"')
                self.write(WORKFLOW_PATH, workflow(step))
                self.assertEqual(self.run_cli()[0], EXIT_FINDINGS)

    def test_every_step_is_checked_with_its_own_line(self) -> None:
        """Two steps in two jobs give two findings, each on its own line."""
        bad = installer_step(install_url=OTHER_URL)
        text = jobs_workflow(job("first", bad), job("second", bad))
        self.write(WORKFLOW_PATH, text)
        status, lines, _ = self.run_cli()
        self.assertEqual(status, EXIT_FINDINGS)
        install_lines = [
            number
            for number, line in enumerate(text.splitlines(), start=1)
            if "install_url" in line
        ]
        self.assertEqual(len(install_lines), 2)
        self.assertEqual(
            [line.split(": ")[0] for line in lines],
            [f"{WORKFLOW_PATH}:{n}" for n in install_lines],
        )

    def test_yaml_extension_and_composite_action_are_checked(self) -> None:
        """`.yaml` workflows and every `action.yml` of the tree are read."""
        step = installer_step(install_url=OTHER_URL)
        self.write(".github/workflows/other.yaml", workflow(step))
        self.write(
            "tools/setup/action.yml",
            "name: Setup\nruns:\n  using: composite\n  steps:\n"
            + step.replace("      ", "    "),
        )
        self.write("tools/setup2/action.yaml", "runs:\n  steps:\n" + step[2:])
        _, lines, _ = self.run_cli()
        self.assertEqual(
            sorted(line.split(":")[0] for line in lines),
            [
                ".github/workflows/other.yaml",
                "tools/setup/action.yml",
                "tools/setup2/action.yaml",
            ],
        )

    def test_workflows_in_nested_github_folders_are_read(self) -> None:
        """A workflow folder at any depth counts, as in a template for consumers."""
        step = installer_step(install_url=OTHER_URL)
        nested = (
            "templates/x/.github/workflows/ci.yml",
            "packages/a/b/.github/workflows/release.yaml",
        )
        for path in nested:
            self.write(path, workflow(step))
        _, lines, _ = self.run_cli()
        self.assertEqual(sorted(line.split(":")[0] for line in lines), sorted(nested))

    def test_starter_workflows_of_the_root_are_read(self) -> None:
        """The files `workflow-templates/*.yml` and `*.yaml` are workflows.

        GitHub reads them as the starter workflows of an organization, from the
        root of its `.github` repository.
        """
        step = installer_step(install_url=OTHER_URL)
        starters = ("workflow-templates/ci.yml", "workflow-templates/release.yaml")
        for path in starters:
            self.write(path, workflow(step))
        status, lines, _ = self.run_cli()
        self.assertEqual(status, EXIT_FINDINGS)
        self.assertEqual(sorted(line.split(":")[0] for line in lines), sorted(starters))

    def test_starter_workflow_with_the_right_address_is_clean(self) -> None:
        """A starter workflow with the `$default-branch` placeholder is valid YAML.

        GitHub replaces the placeholder when it creates a workflow from the
        template, and the file is read as it is.
        """
        text = workflow(installer_step(install_url=INSTALL_URL)).replace(
            "on: push", "on:\n  push:\n    branches: [ $default-branch ]"
        )
        self.write("workflow-templates/ci.yml", text)
        self.assertEqual(self.run_cli(), (EXIT_CLEAN, [], ""))

    def test_files_that_are_not_workflows_are_not_read(self) -> None:
        """A YAML file that GitHub doesn't run as a workflow is skipped.

        The files are a YAML file outside a workflow folder, a file in a
        subfolder of `workflows`, a file that isn't YAML, a `workflows` folder
        without `.github`, a file of the `.github` folder itself, and the
        files of a `workflow-templates` folder that GitHub doesn't read: one in
        a subfolder, one below another folder, and the metadata and the icon
        of a template.
        """
        step = installer_step(install_url=OTHER_URL)
        for path in (
            "docs/example.yml",
            ".github/workflows/nested/ci.yml",
            ".github/workflows/notes.txt",
            "workflows/ci.yml",
            "templates/x/.github/ci.yml",
            "templates/x/.github/other/ci.yml",
            "workflow-templates/nested/ci.yml",
            "templates/workflow-templates/ci.yml",
            "workflow-templates/ci.properties.json",
            "workflow-templates/ci.svg",
        ):
            self.write(path, workflow(step))
        self.assertEqual(self.run_cli()[0], EXIT_CLEAN)

    def test_steps_that_share_a_yaml_anchor_give_one_finding(self) -> None:
        """Two `steps` lists that are one anchored node print one finding.

        The finding is the same path, line and message for both steps, so the
        run reports it once and counts it once.
        """
        step = installer_step(install_url=OTHER_URL)
        text = "\n".join(
            [
                "name: CI",
                "on: push",
                "jobs:",
                "  first:",
                "    runs-on: ubuntu-latest",
                "    steps: &install",
            ]
        )
        text += "\n" + step
        text += "\n".join(
            [
                "  second:",
                "    runs-on: ubuntu-latest",
                "    steps: *install",
                "",
            ]
        )
        self.write(WORKFLOW_PATH, text)
        status, lines, stderr = self.run_cli()
        line = line_of_text(text, "install_url")
        self.assertEqual(status, EXIT_FINDINGS)
        self.assertEqual(
            lines,
            [
                f"{WORKFLOW_PATH}:{line}: install_url is {OTHER_URL}; "
                f"set it to {INSTALL_URL}"
            ],
        )
        self.assertIn("1 finding(s)", stderr)

    def test_symbolic_link_is_not_followed(self) -> None:
        """A linked workflow is not read twice or from outside the tree."""
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        target = Path(elsewhere.name) / "ci.yml"
        target.write_text(
            workflow(installer_step(install_url=OTHER_URL)), encoding="utf-8"
        )
        link = self.root / WORKFLOW_PATH
        link.parent.mkdir(parents=True)
        link.symlink_to(target)
        self.assertEqual(self.run_cli()[0], EXIT_CLEAN)

    def test_shapes_that_are_not_steps_are_skipped(self) -> None:
        """A reusable-workflow job, an empty file and odd values don't raise."""
        self.write(
            WORKFLOW_PATH,
            "jobs:\n  call:\n    uses: ./.github/workflows/other.yml\n"
            "  odd:\n    steps: nope\n  none: 3\n  more:\n    steps:\n"
            "      - just a string\n      - uses: 4\n      - name: no uses\n",
        )
        self.write(".github/workflows/empty.yml", "")
        self.write(".github/workflows/list.yml", "- a\n- b\n")
        self.assertEqual(self.run_cli(), (EXIT_CLEAN, [], ""))


class OtherInstallerTest(TreeTestCase):
    """The rule for the installers whose version the check can't read."""

    def setUp(self) -> None:
        """Write a valid manifest."""
        super().setUp()
        self.write("versions.json", MANIFEST)

    def test_other_installer_is_a_finding_on_the_uses_line(self) -> None:
        """Each action that the check knows as an installer of Nix fails.

        The names hold `nix` with `install` in either order, or one of the
        fragments of the list in `versions.installers`.
        """
        for uses in (
            "DeterminateSystems/nix-installer-action@v1",
            "DeterminateSystems/determinate-nix-action@v3",
            "nixbuild/nix-quick-install-action@v30",
            "someone/lix-installer-action@v1",
            "someone/install-nix@v2",
            "someone/install-nix-action-fork@v2",
            "someone/setup-nix-installer@v2",
            "someone/nix-toolchain-install@v1",
            "someone/install-the-nix-toolchain@v1",
            "NixOS/Installer@v1",
            "someone/installnix@v1",
            "someone/nixinstall@v1",
        ):
            with self.subTest(uses=uses):
                text = workflow(installer_step(install_url=None, uses=uses))
                self.write(WORKFLOW_PATH, text)
                status, lines, _ = self.run_cli()
                line = line_of_text(text, uses)
                self.assertEqual(status, EXIT_FINDINGS)
                self.assertTrue(lines[0].startswith(f"{WORKFLOW_PATH}:{line}: "))
                self.assertIn("can't read", lines[0])

    def test_actions_that_are_not_installers_of_nix_are_clean(self) -> None:
        """A name with only `nix` or only `install` isn't an installer of Nix.

        The letters `nix` inside another word, as in `unix` or `phoenix`, aren't
        the word `nix`.
        """
        steps = "".join(
            installer_step(install_url=None, uses=uses)
            for uses in (
                "actions/cache@v4",
                "actions/setup-node@v4",
                "cachix/cachix-action@v16",
                "DeterminateSystems/magic-nix-cache-action@v13",
                "someone/install-tools@v1",
                "someone/setup-phoenix-install@v1",
                "someone/unix-install-tool@v1",
                "someone/minix-installing-kit@v1",
            )
        )
        self.write(WORKFLOW_PATH, workflow(steps))
        self.assertEqual(self.run_cli(), (EXIT_CLEAN, [], ""))

    def test_name_is_compared_without_case_and_reference(self) -> None:
        """`Cachix/Install-Nix-Action` is the installer action, with its rule."""
        step = installer_step(
            install_url=INSTALL_URL, uses="Cachix/Install-Nix-Action@v31"
        )
        self.write(WORKFLOW_PATH, workflow(step))
        self.assertEqual(self.run_cli()[0], EXIT_CLEAN)
        step = installer_step(install_url=OTHER_URL, uses="Cachix/Install-Nix-Action")
        self.write(WORKFLOW_PATH, workflow(step))
        self.assertEqual(self.run_cli()[0], EXIT_FINDINGS)

    def test_local_action_and_unrelated_actions_are_skipped(self) -> None:
        """A local action is checked through its own `action.yml`."""
        steps = "".join(
            installer_step(install_url=None, uses=uses)
            for uses in (
                "./.github/actions/install-nix",
                "docker://example/nix-installer:1",
                "actions/cache@v4",
            )
        )
        self.write(WORKFLOW_PATH, workflow(steps))
        self.assertEqual(self.run_cli(), (EXIT_CLEAN, [], ""))


class RunScriptTest(TreeTestCase):
    """The rule for a `run` script that downloads or runs a Nix installer."""

    def setUp(self) -> None:
        """Write a valid manifest."""
        super().setUp()
        self.write("versions.json", MANIFEST)

    def test_script_with_an_installer_is_a_finding_on_the_run_line(self) -> None:
        """Each address and name of a known installer fails, in any case."""
        scripts = [
            ("nixos.org/nix/install", "curl -L https://nixos.org/nix/install | sh"),
            ("releases.nixos.org/nix/", f"curl -L {OTHER_URL} -o install.sh"),
            (
                "install.determinate.systems",
                "curl -sSfL https://install.determinate.systems/nix | sh -s -- install",
            ),
            ("install.lix.systems", "curl -sSf https://install.lix.systems/lix | sh"),
            ("nix-installer", "./nix-installer install --no-confirm"),
            ("nixos.org/nix/install", "CURL -L HTTPS://NIXOS.ORG/NIX/INSTALL | SH"),
        ]
        for fragment, script in scripts:
            with self.subTest(fragment=fragment):
                text = workflow(run_step("echo start", script))
                self.write(WORKFLOW_PATH, text)
                status, lines, _ = self.run_cli()
                line = line_of_text(text, "run:")
                self.assertEqual(status, EXIT_FINDINGS)
                self.assertEqual(len(lines), 1, lines)
                self.assertTrue(lines[0].startswith(f"{WORKFLOW_PATH}:{line}: "))
                self.assertIn(f"the script uses the Nix installer {fragment}", lines[0])
                self.assertIn("can't read", lines[0])

    def test_script_on_one_line_is_checked(self) -> None:
        """A `run` value that isn't a block scalar is read too."""
        step = "      - run: curl -L https://nixos.org/nix/install | sh\n"
        self.write(WORKFLOW_PATH, workflow(step))
        self.assertEqual(self.run_cli()[0], EXIT_FINDINGS)

    def test_scripts_without_an_installer_are_clean(self) -> None:
        """A script that builds with Nix or mentions an install is fine."""
        step = run_step(
            "nix build .#checks.x86_64-linux.versions -L",
            'echo "install the tools"',
            "curl -sI https://example.org/install",
        )
        self.write(WORKFLOW_PATH, workflow(step))
        self.assertEqual(self.run_cli(), (EXIT_CLEAN, [], ""))

    def test_script_in_a_composite_action_and_a_nested_template_is_checked(
        self,
    ) -> None:
        """The rule applies to every file that the check reads."""
        script = "curl -L https://nixos.org/nix/install | sh"
        self.write(
            "tools/setup/action.yml",
            "runs:\n  using: composite\n  steps:\n"
            f"    - run: {script}\n      shell: bash\n",
        )
        self.write("templates/x/.github/workflows/ci.yml", workflow(run_step(script)))
        _, lines, _ = self.run_cli()
        self.assertEqual(
            sorted(line.split(":")[0] for line in lines),
            ["templates/x/.github/workflows/ci.yml", "tools/setup/action.yml"],
        )

    def test_script_finding_remains_when_the_manifest_is_invalid(self) -> None:
        """The check of an installer doesn't need the version."""
        self.write("versions.json", "{}")
        self.write(
            WORKFLOW_PATH, workflow(run_step("curl https://nixos.org/nix/install"))
        )
        _, lines, _ = self.run_cli()
        self.assertEqual(
            [line.split(":")[0] for line in lines], [WORKFLOW_PATH, "versions.json"]
        )


class ManifestInTreeTest(TreeTestCase):
    """How a manifest problem combines with the workflow rules."""

    def test_missing_manifest_skips_the_address_but_not_other_installers(self) -> None:
        """Without a version, only the installers that can't be read fail."""
        steps = installer_step(install_url=OTHER_URL) + installer_step(
            install_url=None, uses="someone/install-nix@v2"
        )
        self.write(WORKFLOW_PATH, workflow(steps))
        status, lines, _ = self.run_cli()
        self.assertEqual(status, EXIT_FINDINGS)
        self.assertEqual(len(lines), 2, lines)
        self.assertTrue(lines[0].startswith(f"{WORKFLOW_PATH}:"))
        self.assertTrue(lines[1].startswith("versions.json:1: "))

    def test_findings_are_sorted_by_path(self) -> None:
        """A manifest finding and a workflow finding print in path order."""
        self.write("versions.json", "{}")
        self.write(
            WORKFLOW_PATH,
            workflow(installer_step(install_url=None, uses="a/nix-installer@v1")),
        )
        _, lines, _ = self.run_cli()
        self.assertEqual(
            [line.split(":")[0] for line in lines], [WORKFLOW_PATH, "versions.json"]
        )

    def test_invalid_yaml_is_a_finding_on_its_line(self) -> None:
        """A workflow that can't be parsed could hide a step, so it fails."""
        self.write("versions.json", MANIFEST)
        self.write(WORKFLOW_PATH, "name: CI\njobs: [\n")
        status, lines, _ = self.run_cli()
        self.assertEqual(status, EXIT_FINDINGS)
        self.assertRegex(lines[0], rf"^{WORKFLOW_PATH}:\d+: the file isn't valid YAML")

    def test_workflow_that_is_not_utf8_is_a_finding(self) -> None:
        """Bytes that aren't UTF-8 are reported, not raised."""
        self.write("versions.json", MANIFEST)
        self.write(WORKFLOW_PATH, b"name: \xff\n")
        self.assertEqual(
            self.run_cli()[1], [f"{WORKFLOW_PATH}:1: the file isn't UTF-8 text"]
        )


class CommandLineTest(TreeTestCase):
    """The usage errors and the internal error of the command line."""

    def run_main(self, *argv: str) -> tuple[int, str]:
        """Run `main` and return the status and what it printed to stderr."""
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            return main(list(argv)), stderr.getvalue()

    def test_usage_errors_exit_with_two(self) -> None:
        """No root, two roots, an unknown option and a root that isn't a folder."""
        self.write("file.txt", "x")
        for argv in (
            [],
            [str(self.root), str(self.root)],
            ["--nope", str(self.root)],
            [str(self.root / "missing")],
            [str(self.root / "file.txt")],
        ):
            with self.subTest(argv=argv):
                self.assertEqual(self.run_main(*argv)[0], EXIT_USAGE)

    def test_unreadable_manifest_exits_with_two(self) -> None:
        """A folder named `versions.json` is an I/O error, not a finding."""
        (self.root / "versions.json").mkdir()
        status, stderr = self.run_main(str(self.root))
        self.assertEqual(status, EXIT_USAGE)
        self.assertTrue(stderr.startswith("versions: "), stderr)

    def test_unexpected_exception_exits_with_three(self) -> None:
        """A bug in the tool is not a finding: it has its own status and trace."""
        with mock.patch("versions.cli.check_tree", side_effect=RuntimeError("boom")):
            status, stderr = self.run_main(str(self.root))
        self.assertEqual(status, EXIT_INTERNAL)
        self.assertIn("RuntimeError: boom", stderr)
        self.assertIn("internal error", stderr)


if __name__ == "__main__":
    unittest.main()
