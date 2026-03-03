# MYTUBE-86 — Execute Deploy API workflow on main branch: run completes successfully

## What this test verifies

The `Deploy API` GitHub Actions workflow (`.github/workflows/deploy-api.yml`)
completes successfully on the `main` branch, addressing a previous failure in
run #3.

The test is split into two parts:

**Part A — Workflow file static analysis (always runs, no GitHub credentials required)**

Reads `.github/workflows/deploy-api.yml` and verifies:

- The workflow file exists at the expected path.
- The workflow is named `Deploy API`.
- It is configured to trigger on pushes to `main`.
- All expected deployment steps are defined (checkout, GCP auth, gcloud setup,
  Docker build/push, Cloud Run deploy, show URL, cleanup revisions and images).
- GCP authentication uses the `GCP_SA_KEY` secret.
- The Cloud Run service name is `mytube-api`.
- The Docker image targets GCR (`gcr.io/`).
- Cloud SQL connection is configured.
- The paths filter restricts triggers to `api/**` changes.

**Part B — GitHub API live run check (requires `GITHUB_TOKEN`)**

Uses the `gh` CLI to query the GitHub Actions API and confirms:

- There is at least one completed run of `Deploy API` on `main`.
- The most recent completed run has `conclusion == success`.
- The `deploy` job completed with `success`.
- All expected step names are present and all succeeded.
- The GCP auth, Docker build/push, and Cloud Run deploy steps individually
  all succeeded.

If `GITHUB_TOKEN` is not set or `gh` is not authenticated, Part B is skipped.

## Requirements

- Python 3.10+
- `pytest`
- `pyyaml`
- `gh` CLI (for Part B)
- `GITHUB_TOKEN` environment variable (for Part B)

## Install dependencies

```bash
pip install pytest pyyaml
```

Install `gh` CLI: https://cli.github.com/

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-86/test_mytube_86.py -v
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | Part B only | GitHub personal access token or Actions token with `actions:read` scope |

## Expected output (passing)

```
testing/tests/MYTUBE-86/test_mytube_86.py::TestDeployApiWorkflowStructure::test_workflow_file_exists PASSED
testing/tests/MYTUBE-86/test_mytube_86.py::TestDeployApiWorkflowStructure::test_workflow_name_is_deploy_api PASSED
testing/tests/MYTUBE-86/test_mytube_86.py::TestDeployApiWorkflowStructure::test_workflow_triggers_on_push_to_main PASSED
testing/tests/MYTUBE-86/test_mytube_86.py::TestDeployApiWorkflowStructure::test_workflow_has_deploy_job PASSED
testing/tests/MYTUBE-86/test_mytube_86.py::TestDeployApiWorkflowStructure::test_deploy_job_has_all_expected_steps PASSED
testing/tests/MYTUBE-86/test_mytube_86.py::TestDeployApiWorkflowStructure::test_gcp_auth_uses_secret PASSED
testing/tests/MYTUBE-86/test_mytube_86.py::TestDeployApiWorkflowStructure::test_deploy_step_uses_correct_service_name PASSED
testing/tests/MYTUBE-86/test_mytube_86.py::TestDeployApiWorkflowStructure::test_docker_image_references_gcr PASSED
testing/tests/MYTUBE-86/test_mytube_86.py::TestDeployApiWorkflowStructure::test_workflow_references_cloud_sql_connection PASSED
testing/tests/MYTUBE-86/test_mytube_86.py::TestDeployApiWorkflowStructure::test_paths_filter_includes_api_directory PASSED
testing/tests/MYTUBE-86/test_mytube_86.py::TestDeployApiWorkflowRuns::test_most_recent_run_exists PASSED
testing/tests/MYTUBE-86/test_mytube_86.py::TestDeployApiWorkflowRuns::test_most_recent_run_conclusion_is_success PASSED
testing/tests/MYTUBE-86/test_mytube_86.py::TestDeployApiWorkflowRuns::test_deploy_job_completed_with_success PASSED
testing/tests/MYTUBE-86/test_mytube_86.py::TestDeployApiWorkflowRuns::test_all_expected_steps_succeeded PASSED
testing/tests/MYTUBE-86/test_mytube_86.py::TestDeployApiWorkflowRuns::test_gcp_auth_step_succeeded PASSED
testing/tests/MYTUBE-86/test_mytube_86.py::TestDeployApiWorkflowRuns::test_docker_build_and_push_succeeded PASSED
testing/tests/MYTUBE-86/test_mytube_86.py::TestDeployApiWorkflowRuns::test_cloud_run_deploy_step_succeeded PASSED
testing/tests/MYTUBE-86/test_mytube_86.py::TestDeployApiWorkflowRuns::test_run_triggered_on_main_branch PASSED
18 passed
```
