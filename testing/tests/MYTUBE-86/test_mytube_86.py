"""
MYTUBE-86: Execute Deploy API workflow on main branch — run completes successfully.

Objective:
    Verify that the 'Deploy API' GitHub Actions workflow, which previously failed in
    run #3, now completes successfully on the main branch.

    Expected result:
        The most recent workflow run on 'main' finishes with a green success status,
        and all jobs (Build/Deploy) are executed without errors.

Test structure:
    Part A — Workflow file static analysis (always runs, no GitHub credentials required):
        Reads the deploy-api.yml workflow file and verifies:
        - The workflow file exists at the expected path.
        - The workflow is configured to trigger on pushes to 'main'.
        - All expected deployment jobs and steps are defined.
        - Required GCP secrets and env vars are referenced.

    Part B — GitHub API live check (requires GITHUB_TOKEN):
        Uses the GitHub REST API (via 'gh' CLI) to confirm:
        - The most recent completed run of 'Deploy API' on 'main' has
          conclusion == 'success'.
        - All jobs in that run completed with success.
        - All expected step names are present and succeeded.
        If GITHUB_TOKEN is not set, this part is skipped with a clear message.
"""

import json
import os
import re
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

EXPECTED_STEP_NAMES = [
    "Checkout repository",
    "Authenticate to GCP",
    "Set up Cloud SDK",
    "Configure Docker for GCR",
    "Build and push Docker image",
    "Deploy to Cloud Run",
    "Show service URL",
    "Delete old Cloud Run revisions",
    "Delete old GCR images",
]


# ---------------------------------------------------------------------------
# Part A — Workflow file static analysis
# ---------------------------------------------------------------------------


class TestDeployApiWorkflowStructure:
    """Verify the deploy-api.yml workflow file is correctly structured."""

    @pytest.fixture(scope="class")
    def workflow(self):
        assert os.path.isfile(WORKFLOW_FILE), (
            f"Workflow file not found at {WORKFLOW_FILE}. "
            "Ensure the repository was checked out correctly."
        )
        with open(WORKFLOW_FILE) as f:
            return yaml.safe_load(f)

    def test_workflow_file_exists(self):
        """The deploy-api.yml file must exist at the expected path."""
        assert os.path.isfile(WORKFLOW_FILE), (
            f"Expected workflow file at: {WORKFLOW_FILE}"
        )

    def test_workflow_name_is_deploy_api(self, workflow):
        """The workflow must be named 'Deploy API'."""
        assert workflow.get("name") == WORKFLOW_NAME, (
            f"Expected workflow name '{WORKFLOW_NAME}', got: {workflow.get('name')}"
        )

    def test_workflow_triggers_on_push_to_main(self, workflow):
        """The workflow must be triggered by pushes to the main branch."""
        # PyYAML parses the bare 'on' key as boolean True, not the string "on".
        on_config = workflow.get(True) or workflow.get("on") or {}
        push_config = on_config.get("push", {})
        branches = push_config.get("branches", [])
        assert TARGET_BRANCH in branches, (
            f"Expected 'main' in push.branches, got: {branches}"
        )

    def test_workflow_has_deploy_job(self, workflow):
        """The workflow must define a 'deploy' job."""
        jobs = workflow.get("jobs", {})
        assert "deploy" in jobs, (
            f"Expected a 'deploy' job, found jobs: {list(jobs.keys())}"
        )

    def test_deploy_job_has_all_expected_steps(self, workflow):
        """All expected deployment steps must be present in the deploy job."""
        steps = workflow["jobs"]["deploy"].get("steps", [])
        step_names = [s.get("name", "") for s in steps]
        for expected in EXPECTED_STEP_NAMES:
            assert expected in step_names, (
                f"Expected step '{expected}' not found in workflow steps. "
                f"Found: {step_names}"
            )

    def test_gcp_auth_uses_secret(self, workflow):
        """GCP authentication step must use the GCP_SA_KEY secret."""
        steps = workflow["jobs"]["deploy"].get("steps", [])
        auth_step = next(
            (s for s in steps if s.get("name") == "Authenticate to GCP"), None
        )
        assert auth_step is not None, "Step 'Authenticate to GCP' not found"
        credentials = auth_step.get("with", {}).get("credentials_json", "")
        assert "GCP_SA_KEY" in credentials, (
            f"Expected GCP_SA_KEY in credentials_json, got: {credentials}"
        )

    def test_deploy_step_uses_correct_service_name(self, workflow):
        """The Cloud Run deploy step must target the 'mytube-api' service."""
        env = workflow.get("env", {})
        service = env.get("SERVICE", "")
        assert service == "mytube-api", (
            f"Expected SERVICE to be 'mytube-api', got: {service}"
        )

    def test_docker_image_references_gcr(self, workflow):
        """The Docker image must be pushed to GCR (gcr.io)."""
        env = workflow.get("env", {})
        image = env.get("IMAGE", "")
        assert image.startswith("gcr.io/"), (
            f"Expected IMAGE to start with 'gcr.io/', got: {image}"
        )

    def test_workflow_references_cloud_sql_connection(self, workflow):
        """The deploy step must configure a Cloud SQL instance connection."""
        steps = workflow["jobs"]["deploy"].get("steps", [])
        deploy_step = next(
            (s for s in steps if s.get("name") == "Deploy to Cloud Run"), None
        )
        assert deploy_step is not None, "Step 'Deploy to Cloud Run' not found"
        run_script = deploy_step.get("run", "")
        assert "CLOUD_SQL_CONNECTION_NAME" in run_script, (
            "Expected CLOUD_SQL_CONNECTION_NAME to be referenced in deploy step"
        )

    def test_paths_filter_includes_api_directory(self, workflow):
        """Workflow must only trigger for changes in api/ or workflow file itself."""
        # PyYAML parses the bare 'on' key as boolean True, not the string "on".
        on_config = workflow.get(True) or workflow.get("on") or {}
        paths = on_config.get("push", {}).get("paths", [])
        assert any(p.startswith("api/") for p in paths), (
            f"Expected paths filter to include 'api/**', got: {paths}"
        )


