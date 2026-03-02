# MYTUBE-87 — Deploy API workflow with invalid configuration

## Purpose

Verifies that the **Deploy API** GitHub Actions workflow (`deploy-api.yml`) is
configured to fail with descriptive error logs when deployment prerequisites are
missing or invalid.  The test uses static analysis of the workflow YAML so no
live GCP credentials are required.

## What is tested

- `GCP_SA_KEY` secret is referenced — missing/invalid key causes `google-github-actions/auth` to fail with a clear error.
- Required repository variables (`GCP_PROJECT_ID`, `GCP_REGION`, `CLOUD_SQL_CONNECTION_NAME`, `FIREBASE_PROJECT_ID`, `DB_NAME`) are all referenced.
- Required secrets (`GCP_DB_USER_SECRET`, `GCP_DB_PASSWORD_SECRET`) are wired via `--set-secrets`.
- Critical steps do **not** suppress exit codes (`|| true` or `continue-on-error: true`).
- Cleanup steps intentionally use `|| true` (documented).
- `Authenticate to GCP` step precedes all cloud operations.
- Workflow triggers only on `main` branch pushes with `api/**` path filter.

## Requirements

- Python 3.10+
- `pytest`
- `pyyaml`

## Install dependencies

```bash
pip install pytest pyyaml
```

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-87/test_mytube_87.py -v
```

## Environment variables

None required — this is a pure static-analysis test.

## Expected output (passing)

```
testing/tests/MYTUBE-87/test_mytube_87.py::TestDeployApiWorkflowFailsOnInvalidConfig::test_workflow_file_exists PASSED
testing/tests/MYTUBE-87/test_mytube_87.py::TestDeployApiWorkflowFailsOnInvalidConfig::test_gcp_sa_key_secret_is_referenced PASSED
testing/tests/MYTUBE-87/test_mytube_87.py::TestDeployApiWorkflowFailsOnInvalidConfig::test_db_user_secret_is_referenced PASSED
testing/tests/MYTUBE-87/test_mytube_87.py::TestDeployApiWorkflowFailsOnInvalidConfig::test_db_password_secret_is_referenced PASSED
testing/tests/MYTUBE-87/test_mytube_87.py::TestDeployApiWorkflowFailsOnInvalidConfig::test_all_required_secrets_referenced PASSED
testing/tests/MYTUBE-87/test_mytube_87.py::TestDeployApiWorkflowFailsOnInvalidConfig::test_all_required_vars_referenced PASSED
testing/tests/MYTUBE-87/test_mytube_87.py::TestDeployApiWorkflowFailsOnInvalidConfig::test_auth_step_present PASSED
testing/tests/MYTUBE-87/test_mytube_87.py::TestDeployApiWorkflowFailsOnInvalidConfig::test_auth_step_uses_gcp_auth_action PASSED
testing/tests/MYTUBE-87/test_mytube_87.py::TestDeployApiWorkflowFailsOnInvalidConfig::test_auth_step_receives_credentials_json PASSED
testing/tests/MYTUBE-87/test_mytube_87.py::TestDeployApiWorkflowFailsOnInvalidConfig::test_critical_steps_do_not_suppress_errors PASSED
testing/tests/MYTUBE-87/test_mytube_87.py::TestDeployApiWorkflowFailsOnInvalidConfig::test_cleanup_steps_use_or_true_intentionally PASSED
testing/tests/MYTUBE-87/test_mytube_87.py::TestDeployApiWorkflowFailsOnInvalidConfig::test_deploy_step_uses_set_secrets PASSED
testing/tests/MYTUBE-87/test_mytube_87.py::TestDeployApiWorkflowFailsOnInvalidConfig::test_deploy_step_sets_required_env_vars PASSED
testing/tests/MYTUBE-87/test_mytube_87.py::TestDeployApiWorkflowFailsOnInvalidConfig::test_auth_precedes_cloud_operations PASSED
testing/tests/MYTUBE-87/test_mytube_87.py::TestDeployApiWorkflowFailsOnInvalidConfig::test_workflow_triggers_on_main_branch_only PASSED
testing/tests/MYTUBE-87/test_mytube_87.py::TestDeployApiWorkflowFailsOnInvalidConfig::test_workflow_scoped_to_api_paths PASSED

16 passed in X.XXs
```
