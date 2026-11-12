# The cases of `lib.mkStandards`. `default.nix` in this folder collects them.
# The function composes functions that have their own case files, so these
# cases test what the composition adds: the attributes of the result, that each
# check of the result is the real check, that each optional argument reaches
# every part that it names, and the check of the arguments. A case that must
# fail with an evaluation error can't use `expectedLog`, because that only
# reads the log of a failed build, so these cases evaluate the function in Nix
# and build a derivation only when the outcome is right.
{
  pkgs,
  hub,
  harness,
}:
let
  inherit (pkgs) lib;
  inherit (harness) mustHold;

  # The check of the arguments, which `mkStandards` calls first. The cases of
  # the messages call it directly, because a message of an evaluation error is
  # not readable from Nix.
  inherit ((import ../../lib/standards-arguments.nix { inherit lib; })) argumentProblems;

  # The number of a record that no fixture has, and the owner and the name of
  # the repository of the fixtures. The cases pass `name` and the check builds
  # the repository from it.
  missingNumber = "0042";
  name = "fixture";

  # A tree that every check of the standards accepts: the root file of the
  # formatter and a short page. `files` adds to the tree or replaces a file.
  tree =
    label: files:
    harness.mkTree {
      name = "standards-${label}";
      files = {
        "flake.nix" = "{ }\n";
        "README.md" = "# Title\n\nThis page is short.\n";
      }
      // files;
    };
  cleanTree = tree "clean" { };

  # The text of a Nix file that the formatter changes.
  unformatted = "{a=1;}\n";

  # A module that a repository adds: it keeps `example.nix` out of every
  # formatter.
  excludeExample = {
    settings.global.excludes = [ "example.nix" ];
  };

  # A page that cites the missing record, below the folder `fixtures`.
  citingPage = {
    "fixtures/cites.md" = "# Fixture\n\nSee ADR ${missingNumber}.\n";
  };

  # A hook of a repository that always fails, so that a build of `pre-commit`
  # shows whether the hook ran.
  failingHook = {
    enable = true;
    entry = "${pkgs.coreutils}/bin/false";
  };

  # The arguments that every call needs.
  minimal = {
    inherit pkgs name;
    src = cleanTree;
  };

  # The result of `mkStandards` for the minimal arguments with `args` added.
  standards = args: hub.mkStandards (minimal // args);

  # The ids of the hooks in the result of `mkStandards` with `args` added.
  hookIds =
    args: map (hook: hook.id) (builtins.head (standards args).hooks.config.rawConfig.repos).hooks;

  # Whether the evaluation of `value` to its attributes succeeds. A set is
  # forced to the depth of its names, which is where `mkStandards` checks its
  # arguments.
  evaluates = value: (builtins.tryEval (builtins.deepSeq (builtins.attrNames value) true)).success;

  # The names of an attribute set, in the order of `attrNames`.
  namesOf = builtins.attrNames;

  # The command of `mkSecretsScan` for the scanner `scanner`.
  secretsScan = scanner: hub.mkSecretsScan { inherit pkgs scanner; };

  # The scripts of `secrets-scan` carry the store path of their scanner, so a
  # case can read which scanner a command runs.
  runsScanner =
    scanner: command:
    pkgs.runCommand "standards-runs-${scanner.pname}" { } ''
      grep -q ${scanner} ${lib.getExe command}
      touch "$out"
    '';

  # The longest repository name that GitHub accepts: 100 characters.
  longestName = lib.concatStrings (lib.replicate 100 "a");

  # The message for the invalid repository name `given`. It is written out here
  # and not built from the function's own data, like the other messages.
  nameMessage =
    given:
    "`name` must be a repository name of 1 to 100 letters, digits, `.`, `-` and `_`, and not `.` or `..`, got \"${given}\".";

  # The arguments that are valid, and a table of calls that are not. Each row
  # names the situation and holds the arguments that the call adds, and the
  # message that the check of the arguments must report for it. The messages
  # are written out here and not built from the function's own data.
  valid = minimal;
  invalid = {
    unknown-argument = {
      args.foo = 1;
      message = "Unknown arguments: `foo`. The arguments are `decisions`, `hooks`, `name`, `pkgs`, `scanner`, `src`, `treefmtModules`.";
    };
    pkgs-is-not-a-package-set = {
      args.pkgs = { };
      message = "`pkgs` must be a package set, got `set`.";
    };
    src-is-not-a-source = {
      args.src = 1;
      message = "`src` must be a path, an absolute path string or a set with `outPath`, such as `self`, got `int`.";
    };
    src-is-a-relative-string = {
      args.src = "tree/of/the/repository";
      message = "`src` must be a path, an absolute path string or a set with `outPath`, such as `self`, got `string`.";
    };
    name-is-not-a-string = {
      args.name = 1;
      message = "`name` must be a string, got `int`.";
    };
    name-is-not-a-repository-name = {
      args.name = "a b";
      message = nameMessage "a b";
    };
    name-is-a-dot = {
      args.name = ".";
      message = nameMessage ".";
    };
    name-is-two-dots = {
      args.name = "..";
      message = nameMessage "..";
    };
    name-is-empty = {
      args.name = "";
      message = nameMessage "";
    };
    name-is-longer-than-github-allows = {
      args.name = longestName + "a";
      message = nameMessage (longestName + "a");
    };
    treefmt-modules-is-not-a-list = {
      args.treefmtModules = { };
      message = "`treefmtModules` must be a list of modules, got `set`.";
    };
    hooks-is-not-a-set = {
      args.hooks = [ ];
      message = "`hooks` must be a set of hooks, got `list`.";
    };
    decisions-is-not-a-set = {
      args.decisions = [ ];
      message = "`decisions` must be a set, got `list`.";
    };
    decisions-has-an-unknown-key = {
      args.decisions.include = [ ];
      message = "`decisions` has the unknown keys `include`. Its only key is `exclude`.";
    };
    decisions-exclude-is-not-a-list-of-strings = {
      args.decisions.exclude = [ 1 ];
      message = "`decisions.exclude` must be a list of strings, got `list`.";
    };
    scanner-is-not-a-package = {
      args.scanner = "gitleaks";
      message = "`scanner` must be a package, got `string`.";
    };
    scanner-has-no-main-program = {
      args.scanner = pkgs.runCommand "scanner" { } "touch $out";
      message = "`scanner` must have `meta.mainProgram`, so that `lib.getExe` finds its command.";
    };
  };

  # One case for each row of `invalid`: the message is in the list of problems.
  invalidCases = lib.mapAttrs' (
    situation: row:
    lib.nameValuePair "standards-${situation}-is-reported" {
      check =
        mustHold
          "The problems are ${
            builtins.toJSON (argumentProblems (valid // row.args))
          }, and ${row.message} is not one."
          (builtins.elem row.message (argumentProblems (valid // row.args)));
    }
  ) invalid;
in
{
  # Requirement: the result has the four attributes of the contract and no
  # other.
  standards-result-has-the-contract-attributes = {
    check = mustHold "The result has ${builtins.toJSON (namesOf (standards { }))}." (
      namesOf (standards { }) == [
        "checks"
        "formatter"
        "hooks"
        "packages"
      ]
    );
  };

  # Requirement: `checks` has the five checks of the contract and no other. It
  # has no `config-in-sync`, because a repository that calls the function holds
  # no copy of the tool configuration.
  standards-checks-are-the-five-of-the-contract = {
    check = mustHold "The checks are ${builtins.toJSON (namesOf (standards { }).checks)}." (
      namesOf (standards { }).checks == [
        "decisions"
        "docs"
        "formatting"
        "pre-commit"
        "workflows"
      ]
    );
  };

  # Requirement: `packages` has the six commands of the contract and no other,
  # and each one has `meta.mainProgram`, so that `lib.getExe` finds it.
  standards-packages-are-the-six-commands = {
    check =
      let
        packages = (standards { }).packages;
      in
      mustHold
        "The packages are ${builtins.toJSON (namesOf packages)}, and a command lacks meta.mainProgram."
        (
          namesOf packages == [
            "gitpolicy"
            "lychee"
            "markdownlint-cli2"
            "secrets-scan"
            "vale"
            "workflows"
          ]
          && lib.all (package: package ? meta.mainProgram) (lib.attrValues packages)
        );
  };

  # Requirement: the formatter is the treefmt wrapper, and `hooks` is the
  # check `pre-commit`. The same value serves the check and the `shellHook`.
  standards-formatter-and-hooks-are-the-parts = {
    check =
      let
        result = standards { };
      in
      mustHold "The formatter is not the treefmt wrapper, or hooks is not the check pre-commit." (
        result.formatter.meta.mainProgram == "treefmt"
        && result.hooks.outPath == result.checks.pre-commit.outPath
      );
  };

  # Requirement: a tree that satisfies every rule passes all five checks.
  standards-clean-tree-passes = {
    check = pkgs.linkFarm "standards-clean" (standards { }).checks;
  };

  # Requirement: `checks.formatting` is the real check of the formatter: a Nix
  # file that the formatter changes fails it, and the log shows the change.
  standards-formatting-fails-on-unformatted-file = {
    check =
      (standards { src = tree "unformatted" { "example.nix" = unformatted; }; }).checks.formatting;
    expectedLog = [
      "example.nix"
      "+{ a = 1; }"
    ];
  };

  # Requirement: `checks.docs` is the real documentation check: a link to a
  # page that does not exist fails it, and the log names the page.
  standards-docs-fails-on-broken-link = {
    check =
      (standards {
        src = tree "broken-link" { "README.md" = "# Title\n\nRead [it](missing-page.md).\n"; };
      }).checks.docs;
    expectedLog = [ "missing-page.md" ];
  };

  # Requirement: `checks.decisions` is the real decisions check: a citation of
  # a record that does not exist fails it, and the log names the line.
  standards-decisions-fails-on-missing-record = {
    check =
      (standards {
        src = tree "missing-record" { "README.md" = "# Title\n\nSee ADR ${missingNumber}.\n"; };
      }).checks.decisions;
    expectedLog = [ "README.md:3: decision record ${missingNumber} does not exist" ];
  };

  # Requirement: `checks.workflows` is the real workflow check: a job without
  # `timeout-minutes` fails it, and the log names the job.
  standards-workflows-fails-on-missing-timeout = {
    check =
      (standards {
        src = tree "missing-timeout" {
          ".github/workflows/ci.yml" = ''
            name: Fixture
            on: push
            jobs:
              build:
                runs-on: ubuntu-latest
                steps:
                  - run: echo done
          '';
        };
      }).checks.workflows;
    expectedLog = [ "job \"build\" has no timeout-minutes" ];
  };

  # Requirement: `checks.pre-commit` runs the formatter hook of the
  # repository: an unformatted file fails it, and the log names the hook.
  standards-pre-commit-fails-on-unformatted-file = {
    check =
      (standards { src = tree "hook-unformatted" { "example.nix" = unformatted; }; }).checks.pre-commit;
    expectedLog = [ "treefmt" ];
  };

  # Requirement: the name of the repository is `sealambda/<name>`. A citation
  # that this repository qualifies is about this repository, so a missing
  # record fails the decisions check. The case after this one shows that the
  # same citation of another repository passes.
  standards-name-is-the-repository-of-the-citation = {
    check =
      (standards {
        src = tree "own-repository" {
          "README.md" = "# Title\n\nSee sealambda/${name} ADR ${missingNumber}.\n";
        };
      }).checks.decisions;
    expectedLog = [ "README.md:3: decision record ${missingNumber} does not exist" ];
  };

  # Requirement: a citation that another repository of the organization
  # qualifies is skipped. The case before this one fails with the name of the
  # repository under check.
  standards-citation-of-another-repository-passes = {
    check =
      (standards {
        src = tree "other-repository" {
          "README.md" = "# Title\n\nSee sealambda/chironium ADR ${missingNumber}.\n";
        };
      }).checks.decisions;
  };

  # Requirement: a module in `treefmtModules` reaches `checks.formatting`. The
  # unformatted file passes with the module that excludes it, and fails without
  # it in `standards-formatting-fails-on-unformatted-file`.
  standards-treefmt-module-reaches-the-formatting-check = {
    check =
      (standards {
        treefmtModules = [ excludeExample ];
        src = tree "module-check" { "example.nix" = unformatted; };
      }).checks.formatting;
  };

  # Requirement: a module in `treefmtModules` reaches the hook `treefmt` too,
  # so `nix fmt` and the hook format the same way. The unformatted file passes
  # `pre-commit` with the module, and fails it without the module in
  # `standards-pre-commit-fails-on-unformatted-file`.
  standards-treefmt-module-reaches-the-hook = {
    check =
      (standards {
        treefmtModules = [ excludeExample ];
        src = tree "module-hook" { "example.nix" = unformatted; };
      }).checks.pre-commit;
  };

  # Requirement: a module in `treefmtModules` reaches `formatter`. The wrapper
  # of the formatter with the module differs from the one without it, because
  # the settings of a module go into the wrapper.
  standards-treefmt-module-reaches-the-formatter = {
    check = mustHold "The formatter with a module is the formatter without one." (
      (standards { treefmtModules = [ excludeExample ]; }).formatter.outPath != (standards { })
      .formatter.outPath
    );
  };

  # Requirement: the formatter follows the `pkgs` of the caller, and the tools
  # of the other checks come from the hub's nixpkgs. A package set with other
  # `nixfmt`, `vale`, `lychee` and `markdownlint-cli2` packages changes the
  # formatter, the check `formatting` and the check `pre-commit`, which runs the
  # hook `treefmt`. It leaves `docs`, `decisions` and `workflows` as they are.
  # The contract page states this, so the page can't claim one version of every
  # tool.
  standards-pkgs-reach-the-formatter-and-not-the-hub-tools = {
    check =
      let
        changedPkgs = pkgs.extend (
          _final: prev: {
            nixfmt = prev.hello;
            vale = prev.hello;
            lychee = prev.hello;
            markdownlint-cli2 = prev.hello;
          }
        );
        usual = standards { };
        changed = standards { pkgs = changedPkgs; };
        checkDiffers = check: usual.checks.${check}.outPath != changed.checks.${check}.outPath;
      in
      mustHold "The formatter follows pkgs, and the tools of docs, decisions and workflows don't." (
        usual.formatter.outPath != changed.formatter.outPath
        && checkDiffers "formatting"
        && checkDiffers "pre-commit"
        && !(checkDiffers "docs")
        && !(checkDiffers "decisions")
        && !(checkDiffers "workflows")
      );
  };

  # Requirement: a path in `decisions.exclude` is out of the citation scan. The
  # citation of a missing record in an excluded folder passes, and the same
  # tree without the exclusion fails in
  # `standards-decisions-without-exclude-fails`.
  standards-decisions-exclude-passes = {
    check =
      (standards {
        decisions.exclude = [ "fixtures" ];
        src = tree "exclude" citingPage;
      }).checks.decisions;
  };

  # Requirement: without `decisions`, the tree of
  # `standards-decisions-exclude-passes` fails, and the log names the file.
  standards-decisions-without-exclude-fails = {
    check = (standards { src = tree "no-exclude" citingPage; }).checks.decisions;
    expectedLog = [ "fixtures/cites.md:3: decision record ${missingNumber} does not exist" ];
  };

  # Requirement: `decisions = { }` is valid and means no exclusion. The tree
  # that the exclusion saves fails with it, so the empty set doesn't switch the
  # scan off.
  standards-empty-decisions-excludes-nothing = {
    check =
      (standards {
        decisions = { };
        src = tree "empty-decisions" citingPage;
      }).checks.decisions;
    expectedLog = [ "fixtures/cites.md:3: decision record ${missingNumber} does not exist" ];
  };

  # Requirement: a hook in `hooks` runs in addition to the hooks of the hub.
  standards-extra-hook-is-added = {
    check =
      let
        ids = hookIds { hooks.my-hook = failingHook; };
      in
      mustHold "The hooks are ${builtins.toJSON ids}, and my-hook or a hub hook is missing." (
        builtins.all (id: builtins.elem id ids) [
          "my-hook"
          "treefmt"
          "docs"
          "workflows"
          "secrets-scan"
          "gitpolicy-commit-msg"
          "gitpolicy-branch"
        ]
      );
  };

  # Requirement: a hook in `hooks` runs in the check `pre-commit`. The hook
  # always fails, and the log names it. The tree is clean, so the hook of the
  # repository is the only one that fails: `standards-clean-tree-passes` shows
  # that the same tree passes without it.
  standards-extra-hook-runs-in-pre-commit = {
    check = (standards { hooks.my-hook = failingHook; }).checks.pre-commit;
    expectedLog = [ "my-hook" ];
  };

  # Requirement: a hook in `hooks` that has the name of a hub hook is an error,
  # as in `mkHooks`, so a repository can't replace a rule by accident. The
  # case before this one shows that a hook with another name works.
  standards-extra-hook-with-a-hub-name-is-refused = {
    check = mustHold "hooks with the name docs was accepted." (
      !evaluates (standards { hooks.docs = failingHook; }).hooks.config.rawConfig
    );
  };

  # Requirement: without `scanner`, the command `secrets-scan` of the result
  # runs gitleaks, the default of `mkSecretsScan`.
  standards-default-scanner-is-gitleaks = {
    check = runsScanner pkgs.gitleaks (standards { }).packages.secrets-scan;
  };

  # Requirement: the `scanner` of the call is the scanner of the command
  # `secrets-scan` in `packages`.
  standards-scanner-reaches-the-command = {
    check =
      runsScanner pkgs.betterleaks
        (standards { scanner = pkgs.betterleaks; }).packages.secrets-scan;
  };

  # Requirement: the `scanner` of the call is the scanner of the hook
  # `secrets-scan` too, so the command and the hook can't disagree. The hook
  # runs the command of `packages`, and the command of another scanner is a
  # different store path.
  standards-scanner-reaches-the-hook = {
    check =
      let
        betterleaks = standards { scanner = pkgs.betterleaks; };
        hook = lib.findFirst (
          hook: hook.id == "secrets-scan"
        ) null (builtins.head betterleaks.hooks.config.rawConfig.repos).hooks;
      in
      mustHold "The hook runs ${hook.entry}, not the command with betterleaks." (
        hook.entry == "${lib.getExe (secretsScan pkgs.betterleaks)} staged"
        && hook.entry != "${lib.getExe (secretsScan pkgs.gitleaks)} staged"
      );
  };

  # Requirement: a call with every optional argument builds the checks that the
  # call without them builds. The arguments change the checks only as the cases
  # above show.
  standards-every-optional-argument-together-passes = {
    check =
      pkgs.linkFarm "standards-all-options"
        (standards {
          treefmtModules = [ excludeExample ];
          decisions.exclude = [ "fixtures" ];
          hooks.my-hook = {
            enable = true;
            entry = "${pkgs.coreutils}/bin/true";
          };
          scanner = pkgs.betterleaks;
          src = tree "all-options" (citingPage // { "example.nix" = unformatted; });
        }).checks;
  };

  # Requirement: a call with an unknown argument stops the evaluation. The
  # message is in `standards-unknown-argument-is-reported`. The twin shows that
  # the call without the argument works, so the failure comes from the argument.
  standards-unknown-argument-stops-the-evaluation = {
    check = mustHold "A call with the argument foo was accepted, or a valid call failed." (
      evaluates (standards { })
      && !evaluates (standards {
        foo = 1;
      })
    );
  };

  # Requirement: a call with an argument of the wrong type stops the
  # evaluation, before the function builds anything.
  standards-wrong-type-stops-the-evaluation = {
    check = mustHold "A call with name = 1 was accepted." (
      !evaluates (standards {
        name = 1;
      })
    );
  };

  # Requirement: a valid call has no problem.
  standards-valid-arguments-have-no-problem = {
    check =
      mustHold "The valid arguments have the problems ${builtins.toJSON (argumentProblems valid)}."
        (argumentProblems valid == [ ]);
  };

  # Requirement: the names that GitHub accepts are valid, among them the
  # `.github` repository of an organization, a name of 100 characters and a
  # name that mixes the allowed characters. The rows `name-is-a-dot` and the
  # ones after it show that the neighbors of these names are refused.
  standards-github-repository-names-are-valid = {
    check =
      let
        names = [
          ".github"
          longestName
          "a.b-c_d"
          "x"
          "..a"
          "a.."
        ];
        refused = builtins.filter (given: argumentProblems (valid // { name = given; }) != [ ]) names;
      in
      mustHold "The names ${builtins.toJSON refused} were refused." (refused == [ ]);
  };

  # Requirement: a `src` that is a string holding an absolute path is a source,
  # as `"${self}"` is, and all five checks accept it, because each one puts
  # `src` into a command or reads it as a path. The row `src-is-a-relative-string`
  # shows that a relative string is refused.
  standards-absolute-path-string-is-a-source = {
    check = pkgs.linkFarm "standards-string-source" (standards { src = "${cleanTree}"; }).checks;
  };

  # Requirement: every problem of one call is in one message, so a mistake costs
  # one evaluation.
  standards-all-problems-are-reported-together = {
    check =
      let
        problems = argumentProblems (
          valid
          // {
            name = 1;
            foo = 1;
          }
        );
      in
      mustHold "The call has ${toString (builtins.length problems)} problems, and it should have 2." (
        builtins.length problems == 2
      );
  };

  # Requirement: a call without a required argument is reported, and the
  # message names the argument.
  standards-missing-required-argument-is-reported = {
    check =
      let
        problems = argumentProblems (removeAttrs valid [ "name" ]);
      in
      mustHold "The problems are ${builtins.toJSON problems}." (
        problems == [ "Missing required arguments: `name`." ]
      );
  };
}
// invalidCases
