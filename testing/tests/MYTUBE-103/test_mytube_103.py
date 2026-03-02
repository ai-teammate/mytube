"""
MYTUBE-103: Trigger Deploy API workflow with concurrent commits — runs are
managed without conflict.

Objective:
    Verify that the 'Deploy API' GitHub Actions workflow handles multiple
    simultaneous triggers without causing race conditions or inconsistent
    deployment states. The latest commit must be correctly prioritised and
    concurrent runs must be managed (older runs cancelled or new runs queued)
    to ensure environment consistency.

Test structure:
    Part A — Workflow concurrency static analysis (always runs, no GitHub
              credentials required):
        Reads the deploy-api.yml workflow file and verifies:
        - A ``concurrency`` block is defined at the workflow level.
        - The concurrency ``group`` expression scopes cancellation to the same
          branch so that concurrent pushes to ``main`` are serialised.
        - ``cancel-in-progress: true`` is set so that an older run is
          automatically cancelled when a newer commit arrives, ensuring the
          latest commit is always the one that deploys.

    Part B — GitHub API live run history check (requires GITHUB_TOKEN):
        Uses the GitHub REST API (via 'gh' CLI) to confirm that the recent
        run history on 'main' is consistent with a concurrency-managed
        workflow:
        - There is at most one run in the ``in_progress`` or ``queued``
          state at any given moment (no unbounded pile-up).
        - Any ``cancelled`` runs have a newer sibling run that replaced them,
          confirming that the cancel-in-progress mechanism fired correctly
          rather than an unrelated failure causing the cancellation.
        If GITHUB_TOKEN is not set, this part is skipped with a clear message.
"""

import json
import os
import subprocess
import sys

import pytest
import yaml

# Make the testing root importable regardless of where pytest is invoked from.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)

WORKFLOW_FILE = os.path.join(REPO_ROOT, ".github", "workflows", "deploy-api.yml")

WORKFLOW_NAME = "Deploy API"
TARGET_BRANCH = "main"

# Maximum number of active (in_progress + queued) runs allowed simultaneously.
# With cancel-in-progress enabled, this should never exceed 1 (the newest run).
MAX_CONCURRENT_ACTIVE_RUNS = 1


# ---------------------------------------------------------------------------
# Part A — Concurrency static analysis
# ---------------------------------------------------------------------------


class TestDeployApiConcurrencyConfig:
    """Verify deploy-api.yml has a correctly configured concurrency block."""

    @pytest.fixture(scope="class")
    def workflow_text(self) -> str:
        assert os.path.isfile(WORKFLOW_FILE), (
            f"Workflow file not found at {WORKFLOW_FILE}. "
            "Ensure the repository was checked out correctly."
        )
        with open(WORKFLOW_FILE) as fh:
            return fh.read()

    @pytest.fixture(scope="class")
    def workflow(self, workflow_text: str) -> dict:
        parsed = yaml.safe_load(workflow_text)
        # PyYAML parses bare ``on:`` as Python True (YAML 1.1 boolean quirk).
        if True in parsed and "on" not in parsed:
            parsed["on"] = parsed.pop(True)
        return parsed

    # ------------------------------------------------------------------
    # Concurrency block presence
    # ------------------------------------------------------------------

    def test_concurrency_block_is_defined(self, workflow: dict):
        """The workflow must define a top-level ``concurrency`` block.

        Without it, GitHub Actions will happily run multiple deployments of
        the same workflow in parallel, allowing race conditions when two
        commits land in quick succession on main.
        """
        assert "concurrency" in workflow, (
            "deploy-api.yml does not define a top-level 'concurrency' block. "
            "Without concurrency control, concurrent pushes to main can trigger "
            "simultaneous deployments that race each other, leading to "
            "inconsistent Cloud Run revision states."
        )

    def test_concurrency_group_is_set(self, workflow: dict):
        """The ``concurrency.group`` key must be present and non-empty.

        The group expression determines which runs compete with each other.
        A missing or empty group means every run is in its own group,
        rendering the concurrency block ineffective.
        """
        concurrency = workflow.get("concurrency", {})
        group = concurrency.get("group", "") if isinstance(concurrency, dict) else ""
        assert group, (
            "deploy-api.yml has a 'concurrency' block but no 'group' is defined "
            "(or the group is empty). "
            "The group expression scopes which runs cancel each other; without "
            "it the concurrency block has no effect."
        )

    def test_concurrency_group_includes_branch_reference(self, workflow: dict):
        """The concurrency group expression must reference the branch.

        Scoping the group to the branch (e.g. via ``github.ref`` or
        ``github.ref_name``) ensures that concurrent pushes to the *same*
        branch cancel each other while runs on different branches remain
        independent.
        """
        concurrency = workflow.get("concurrency", {})
        group = str(concurrency.get("group", "")) if isinstance(concurrency, dict) else ""
        branch_expressions = ("github.ref", "github.ref_name", "github.head_ref")
        has_branch_ref = any(expr in group for expr in branch_expressions)
        assert has_branch_ref, (
            f"concurrency.group '{group}' does not reference a branch expression "
            f"({', '.join(branch_expressions)}). "
            "Without a branch reference, runs from different branches could "
            "cancel each other unexpectedly, or concurrent pushes to the same "
            "branch would not be grouped correctly."
        )

    def test_cancel_in_progress_is_true(self, workflow: dict):
        """``concurrency.cancel-in-progress`` must be set to ``true``.

        When a new commit arrives while a previous run is still executing,
        ``cancel-in-progress: true`` causes GitHub Actions to cancel the older
        run immediately, ensuring the freshest commit is the one that deploys.
        Without this flag, the older run continues to completion and may
        overwrite the newer deployment.
        """
        concurrency = workflow.get("concurrency", {})
        cancel = (
            concurrency.get("cancel-in-progress", False)
            if isinstance(concurrency, dict)
            else False
        )
        assert cancel is True, (
            f"concurrency.cancel-in-progress is '{cancel}' — expected True. "
            "Without cancel-in-progress: true, a slow-running older deployment "
            "will complete *after* the newer one, leaving the service running "
            "the older commit's image instead of the latest."
        )

    def test_concurrency_group_is_workflow_scoped(self, workflow: dict):
        """The group must include a workflow-level identifier (name or file).

        If the group expression only uses ``github.ref``, all workflows sharing
        the same branch would cancel each other across different workflow files.
        Including the workflow name or ``github.workflow`` scopes cancellation
        to this specific workflow only.
        """
        concurrency = workflow.get("concurrency", {})
        group = str(concurrency.get("group", "")) if isinstance(concurrency, dict) else ""
        workflow_identifiers = ("github.workflow", "deploy-api", "Deploy API")
        has_workflow_scope = any(ident in group for ident in workflow_identifiers)
        assert has_workflow_scope, (
            f"concurrency.group '{group}' does not include a workflow-level "
            f"identifier. "
            "Expected at least one of: github.workflow, 'deploy-api', or "
            "'Deploy API' in the group string. "
            "Without this, all workflows on the same branch compete in the "
            "same concurrency group and cancel each other unintentionally."
        )


