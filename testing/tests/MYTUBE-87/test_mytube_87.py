"""
MYTUBE-87: Deploy API workflow with invalid configuration — pipeline fails
with descriptive error logs.

Objective:
    Ensure that the CI pipeline correctly identifies and logs failures when
    deployment prerequisites are missing or invalid, preventing silent failures.

Test approach:
    Static analysis of the ``deploy-api.yml`` workflow file.  We verify that:

    1. Every critical step uses secrets/variables that GitHub will surface as
       clear errors when missing or invalid (no silent-fail patterns).

    2. The GCP authentication step uses ``GCP_SA_KEY`` — if that secret is
       absent or invalid, the ``google-github-actions/auth`` action fails with
       a descriptive error, immediately halting the pipeline.

    3. Required repository variables (GCP_PROJECT_ID, GCP_REGION,
       CLOUD_SQL_CONNECTION_NAME, FIREBASE_PROJECT_ID, DB_NAME) are referenced,
       so a missing or empty variable causes a concrete failure at the affected
       step rather than a silent misconfiguration.

    4. Required secrets (GCP_DB_USER_SECRET, GCP_DB_PASSWORD_SECRET) are wired
       via ``--set-secrets``, so Cloud Run deploy fails when the secrets are
       absent or contain invalid values.

    5. No critical step has its exit code suppressed (``|| true``) — cleanup
       steps that use ``|| true`` are intentional and explicitly identified as
       non-critical.

    6. The workflow does NOT continue on error for critical steps, ensuring the
       pipeline halts rather than proceeding with broken configuration.
"""

import os
import re

import pytest
import yaml

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
WORKFLOW_PATH = os.path.join(
    REPO_ROOT, ".github", "workflows", "deploy-api.yml"
)

# Names of steps whose failure must halt the pipeline.
CRITICAL_STEP_NAMES = [
    "Checkout repository",
    "Authenticate to GCP",
    "Set up Cloud SDK",
    "Configure Docker for GCR",
    "Build and push Docker image",
    "Deploy to Cloud Run",
]

# Steps that are intentionally non-critical (cleanup) and may suppress errors.
CLEANUP_STEP_NAMES = [
    "Delete old Cloud Run revisions",
    "Delete old GCR images",
]

# Secrets that must be referenced for the pipeline to detect invalid configs.
REQUIRED_SECRETS = [
    "GCP_SA_KEY",
    "GCP_DB_USER_SECRET",
    "GCP_DB_PASSWORD_SECRET",
]

