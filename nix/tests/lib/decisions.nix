# The cases of `lib.mkDecisionsCheck`. `default.nix` in this folder collects
# them. A case holds the check applied to a fixture and, for a case that must
# fail, the text that the log of the failure holds.
{
  pkgs,
  hub,
  harness,
}:
let
  inherit (pkgs) lib;

  # The folder of the records, built from two parts. The hub's own decisions
  # check reads the files of this repository for citations, and it would
  # resolve a path or a citation that this file writes out, so this file
  # writes neither: a citation is "ADR " and a number from `existingNumber` or
  # `missingNumber`.
  recordsFolder = "docs" + "/decisions";

  # The number of the record that every tree has.
  existingNumber = "0001";

  # The path of that record in a tree.
  recordPath = "${recordsFolder}/${existingNumber}-first.md";

  # A record with valid front matter and a title.
  record = ''
    ---
    status: accepted
    date: 2026-01-01
    decision-makers: Test Maker
    ---

    # A decision
  '';

  # The same record with a status that the schema does not list.
  unknownStatus = "wished";
  recordWithUnknownStatus = lib.replaceStrings [ "accepted" ] [ unknownStatus ] record;

  # A tree with the record `existingNumber`, a page of the text `readme`, and
  # the files of `extraFiles`. A file of `extraFiles` replaces a file of the
  # tree with the same path.
  tree =
    name: readme: extraFiles:
    harness.mkTree {
      name = "decisions-${name}";
      files = {
        ${recordPath} = record;
        "README.md" = readme;
      }
      // extraFiles;
    };

  # The repository that holds the fixture, and another repository of the same
  # owner.
  repository = "example/fixture";
  otherRepository = "example/other";

  # The check as a repository calls it, for the repository `example/fixture`,
  # with the options of `options` added to the call.
  decisionsCheckWith =
    options: src: hub.mkDecisionsCheck pkgs src ({ inherit repository; } // options);
  decisionsCheck = decisionsCheckWith { };

  # The number of a record that the tree has not.
  missingNumber = "0042";

  # A page that cites the missing record, under a folder that a case excludes.
  citingPage = {
    "fixtures/cites.md" = "# Fixture\n\nSee ADR ${missingNumber}.\n";
  };
in
{
  # Requirement: a set of records with valid front matter, and a citation of a
  # record that exists, pass the check.
  decisions-valid-set-passes = {
    check = decisionsCheck (tree "valid-set" "# Title\n\nSee ADR ${existingNumber}.\n" { });
  };

  # Requirement: a record whose front matter breaks the schema fails the
  # check, and the log names the record and the field. The tree is the one of
  # `decisions-valid-set-passes` with one changed field, so only the record
  # can cause the failure.
  decisions-unknown-status-fails = {
    check = decisionsCheck (
      tree "unknown-status" "# Title\n\nSee ADR ${existingNumber}.\n" {
        ${recordPath} = recordWithUnknownStatus;
      }
    );
    expectedLog = [
      "${recordPath}:2: status: '${unknownStatus}' is not one of"
    ];
  };

  # Requirement: a citation of a record that does not exist fails the check,
  # and the log names the number and the line of the citation. This is also
  # the unqualified form of the citation in `decisions-other-repository-passes`.
  decisions-missing-record-fails = {
    check = decisionsCheck (tree "missing-record" "# Title\n\nSee ADR ${missingNumber}.\n" { });
    expectedLog = [
      "README.md:3: decision record ${missingNumber} does not exist"
    ];
  };

  # Requirement: a citation that another repository of the same owner
  # qualifies is about that repository, so the check skips it. The same
  # citation without the qualifier fails in `decisions-missing-record-fails`.
  decisions-other-repository-passes = {
    check = decisionsCheck (
      tree "other-repository" "# Title\n\nSee ${otherRepository} ADR ${missingNumber}.\n" { }
    );
  };

  # Requirement: a citation that the repository under check qualifies is about
  # this repository, so the check does not skip it. The name that the caller
  # passes as `repository` decides which qualifier counts.
  decisions-own-repository-fails = {
    check = decisionsCheck (
      tree "own-repository" "# Title\n\nSee ${repository} ADR ${missingNumber}.\n" { }
    );
    expectedLog = [
      "README.md:3: decision record ${missingNumber} does not exist"
    ];
  };

  # Requirement: a path in `exclude` is out of the citation scan, with the
  # files below it. A citation of a missing record in an excluded folder
  # passes, and the same tree without the exclusion fails in
  # `decisions-no-exclude-fails`.
  decisions-exclude-passes = {
    check = decisionsCheckWith { exclude = [ "fixtures" ]; } (
      tree "exclude" "# Title\n\nSee ADR ${existingNumber}.\n" citingPage
    );
  };

  # Requirement: without `exclude`, the same tree as in
  # `decisions-exclude-passes` fails, and the log names the file of the
  # citation.
  decisions-no-exclude-fails = {
    check = decisionsCheck (tree "no-exclude" "# Title\n\nSee ADR ${existingNumber}.\n" citingPage);
    expectedLog = [
      "fixtures/cites.md:3: decision record ${missingNumber} does not exist"
    ];
  };
}