# ---------------------------------------------------------------------------
# Part B — GitHub API live run history check
# ---------------------------------------------------------------------------


def _gh_available() -> bool:
    """Return True if 'gh' CLI is present and authenticated."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return False
    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _list_recent_runs(limit: int = 20) -> list:
    """Fetch recent workflow runs for 'Deploy API' on main, any status."""
    result = subprocess.run(
        [
            "gh", "run", "list",
            "--workflow=deploy-api.yml",
            f"--branch={TARGET_BRANCH}",
            f"--limit={limit}",
            "--json", "databaseId,status,conclusion,createdAt,displayTitle",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"'gh run list' failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return json.loads(result.stdout)


@pytest.mark.skipif(
    not _gh_available(),
    reason=(
        "GITHUB_TOKEN not set or 'gh' CLI not authenticated — "
        "skipping live run history check"
    ),
)
class TestDeployApiConcurrentRunHistory:
    """Verify that the run history is consistent with concurrency management."""

    @pytest.fixture(scope="class")
    def recent_runs(self) -> list:
        """Return up to 20 recent runs of 'Deploy API' on main."""
        return _list_recent_runs(limit=20)

    def test_recent_runs_exist(self, recent_runs: list):
        """There must be at least one recorded run for the Deploy API workflow."""
        assert recent_runs, (
            "No runs found for 'Deploy API' workflow on branch 'main'. "
            "The workflow must have been triggered at least once."
        )

    def test_at_most_one_active_run_at_any_time(self, recent_runs: list):
        """There must be at most one run in an active state right now.

        With ``cancel-in-progress: true``, a second concurrent push causes the
        first run to be cancelled before the second begins.  At any snapshot in
        time we should therefore never see more than one active run.
        """
        active_runs = [
            r for r in recent_runs
            if r.get("status") in ("in_progress", "queued")
        ]
        assert len(active_runs) <= MAX_CONCURRENT_ACTIVE_RUNS, (
            f"Found {len(active_runs)} active run(s) simultaneously; "
            f"expected at most {MAX_CONCURRENT_ACTIVE_RUNS}. "
            f"Active runs: {[r['databaseId'] for r in active_runs]}. "
            "This suggests the workflow's concurrency control is not working "
            "— multiple deployments are running in parallel."
        )

    def test_cancelled_runs_have_newer_replacement(self, recent_runs: list):
        """Every cancelled run must have a newer run that replaced it.

        When ``cancel-in-progress: true`` fires, the cancelled run is replaced
        by a newer run.  If we find a cancelled run with no newer run after it,
        that indicates the cancellation was caused by something other than the
        concurrency mechanism (e.g. a manual cancellation or a workflow bug).

        Runs are ordered newest-first by 'gh run list', so a cancelled run at
        index i should have at least one run at index < i (i.e. a newer run).
        """
        cancelled_runs = [
            (idx, r)
            for idx, r in enumerate(recent_runs)
            if r.get("conclusion") == "cancelled"
        ]

        for idx, cancelled_run in cancelled_runs:
            # Runs with index < idx are newer (gh run list is newest-first).
            newer_runs = recent_runs[:idx]
            assert newer_runs, (
                f"Run #{cancelled_run['databaseId']} ('{cancelled_run.get('displayTitle')}') "
                f"was cancelled but no newer run exists after it. "
                "An isolated cancellation with no replacement suggests the "
                "cancel was not triggered by a concurrent commit — "
                "investigate for unrelated failures or manual cancellations."
            )

    def test_no_concurrent_successful_runs_for_same_commit(
        self, recent_runs: list
    ):
        """No two successful runs should share the same commit title.

        If two runs with the same ``displayTitle`` (which includes the commit
        SHA or message) both succeeded, it implies both ran to completion
        concurrently, bypassing the concurrency cancellation mechanism.
        """
        successful_runs = [
            r for r in recent_runs
            if r.get("conclusion") == "success"
        ]

        title_counts: dict = {}
        for run in successful_runs:
            title = run.get("displayTitle", "")
            title_counts[title] = title_counts.get(title, 0) + 1

        duplicates = {t: c for t, c in title_counts.items() if c > 1}
        assert not duplicates, (
            f"The following commit titles have multiple successful runs, "
            f"suggesting two deployments ran concurrently for the same commit: "
            f"{duplicates}. "
            "This points to a broken or absent concurrency control configuration."
        )