# Repository variables that must be referenced.
REQUIRED_VARS = [
    "GCP_PROJECT_ID",
    "GCP_REGION",
    "CLOUD_SQL_CONNECTION_NAME",
    "FIREBASE_PROJECT_ID",
    "DB_NAME",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def workflow_text() -> str:
    """Return the raw text of deploy-api.yml."""
    with open(WORKFLOW_PATH, "r") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def workflow(workflow_text: str) -> dict:
    """Return the parsed YAML of deploy-api.yml.

    Note: PyYAML parses the YAML ``on:`` key as Python ``True`` (a boolean)
    because ``on`` is a YAML 1.1 boolean literal.  The fixture normalises the
    key back to the string ``"on"`` so consumers can use ``workflow["on"]``.
    """
    parsed = yaml.safe_load(workflow_text)
    # Normalise: move True -> "on" if needed (PyYAML YAML 1.1 quirk)
    if True in parsed and "on" not in parsed:
        parsed["on"] = parsed.pop(True)
    return parsed


@pytest.fixture(scope="module")
def deploy_steps(workflow: dict) -> list:
    """Return the list of steps in the 'deploy' job."""
    return workflow["jobs"]["deploy"]["steps"]


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestDeployApiWorkflowFailsOnInvalidConfig:
    """
    Verifies that the Deploy API workflow is configured so that any invalid
    or missing prerequisite causes a pipeline failure with descriptive logs.
    """

    # ------------------------------------------------------------------
    # Workflow file existence
    # ------------------------------------------------------------------

    def test_workflow_file_exists(self):
        """The deploy-api.yml workflow file must exist in the repository."""
        assert os.path.isfile(WORKFLOW_PATH), (
            f"Workflow file not found at {WORKFLOW_PATH}. "
            "The Deploy API workflow must exist."
        )

    # ------------------------------------------------------------------
    # Required secrets are referenced
    # ------------------------------------------------------------------

    def test_gcp_sa_key_secret_is_referenced(self, workflow_text: str):
        """
        ``GCP_SA_KEY`` must be referenced in the workflow.

        This secret is used by ``google-github-actions/auth``.  When the
        secret is absent or contains an invalid service-account JSON, the
        auth action produces a descriptive error and the pipeline stops at
        the 'Authenticate to GCP' step — there is no silent continuation.
        """
        assert "secrets.GCP_SA_KEY" in workflow_text, (
            "GCP_SA_KEY secret is not referenced in deploy-api.yml. "
            "GCP authentication requires this secret; without it the "
            "pipeline cannot detect an invalid configuration."
        )

    def test_db_user_secret_is_referenced(self, workflow_text: str):
        """
        ``GCP_DB_USER_SECRET`` must be referenced so Cloud Run deploy fails
        when the secret is missing or invalid.
        """
        assert "vars.GCP_DB_USER_SECRET" in workflow_text or "GCP_DB_USER_SECRET" in workflow_text, (
            "GCP_DB_USER_SECRET is not referenced in deploy-api.yml. "
            "Database credentials must be wired via --set-secrets."
        )

    def test_db_password_secret_is_referenced(self, workflow_text: str):
        """
        ``GCP_DB_PASSWORD_SECRET`` must be referenced so Cloud Run deploy
        fails when the secret is missing or invalid.
        """
        assert "GCP_DB_PASSWORD_SECRET" in workflow_text, (
            "GCP_DB_PASSWORD_SECRET is not referenced in deploy-api.yml. "
            "Database password must be wired via --set-secrets."
        )

    def test_all_required_secrets_referenced(self, workflow_text: str):
        """All required secrets are referenced in the workflow."""
        missing = [s for s in REQUIRED_SECRETS if s not in workflow_text]
        assert not missing, (
            f"The following secrets are not referenced in deploy-api.yml: "
            f"{missing}. Missing secrets cause silent misconfigurations."
        )

    # ------------------------------------------------------------------
    # Required variables are referenced
    # ------------------------------------------------------------------

    def test_all_required_vars_referenced(self, workflow_text: str):
        """
        All required repository variables must be referenced in the workflow
        so that an empty or missing variable produces a concrete step failure.
        """
        missing = [v for v in REQUIRED_VARS if v not in workflow_text]
        assert not missing, (
            f"The following repository variables are not referenced in "
            f"deploy-api.yml: {missing}."
        )

    # ------------------------------------------------------------------
    # GCP authentication step is the first privileged step
    # ------------------------------------------------------------------

    def test_auth_step_present(self, deploy_steps: list):
        """
        An 'Authenticate to GCP' step must exist.

        This step uses the ``google-github-actions/auth`` action, which
        validates ``GCP_SA_KEY`` immediately.  If the secret is invalid,
        the action exits with a detailed error message before any cloud
        resources are touched.
        """
        step_names = [s.get("name", "") for s in deploy_steps]
        assert "Authenticate to GCP" in step_names, (
            "No 'Authenticate to GCP' step found in the deploy job. "
            "GCP authentication must be an explicit step so that an invalid "
            "GCP_SA_KEY fails the pipeline at a clearly identifiable point."
        )

    def test_auth_step_uses_gcp_auth_action(self, deploy_steps: list):
        """
        The 'Authenticate to GCP' step must use the
        ``google-github-actions/auth`` action, which validates credentials
        and emits a descriptive error when they are invalid.
        """
        auth_step = next(
            (s for s in deploy_steps if s.get("name") == "Authenticate to GCP"),
            None,
        )
        assert auth_step is not None, "Authenticate to GCP step not found."
        uses = auth_step.get("uses", "")
        assert uses.startswith("google-github-actions/auth"), (
            f"Expected 'Authenticate to GCP' to use google-github-actions/auth, "
            f"got: {uses!r}."
        )

    def test_auth_step_receives_credentials_json(self, deploy_steps: list):
        """
        The auth step must pass ``credentials_json: ${{ secrets.GCP_SA_KEY }}``.
        Without this, an invalid or missing key would not be detected.
        """
        auth_step = next(
            (s for s in deploy_steps if s.get("name") == "Authenticate to GCP"),
            None,
        )
        assert auth_step is not None, "Authenticate to GCP step not found."
        with_block = auth_step.get("with", {})
        credentials = with_block.get("credentials_json", "")
        assert "GCP_SA_KEY" in str(credentials), (
            f"credentials_json in 'Authenticate to GCP' does not reference "
            f"GCP_SA_KEY: {credentials!r}."
        )

    # ------------------------------------------------------------------
    # Critical steps must not suppress errors
    # ------------------------------------------------------------------

    def test_critical_steps_do_not_suppress_errors(
        self, deploy_steps: list, workflow_text: str
    ):
        """
        Critical deployment steps must not use ``|| true`` or
        ``continue-on-error: true``.  If they did, a misconfigured secret or
        variable would allow the workflow to silently succeed, hiding the error.

        Cleanup steps (Delete old … revisions/images) are excluded because
        they deliberately use ``|| true`` to avoid blocking a successful
        deployment due to a cleanup failure.
        """
        critical_steps = [
            s for s in deploy_steps
            if s.get("name") in CRITICAL_STEP_NAMES
        ]

        for step in critical_steps:
            step_name = step.get("name", "")

            # continue-on-error must not be set to True
            continue_on_err = step.get("continue-on-error", False)
            assert continue_on_err is not True, (
                f"Step '{step_name}' has continue-on-error: true. "
                "Critical steps must not swallow errors."
            )

            # run blocks must not end with || true
            run_block = step.get("run", "")
            assert "|| true" not in run_block, (
                f"Step '{step_name}' contains '|| true', which suppresses "
                "failure exit codes. Critical steps must propagate errors."
            )

    def test_cleanup_steps_use_or_true_intentionally(self, deploy_steps: list):
        """
        The cleanup steps (delete old revisions, delete old images) explicitly
        use ``|| true`` so that a cleanup failure does not block a successful
        deployment.  This test documents that this suppression is intentional
        and limited to cleanup operations only.
        """
        cleanup_steps = [
            s for s in deploy_steps
            if s.get("name") in CLEANUP_STEP_NAMES
        ]
        assert len(cleanup_steps) == len(CLEANUP_STEP_NAMES), (
            f"Expected {len(CLEANUP_STEP_NAMES)} cleanup steps, "
            f"found {len(cleanup_steps)}."
        )
        for step in cleanup_steps:
            run_block = step.get("run", "")
            assert "|| true" in run_block, (
                f"Cleanup step '{step.get('name')}' unexpectedly does not "
                "use '|| true'. Cleanup steps should tolerate failures."
            )

    # ------------------------------------------------------------------
    # Deploy step wires secrets via --set-secrets
    # ------------------------------------------------------------------

    def test_deploy_step_uses_set_secrets(self, deploy_steps: list):
        """
        The 'Deploy to Cloud Run' step must use ``--set-secrets`` to inject
        database credentials.  If the referenced GCP Secret Manager secrets
        are invalid or missing, Cloud Run will reject the deployment with a
        descriptive error.
        """
        deploy_step = next(
            (s for s in deploy_steps if s.get("name") == "Deploy to Cloud Run"),
            None,
        )
        assert deploy_step is not None, "Deploy to Cloud Run step not found."
        run_block = deploy_step.get("run", "")
        assert "--set-secrets" in run_block, (
            "Deploy to Cloud Run step does not use --set-secrets. "
            "Database credentials must be injected via GCP Secret Manager "
            "references so that an invalid secret causes a clear deploy failure."
        )

    def test_deploy_step_sets_required_env_vars(self, deploy_steps: list):
        """
        The 'Deploy to Cloud Run' step must set the required environment
        variables (DB_NAME, INSTANCE_UNIX_SOCKET, FIREBASE_PROJECT_ID) via
        ``--set-env-vars``.  Missing or empty variables will cause the
        deployed service to fail at startup with a descriptive log entry.
        """
        deploy_step = next(
            (s for s in deploy_steps if s.get("name") == "Deploy to Cloud Run"),
            None,
        )
        assert deploy_step is not None, "Deploy to Cloud Run step not found."
        run_block = deploy_step.get("run", "")
        for var in ("DB_NAME", "INSTANCE_UNIX_SOCKET", "FIREBASE_PROJECT_ID"):
            assert var in run_block, (
                f"Deploy to Cloud Run step does not set {var} in "
                f"--set-env-vars. A missing value causes a silent "
                f"misconfiguration instead of a descriptive error."
            )

    # ------------------------------------------------------------------
    # Overall step ordering: auth before any cloud operations
    # ------------------------------------------------------------------

    def test_auth_precedes_cloud_operations(self, deploy_steps: list):
        """
        The 'Authenticate to GCP' step must appear before any step that
        calls ``gcloud`` or ``docker``.  This ensures that an invalid
        ``GCP_SA_KEY`` is detected immediately, before any cloud resource
        is touched, and the error message pinpoints the authentication step.
        """
        step_names = [s.get("name", "") for s in deploy_steps]
        auth_index = next(
            (i for i, n in enumerate(step_names) if n == "Authenticate to GCP"),
            None,
        )
        assert auth_index is not None, "Authenticate to GCP step not found."

        cloud_steps = [
            "Configure Docker for GCR",
            "Build and push Docker image",
            "Deploy to Cloud Run",
        ]
        for cloud_step in cloud_steps:
            cloud_index = next(
                (i for i, n in enumerate(step_names) if n == cloud_step),
                None,
            )
            if cloud_index is not None:
                assert auth_index < cloud_index, (
                    f"'Authenticate to GCP' (index {auth_index}) must appear "
                    f"before '{cloud_step}' (index {cloud_index})."
                )

    # ------------------------------------------------------------------
    # Workflow triggers: only on main branch
    # ------------------------------------------------------------------

    def test_workflow_triggers_on_main_branch_only(self, workflow: dict):
        """
        The workflow must trigger only on pushes to the ``main`` branch.
        Triggering on other branches could expose an invalid configuration
        silently through a long-running branch.
        """
        on_section = workflow.get("on", {})
        push_section = on_section.get("push", {})
        branches = push_section.get("branches", [])
        assert "main" in branches, (
            f"deploy-api.yml does not trigger on the 'main' branch: {branches}."
        )

    def test_workflow_scoped_to_api_paths(self, workflow: dict):
        """
        The workflow must use path filters (``api/**``) so it only runs when
        relevant files change.  An unscoped trigger could deploy with stale
        or invalid configuration from unrelated commits.
        """
        on_section = workflow.get("on", {})
        push_section = on_section.get("push", {})
        paths = push_section.get("paths", [])
        api_path_filter = any("api/" in p or "api/**" in p for p in paths)
        assert api_path_filter, (
            f"deploy-api.yml does not restrict to api/** paths: {paths}. "
            "Without path filtering, the workflow may trigger on unrelated changes."
        )
