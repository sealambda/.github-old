# The check of the arguments of `mkStandards`. `standards.nix` calls it before
# it builds anything, and `nix/tests/lib/standards.nix` calls it to test the
# text of each message. The function is pure and needs only `lib`, so the tests
# import this file without the rest of the hub.
{ lib }:
let
  # The arguments that `mkStandards` takes: `required` has no default, and
  # `optional` has one.
  required = [
    "pkgs"
    "src"
    "name"
  ];
  optional = [
    "treefmtModules"
    "decisions"
    "hooks"
    "scanner"
  ];

  # The keys that the argument `decisions` can hold.
  decisionsKeys = [ "exclude" ];

  # The type of `value` for a message: the name that Nix gives it, and
  # `derivation` for a derivation, which Nix types as a set.
  describe = value: if lib.isDerivation value then "a derivation" else "`${builtins.typeOf value}`";

  # Lists names for a message, in quotes and in a fixed order.
  quoted = names: lib.concatMapStringsSep ", " (name: "`${name}`") (lib.sort lib.lessThan names);

  # The message for an argument that has the wrong type: what the argument
  # must be, and what the caller passed.
  wrongType =
    argument: expected: value:
    "`${argument}` must be ${expected}, got ${describe value}.";

  # A repository name on GitHub: 1 to 100 ASCII letters, digits, dots, dashes
  # and underscores, and not `.` or `..`, which name a folder and not a
  # repository. GitHub documents the characters and the length. A name such as
  # `.github` is valid. The pattern holds the same limit of 100 as the message
  # in `problemsOfRequired`.
  isRepositoryName =
    name:
    lib.isString name
    && builtins.match "[A-Za-z0-9._-]{1,100}" name != null
    && !(builtins.elem name [
      "."
      ".."
    ]);

  # The source tree: a path, a string that holds an absolute path such as
  # `"${self}"`, or a set with `outPath`, as a flake's `self` or a derivation
  # has. The checks put `src` into a command and the hooks read it as a path,
  # so a string works when it is absolute: a relative string is no source.
  isSource =
    src:
    lib.isPath src || (lib.isString src && lib.hasPrefix "/" src) || (lib.isAttrs src && src ? outPath);

  # The message for a `pkgs` that is not a package set. A set without `stdenv`
  # is typically the flake `nixpkgs` and not its `legacyPackages.<system>`, so
  # the message says what the set lacks. A value that is no set gets the
  # message about its type.
  pkgsMessage =
    pkgs:
    if lib.isAttrs pkgs then
      "`pkgs` must be a package set such as `nixpkgs.legacyPackages.<system>`, and this set has no `stdenv`."
    else
      wrongType "pkgs" "a package set" pkgs;

  # The problems of `pkgs`, `src` and `name`.
  problemsOfRequired =
    args:
    lib.optional (args ? pkgs && !(lib.isAttrs args.pkgs && args.pkgs ? stdenv)) (pkgsMessage args.pkgs)
    ++ lib.optional (args ? src && !isSource args.src) (
      wrongType "src" "a path, an absolute path string or a set with `outPath`, such as `self`" args.src
    )
    ++ lib.optional (args ? name && !isRepositoryName args.name) (
      if lib.isString args.name then
        "`name` must be a repository name of 1 to 100 letters, digits, `.`, `-` and `_`, and not `.` or `..`, got \"${args.name}\"."
      else
        wrongType "name" "a string" args.name
    );

  # The problems of `treefmtModules` and `hooks`.
  problemsOfCollections =
    args:
    lib.optional (args ? treefmtModules && !lib.isList args.treefmtModules) (
      wrongType "treefmtModules" "a list of modules" args.treefmtModules
    )
    ++ lib.optional (args ? hooks && !lib.isAttrs args.hooks) (
      wrongType "hooks" "a set of hooks" args.hooks
    );

  # The problems of `decisions`: a set whose only key is `exclude`, a list of
  # strings.
  problemsOfDecisions =
    args:
    let
      value = args.decisions;
      unknownKeys = builtins.attrNames (removeAttrs value decisionsKeys);
    in
    if !lib.isAttrs value then
      [ (wrongType "decisions" "a set" value) ]
    else
      lib.optional (
        unknownKeys != [ ]
      ) "`decisions` has the unknown keys ${quoted unknownKeys}. Its only key is `exclude`."
      ++ lib.optional (
        value ? exclude && !(lib.isList value.exclude && lib.all lib.isString value.exclude)
      ) (wrongType "decisions.exclude" "a list of strings" value.exclude);

  # The problems of `scanner`: a package that `lib.getExe` can run.
  problemsOfScanner =
    args:
    lib.optional (args ? scanner && !(lib.isDerivation args.scanner)) (
      wrongType "scanner" "a package" args.scanner
    )
    ++ lib.optional (
      args ? scanner && lib.isDerivation args.scanner && !(args.scanner ? meta.mainProgram)
    ) "`scanner` must have `meta.mainProgram`, so that `lib.getExe` finds its command.";
in
{
  /**
    Lists what is wrong with the arguments of `mkStandards`, as sentences. The
    list is empty when the arguments are valid. The check covers the names,
    the required arguments and the type of each value, and it reports every
    problem at once. A message about a type names the type that the caller
    passed. The check reads the shape of `pkgs`, `src` and `scanner` and
    builds nothing.

    # Inputs

    `args`
    : The attribute set that the caller passes to `mkStandards`.

    # Type

    ```
    argumentProblems :: AttrSet -> [String]
    ```
  */
  argumentProblems =
    args:
    let
      known = required ++ optional;
      unknown = builtins.attrNames (removeAttrs args known);
      missing = builtins.filter (name: !(args ? ${name})) required;
    in
    lib.optional (
      unknown != [ ]
    ) "Unknown arguments: ${quoted unknown}. The arguments are ${quoted known}."
    ++ lib.optional (missing != [ ]) "Missing required arguments: ${quoted missing}."
    ++ problemsOfRequired args
    ++ problemsOfCollections args
    ++ lib.optionals (args ? decisions) (problemsOfDecisions args)
    ++ problemsOfScanner args;
}
