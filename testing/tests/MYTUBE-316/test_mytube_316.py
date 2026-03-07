"""
MYTUBE-316: Audit Cloud Run services — mytube-transcoder-trigger service is deployed.

Objective
---------
Verify that the ``mytube-transcoder-trigger`` Cloud Run service is present and
has a 'Ready' status. The service is the critical link between GCS events and
Cloud Run Job execution.

Steps
-----
1. Run: gcloud run services list --filter="SERVICE:mytube-transcoder-trigger"
        --region=us-central1
2. Assert that the output contains exactly one entry for
   ``mytube-transcoder-trigger``.
3. Describe the service and assert that the Ready condition is True.

Expected Result
---------------
``mytube-transcoder-trigger`` is listed and its Ready status is True.

Prerequisites
-------------
- GCP_PROJECT_ID env var (default: ai-native-478811).
- ``gcloud`` CLI authenticated with at least ``run.services.list`` and
  ``run.services.get`` permissions.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcp_config import GcpConfig

SERVICE_NAME = "mytube-transcoder-trigger"
REGION = "us-central1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def gcp_config() -> GcpConfig:
    config = GcpConfig()
    if not config.project_id:
        pytest.skip(
            "GCP_PROJECT_ID is not set — skipping Cloud Run audit test. "
            "Set GCP_PROJECT_ID and ensure gcloud is authenticated."
        )
    return config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_gcloud(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["gcloud", *args], capture_output=True, text=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTranscoderTriggerServiceDeployed:
    """mytube-transcoder-trigger must be present and Ready in Cloud Run."""

    def test_service_appears_in_list(self, gcp_config: GcpConfig):
        """Step 1 — gcloud run services list must include mytube-transcoder-trigger.

        Runs the exact command from the test case spec:
          gcloud run services list --filter="SERVICE:mytube-transcoder-trigger"
          --region=us-central1
        and asserts that the service name appears in the output.
        """
        result = _run_gcloud(
            "run", "services", "list",
            f"--filter=SERVICE:{SERVICE_NAME}",
            f"--region={REGION}",
            "--project", gcp_config.project_id,
        )

        assert result.returncode == 0, (
            f"'gcloud run services list' exited with code {result.returncode}.\n"
            f"stderr:\n{result.stderr.strip()}"
        )

        output = result.stdout + result.stderr
        assert SERVICE_NAME in output, (
            f"Service '{SERVICE_NAME}' was NOT found in the output of "
            f"'gcloud run services list --filter=SERVICE:{SERVICE_NAME} "
            f"--region={REGION}'.\n"
            f"Full output:\n{output.strip()}\n\n"
            "This means the service is either not deployed or the filter "
            "returned no results — the transcoder trigger is missing from "
            "Cloud Run."
        )

    def test_service_is_ready(self, gcp_config: GcpConfig):
        """Step 2 — the service's Ready condition must be True.

        Describes the service in JSON and inspects the Ready condition in
        status.conditions to confirm 'status: True'.
        """
        result = _run_gcloud(
            "run", "services", "describe", SERVICE_NAME,
            f"--region={REGION}",
            "--project", gcp_config.project_id,
            "--format=json",
        )

        assert result.returncode == 0, (
            f"'gcloud run services describe {SERVICE_NAME}' failed with "
            f"exit code {result.returncode}.\n"
            f"stderr:\n{result.stderr.strip()}\n\n"
            "The service may not exist in the specified region/project."
        )

        service = json.loads(result.stdout)
        conditions = (
            service.get("status", {}).get("conditions", [])
        )

        ready_condition = next(
            (c for c in conditions if c.get("type") == "Ready"),
            None,
        )

        assert ready_condition is not None, (
            f"No 'Ready' condition found in the status of service "
            f"'{SERVICE_NAME}' in region '{REGION}'.\n"
            f"Conditions present: {[c.get('type') for c in conditions]}"
        )

        assert ready_condition.get("status") == "True", (
            f"Service '{SERVICE_NAME}' exists but is NOT ready.\n"
            f"Ready condition status: {ready_condition.get('status')!r}\n"
            f"Full Ready condition: {ready_condition}\n\n"
            "The service is deployed but unhealthy — check Cloud Run logs "
            "for startup errors."
        )
