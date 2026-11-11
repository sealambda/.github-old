"""The Nix installers that the version check knows by name and by address.

The hub accepts one way to install Nix: `cachix/install-nix-action` with the
`install_url` that `versions.json` gives. Any other installer is a finding,
because the check can't read the Nix version that it installs. The check
recognizes another installer only by the fragments in `KNOWN_INSTALLERS`. An
installer that no fragment matches isn't found: review covers it
(`docs/reference/versions.md`).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class KnownInstallers:
    """The fragments that identify an installer of Nix other than the accepted one.

    All fragments are lower case, and a text is lowered before it is compared.

    Attributes:
        action_fragments: A `uses` step whose action name (`owner/name`)
            contains one of these is an installer action. The name also
            matches when it holds `nix` and `install` in any order.
        script_fragments: A `run` script that contains one of these downloads
            or runs an installer: an installer address, or the name of the
            installer program.
    """

    action_fragments: tuple[str, ...]
    script_fragments: tuple[str, ...]


KNOWN_INSTALLERS = KnownInstallers(
    action_fragments=(
        "determinate-nix",
        "nix-quick-install",
        "lix-installer",
        "install-nix",
        "nix-installer",
    ),
    script_fragments=(
        "nixos.org/nix/install",
        "releases.nixos.org/nix/",
        "install.determinate.systems",
        "install.lix.systems",
        "nix-installer",
    ),
)
"""The only list of installers that the check knows.

Add a fragment here when a review finds an installer that the list lacks.
"""


def is_other_installer_action(action_name: str) -> bool:
    """Tell whether an action name is a Nix installer other than the accepted one.

    Args:
        action_name: The `owner/name` of the action, without the reference
            after `@`, in any case.

    Returns:
        `True` when the name holds `nix` together with `install`, or one of
        `KNOWN_INSTALLERS.action_fragments`. The caller excludes the accepted
        installer first.
    """
    name = action_name.lower()
    if "nix" in name and "install" in name:
        return True
    return any(fragment in name for fragment in KNOWN_INSTALLERS.action_fragments)


def script_installer_fragment(script: str) -> str | None:
    """Return the known installer fragment that a `run` script holds, if any.

    Args:
        script: The text of the `run` key, in any case.

    Returns:
        The first fragment of `KNOWN_INSTALLERS.script_fragments` in the
        script, or `None` when the script holds none. The search is a plain
        substring search: a script that builds an address from parts isn't
        found.
    """
    text = script.lower()
    for fragment in KNOWN_INSTALLERS.script_fragments:
        if fragment in text:
            return fragment
    return None
