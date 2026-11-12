# The secret scan. `flake.nix` imports this file and exports `mkSecretsScan` as
# `lib.mkSecretsScan`, which a consumer calls, and builds the hub's own
# `secrets-scan` package with it. The command is the script
# `nix/scripts/secrets-scan.sh`, and the base configuration is
# `config/gitleaks.toml`. There is no check function: a flake check sees no Git
# history, so the scan runs in a Git hook and in CI. The reusable workflow
# `secrets.yml` is independent of this file, and the checks of the hub only test
# the command against repositories that the tests build.
{ lib, hubPackagesFor }:
{
  /**
    Builds the `secrets-scan` command: `secrets-scan history` scans the whole
    Git history of the current repository, and `secrets-scan staged` scans the
    staged changes. The output is redacted, and the scanner reads the hub's base
    configuration, which keeps the default rules of the scanner. A repository
    adds fingerprints to its `.gitleaksignore` file, and a `.gitleaks.toml` in a
    repository has no effect. `history` refuses a shallow clone (status 3) and a
    history that Git can't read (status 4), because a scanner reports no finding
    for both. The rules and the exit statuses are in
    `docs/reference/secrets-scan.md`.

    The command and its `git` come from the hub's own nixpkgs, whatever nixpkgs
    the calling flake uses: the function takes only the system from `pkgs`. A
    Git hook or a CI step runs the result with `lib.getExe`.

    # Inputs

    `pkgs`
    : The package set of one system. Only its system is used.

    `scanner`
    : The package of the scanner. It must have `meta.mainProgram` and take
    the `git` command with the flags `--staged`, `--log-opts` (the options of
    `git log` that replace its own defaults, which carry the guards of the
    history scan), `--config`, `--redact`, `--verbose`, `--no-banner` and
    `--no-color`, and it must read the `.gitleaksignore` file. It must run Git
    as the command `git` that it finds on PATH, because the command
    `secrets-scan` puts a `git` first on PATH that adds `--text` and
    `--no-renames` to `git diff` and `git log`. The `git` command of the scanner
    may start with the global options `-C`, `-c`, `--git-dir`, `--work-tree`,
    `--namespace`, `--config-env` and `--attr-source`, and with options that
    have their value after an equals sign. The default is gitleaks of the hub's
    nixpkgs. `betterleaks` is an alternative that the hub's tests also run, and
    it finds no secret in a deflated zip file that it finds without the
    `--text` flag: see `docs/reference/secrets-scan.md`.

    # Type

    ```
    mkSecretsScan :: { pkgs :: AttrSet, scanner :: Derivation ? <hub gitleaks> } -> Derivation
    ```

    The derivation has `meta.mainProgram`, so `lib.getExe` finds the command.
  */
  mkSecretsScan =
    {
      pkgs,
      scanner ? (hubPackagesFor pkgs).gitleaks,
    }:
    let
      hub = hubPackagesFor pkgs;

      # A `git` command that runs Git with `--text` after `diff` and `log`. The
      # command `secrets-scan` puts its folder first on PATH: see
      # `nix/scripts/secrets-scan-git.sh`.
      gitWithText = hub.writeShellApplication {
        name = "git";
        runtimeEnv.SECRETS_SCAN_REAL_GIT = lib.getExe hub.git;
        text = builtins.readFile ../scripts/secrets-scan-git.sh;
      };
    in
    hub.writeShellApplication {
      name = "secrets-scan";
      # The `git` command of the scan, for the tests of its parsing of global
      # options: `nix/tests/secrets-scan.sh` runs it on its own.
      passthru = { inherit gitWithText; };
      runtimeInputs = [ hub.git ];
      runtimeEnv = {
        SECRETS_SCAN_SCANNER = lib.getExe scanner;
        SECRETS_SCAN_CONFIG = "${../../config/gitleaks.toml}";
        SECRETS_SCAN_GIT_DIR = "${gitWithText}/bin";
      };
      text = builtins.readFile ../scripts/secrets-scan.sh;
    };
}
