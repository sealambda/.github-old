"""The two rules: a time limit for each job and a group for each pull request run."""

from decisions.findings import Finding
from decisions.workflow_files import ActionsFile
from workflows.triggers import read_triggers

MAX_TIMEOUT_MINUTES = 360
"""The largest `timeout-minutes` that the rule accepts: six hours.

GitHub caps a step at 360 minutes on every runner and a job on a hosted runner
at six hours; a job on a self-hosted runner may run for five days. The rule
holds every job to the six hours: a job that needs more is a design to review.
"""

PULL_REQUEST_EVENTS = frozenset({"pull_request", "pull_request_target"})
"""The events whose runs the rule for concurrency covers."""

_EXPRESSION_OPEN = "${{"
_EXPRESSION_CLOSE = "}}"


def _is_single_expression(text: str) -> bool:
    """Tell whether `text` is exactly one balanced expression `${{ ... }}`.

    Whitespace around the expression is allowed. The first `}}` after the
    opening `${{` must end the text, and the text between the delimiters must
    not be empty or blank and must not hold another `${{`. So an unclosed
    `${{ x`, an empty `${{ }}`, two expressions in a row and a stray `}}` are
    not one expression. An expression whose string literal holds `}}` is not
    accepted either: the check doesn't parse the expression language.
    """
    stripped = text.strip()
    if not stripped.startswith(_EXPRESSION_OPEN):
        return False
    inner = stripped[len(_EXPRESSION_OPEN) :]
    close = inner.find(_EXPRESSION_CLOSE)
    if close < 0 or close != len(inner) - len(_EXPRESSION_CLOSE):
        return False
    body = inner[:close]
    return bool(body.strip()) and _EXPRESSION_OPEN not in body


def _is_valid_timeout(value: object) -> bool:
    """Tell whether a `timeout-minutes` value meets the rule.

    A value is valid when it is a whole number from 1 to `MAX_TIMEOUT_MINUTES`,
    or a string that is exactly one expression, whose value the file doesn't
    hold. A boolean is not a number here, although Python counts it as an
    integer.
    """
    if isinstance(value, str):
        return _is_single_expression(value)
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 1 <= value <= MAX_TIMEOUT_MINUTES
    )


def check_timeouts(file: ActionsFile) -> list[Finding]:
    """Return a finding for each job that has no valid time limit.

    A job that calls a reusable workflow (it has `uses`) is skipped: GitHub
    doesn't allow `timeout-minutes` there, and the called workflow sets the
    limit of its own jobs. Every other job needs `timeout-minutes`. A job or a
    `jobs` value of another shape is skipped: actionlint reports it.

    Args:
        file: The parsed workflow.
    """
    data = file.document.data
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, dict):
        return []
    findings = []
    for job_id, job in jobs.items():
        if not isinstance(job, dict) or "uses" in job:
            continue
        finding = _check_job_timeout(file, str(job_id), job)
        if finding is not None:
            findings.append(finding)
    return findings


def _check_job_timeout(
    file: ActionsFile, job_id: str, job: dict[object, object]
) -> Finding | None:
    """Return the finding for the time limit of one job, or `None` when it is fine."""
    advice = (
        f"set timeout-minutes to a whole number from 1 to {MAX_TIMEOUT_MINUTES}"
        " or to an expression"
    )
    if "timeout-minutes" not in job:
        return file.finding(
            ["jobs", job_id], f'job "{job_id}" has no timeout-minutes; {advice}'
        )
    value = job["timeout-minutes"]
    if _is_valid_timeout(value):
        return None
    return file.finding(
        ["jobs", job_id, "timeout-minutes"],
        f'job "{job_id}" has timeout-minutes {value!r}; {advice}',
    )


def check_concurrency(file: ActionsFile) -> list[Finding]:
    """Return a finding when a pull request workflow has no concurrency group.

    The rule covers a workflow that `pull_request` or `pull_request_target`
    triggers. It is met by a `concurrency` group at the top of the workflow, or
    by a `concurrency` group on every job, a job that calls a reusable workflow
    included. `_sets_group` says what counts as a group. A workflow that only
    `workflow_call` triggers is a reusable workflow: its caller owns the group,
    so the rule doesn't cover it.

    Args:
        file: The parsed workflow.

    Returns:
        No finding, or one finding at the first pull request event.
    """
    data = file.document.data
    triggers = [t for t in read_triggers(data) if t.name in PULL_REQUEST_EVENTS]
    if not triggers or not isinstance(data, dict):
        return []
    if _sets_group(data.get("concurrency")) or _every_job_has_concurrency(data):
        return []
    trigger = triggers[0]
    return [
        file.finding(
            trigger.location,
            f"the workflow runs on {trigger.name} and has no concurrency group; "
            "set concurrency at the top level or on every job",
        )
    ]


def _sets_group(value: object) -> bool:
    """Tell whether a `concurrency` value names a group.

    The value is a string, which is the group, or a mapping with a `group` key
    whose value is a string. A blank string is no group. A mapping that holds
    only `cancel-in-progress` is no group either: GitHub requires `group` in the
    mapping form. The check doesn't read the group expression.
    """
    if isinstance(value, dict):
        value = value.get("group")
    return isinstance(value, str) and bool(value.strip())


def _every_job_has_concurrency(data: dict[object, object]) -> bool:
    """Tell whether `jobs` holds at least one job and each one sets a group."""
    jobs = data.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return False
    return all(
        isinstance(job, dict) and _sets_group(job.get("concurrency"))
        for job in jobs.values()
    )
