# The cases of `lib.mkWorkflowsCheck`. `default.nix` in this folder collects
# them. A case holds the check applied to a fixture and, for a case that must
# fail, the text that the log of the failure holds.
{
  pkgs,
  hub,
  harness,
}:
let
  # A tree with one workflow, the text `workflow`, at the path that GitHub reads.
  tree =
    name: workflow:
    harness.mkTree {
      name = "workflows-${name}";
      files.".github/workflows/ci.yml" = workflow;
    };

  # The text of a workflow whose events are `on`. `top` is one line at the top
  # level, after `on`, and `jobExtra` is one key of the job `build`. Both
  # default to an empty line, so the job `build` is on line 5 and each case
  # says whether the workflow has a concurrency group or the job a time limit.
  workflow =
    {
      on,
      top ? "",
      jobExtra ? "",
    }:
    ''
      name: Fixture
      on: ${on}
      ${top}
      jobs:
        build:
          runs-on: ubuntu-latest
          ${jobExtra}
          steps:
            - run: echo done
    '';

  workflowsCheck = hub.mkWorkflowsCheck pkgs;
in
{
  # Requirement: a job with a time limit in a workflow that no pull request
  # triggers passes the check.
  workflows-valid-passes = {
    check = workflowsCheck (
      tree "valid" (workflow {
        on = "push";
        jobExtra = "timeout-minutes: 10";
      })
    );
  };

  # Requirement: a pull request workflow with a time limit and a concurrency
  # group passes the check.
  workflows-pull-request-with-group-passes = {
    check = workflowsCheck (
      tree "pull-request-with-group" (workflow {
        on = "pull_request";
        top = "concurrency: fixture";
        jobExtra = "timeout-minutes: 10";
      })
    );
  };

  # Requirement: a job without `timeout-minutes` fails the check, and the log
  # names the job and the line of the job.
  workflows-missing-timeout-fails = {
    check = workflowsCheck (
      tree "missing-timeout" (workflow {
        on = "push";
      })
    );
    expectedLog = [
      ".github/workflows/ci.yml:5: job \"build\" has no timeout-minutes"
    ];
  };

  # Requirement: a `timeout-minutes` above 360 fails the check, and the log
  # names the value.
  workflows-timeout-too-large-fails = {
    check = workflowsCheck (
      tree "timeout-too-large" (workflow {
        on = "push";
        jobExtra = "timeout-minutes: 361";
      })
    );
    expectedLog = [
      "job \"build\" has timeout-minutes 361"
    ];
  };

  # Requirement: a pull request workflow without a concurrency group fails
  # the check, and the log names the event.
  workflows-missing-concurrency-fails = {
    check = workflowsCheck (
      tree "missing-concurrency" (workflow {
        on = "pull_request";
        jobExtra = "timeout-minutes: 10";
      })
    );
    expectedLog = [
      ".github/workflows/ci.yml:2: the workflow runs on pull_request and has no concurrency group"
    ];
  };
}
