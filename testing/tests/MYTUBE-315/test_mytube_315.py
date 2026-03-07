"""
MYTUBE-315: Verify Eventarc API status — eventarc.googleapis.com is enabled.

Objective:
    Ensure the Eventarc API is active in the GCP project to allow the
    event-driven pipeline to function.

Steps:
    1. Execute:
       gcloud services list --enabled --filter="name:eventarc.googleapis.com"
                            --project=<GCP_PROJECT_ID>
    2. Assert that ``eventarc.googleapis.com`` appears in the output.

Expected Result:
    The output confirms that ``eventarc.googleapis.com`` is enabled for the
    project.

Environment Variables:
    GCP_PROJECT_ID   GCP project ID (default: ``ai-native-478811``).
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcp_config import GcpConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SERVICE_NAME = "eventarc.googleapis.com"
DEFAULT_PROJECT = "ai-native-478811"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcp_project() -> str:
    """Return the GCP project ID from the environment or use the default."""
    return os.environ.get("GCP_PROJECT_ID", DEFAULT_PROJECT)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEventarcApiEnabled:
    """Verify that the Eventarc API is enabled in the GCP project."""

    def test_eventarc_api_is_enabled(self, gcp_project: str) -> None:
        """
        Run ``gcloud services list`` filtered to ``eventarc.googleapis.com``
        and assert the service appears in the output, confirming it is enabled.
        """
        result = subprocess.run(
            [
                "gcloud", "services", "list",
                "--enabled",
                f"--filter=name:{SERVICE_NAME}",
                f"--project={gcp_project}",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"gcloud services list exited with code {result.returncode}.\n"
            f"stderr: {result.stderr.strip()}"
        )

        assert SERVICE_NAME in result.stdout, (
            f"Expected '{SERVICE_NAME}' to appear in the output of "
            f"'gcloud services list --enabled' for project '{gcp_project}', "
            f"but it was not found.\n"
            f"stdout: {result.stdout.strip()}\n"
            f"stderr: {result.stderr.strip()}\n"
            f"This means the Eventarc API is NOT enabled for this project, "
            f"which will prevent the event-driven pipeline from functioning."
        )