# ---------------------------------------------------------------------------
# Part B — GitHub API live run check
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


def _get_recent_runs(limit: int = 5) -> list:
    """Fetch recent completed runs for the Deploy API workflow on main."""
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


def _get_run_details(run_id: int) -> dict:
    """Fetch full details including jobs and steps for a specific run."""
    result = subprocess.run(
        [
            "gh", "run", "view",
            str(run_id),
            "--json", "databaseId,status,conclusion,createdAt,displayTitle,jobs",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"'gh run view {run_id}' failed:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return json.loads(result.stdout)


@pytest.mark.skipif(
    not _gh_available(),
    reason="GITHUB_TOKEN not set or 'gh' CLI not authenticated — skipping live run check",
)
class TestDeployApiWorkflowRuns:
    """Verify the most recent Deploy API workflow run on main succeeded."""

    @pytest.fixture(scope="class")
    def latest_run(self):
        """Return the most recent completed run details."""
        runs = _get_recent_runs(limit=10)
        completed = [r for r in runs if r.get("status") == "completed"]
        assert completed, (
            "No completed runs found for 'Deploy API' workflow on branch 'main'. "
            "The workflow may not have been triggered yet."
        )
        # Most recent completed run
        latest = completed[0]
        return _get_run_details(latest["databaseId"])

    def test_most_recent_run_exists(self, latest_run):
        """There must be at least one completed run of 'Deploy API' on main."""
        assert latest_run is not None
        assert latest_run.get("databaseId"), "Run must have a valid ID"

    def test_most_recent_run_conclusion_is_success(self, latest_run):
        """The most recent completed run must have conclusion 'success'."""
        conclusion = latest_run.get("conclusion")
        run_id = latest_run.get("databaseId")
        display_title = latest_run.get("displayTitle", "")
        assert conclusion == "success", (
            f"Expected run #{run_id} ('{display_title}') to have conclusion 'success', "
            f"got: '{conclusion}'. "
            "The Deploy API workflow has not completed successfully on main."
        )

    def test_deploy_job_completed_with_success(self, latest_run):
        """The 'deploy' job must have completed with success."""
        jobs = latest_run.get("jobs", [])
        assert jobs, f"No jobs found in run #{latest_run.get('databaseId')}"
        deploy_job = next((j for j in jobs if j.get("name") == "deploy"), None)
        assert deploy_job is not None, (
            f"Expected a job named 'deploy', found: {[j.get('name') for j in jobs]}"
        )
        assert deploy_job.get("conclusion") == "success", (
            f"'deploy' job conclusion: {deploy_job.get('conclusion')}"
        )
        assert deploy_job.get("status") == "completed", (
            f"'deploy' job status: {deploy_job.get('status')}"
        )

    def test_all_expected_steps_succeeded(self, latest_run):
        """All expected deployment steps must have succeeded."""
        jobs = latest_run.get("jobs", [])
        deploy_job = next((j for j in jobs if j.get("name") == "deploy"), None)
        assert deploy_job is not None, "Job 'deploy' not found"

        steps = deploy_job.get("steps", [])
        step_map = {s["name"]: s for s in steps}

        for step_name in EXPECTED_STEP_NAMES:
            assert step_name in step_map, (
                f"Expected step '{step_name}' not found in run steps. "
                f"Found steps: {list(step_map.keys())}"
            )
            step = step_map[step_name]
            assert step.get("conclusion") == "success", (
                f"Step '{step_name}' did not succeed. "
                f"conclusion={step.get('conclusion')}, status={step.get('status')}"
            )

    def test_gcp_auth_step_succeeded(self, latest_run):
        """The 'Authenticate to GCP' step must have succeeded."""
        jobs = latest_run.get("jobs", [])
        deploy_job = next((j for j in jobs if j.get("name") == "deploy"), None)
        assert deploy_job is not None
        steps = {s["name"]: s for s in deploy_job.get("steps", [])}
        auth_step = steps.get("Authenticate to GCP")
        assert auth_step is not None, "Step 'Authenticate to GCP' not found"
        assert auth_step.get("conclusion") == "success", (
            f"GCP authentication step failed: {auth_step}"
        )

    def test_docker_build_and_push_succeeded(self, latest_run):
        """The 'Build and push Docker image' step must have succeeded."""
        jobs = latest_run.get("jobs", [])
        deploy_job = next((j for j in jobs if j.get("name") == "deploy"), None)
        assert deploy_job is not None
        steps = {s["name"]: s for s in deploy_job.get("steps", [])}
        build_step = steps.get("Build and push Docker image")
        assert build_step is not None, "Step 'Build and push Docker image' not found"
        assert build_step.get("conclusion") == "success", (
            f"Docker build/push step failed: {build_step}"
        )

    def test_cloud_run_deploy_step_succeeded(self, latest_run):
        """The 'Deploy to Cloud Run' step must have succeeded."""
        jobs = latest_run.get("jobs", [])
        deploy_job = next((j for j in jobs if j.get("name") == "deploy"), None)
        assert deploy_job is not None
        steps = {s["name"]: s for s in deploy_job.get("steps", [])}
        deploy_step = steps.get("Deploy to Cloud Run")
        assert deploy_step is not None, "Step 'Deploy to Cloud Run' not found"
        assert deploy_step.get("conclusion") == "success", (
            f"Cloud Run deploy step failed: {deploy_step}"
        )

    def test_run_triggered_on_main_branch(self, latest_run):
        """The successful run must have been triggered on the main branch."""
        # The branch info comes from the run list (not view), but we can verify
        # indirectly by checking that we fetched from the main-branch run list.
        # The latest_run fixture already filtered by --branch=main.
        assert latest_run.get("databaseId") is not None, (
            "Run ID must be valid — confirming run was fetched from main branch filter"
        )
