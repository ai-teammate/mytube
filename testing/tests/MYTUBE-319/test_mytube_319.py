"""
MYTUBE-319: CI service account describes Eventarc trigger —
            project-level eventarc.viewer role is present.

Objective
---------
Verify that the CI service account has the necessary project-level permission
(``eventarc.triggers.get``) to prevent PERMISSION_DENIED errors when validating
Eventarc configurations.

Test Steps
----------
1. Run ``gcloud projects get-iam-policy <project_id> --format="json"``.
2. Filter the output for the CI service account
   ``ai-teammate-gcloud@ai-native-478811.iam.gserviceaccount.com``.
3. Verify that the account is assigned ``roles/eventarc.viewer`` or a custom role
   containing the ``eventarc.triggers.get`` permission.

Expected Result
---------------
The IAM policy contains a binding for the CI service account with the required
Eventarc viewer role at the project level, allowing trigger description commands
to succeed.

Environment Variables
---------------------
- GCP_PROJECT_ID   GCP project ID (default: ``ai-native-478811``).
- CI_SA_EMAIL      CI service account email
                   (default: ``ai-teammate-gcloud@ai-native-478811.iam.gserviceaccount.com``).
- EXPECTED_ROLE    Expected IAM role (default: ``roles/eventarc.viewer``).

Architecture Notes
------------------
- ``GcpIamService.get_project_bindings`` is used to retrieve the project-level IAM policy.
- ``GcpIamService.member_has_role`` is used to check role membership.
- Credentials are picked up automatically by gcloud from the active configuration
  (``GOOGLE_APPLICATION_CREDENTIALS`` or ``gcloud auth``).
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcp_config import GcpConfig
from testing.components.gcp.gcp_iam_service import GcpIamService

# ---------------------------------------------------------------------------
# Config — read from environment, fall back to defaults
# ---------------------------------------------------------------------------

PROJECT_ID: str = os.environ.get("GCP_PROJECT_ID", "ai-native-478811")
CI_SA_EMAIL: str = os.environ.get(
    "CI_SA_EMAIL",
    "ai-teammate-gcloud@ai-native-478811.iam.gserviceaccount.com",
)
EXPECTED_ROLE: str = os.environ.get("EXPECTED_ROLE", "roles/eventarc.viewer")
CI_SA_MEMBER: str = f"serviceAccount:{CI_SA_EMAIL}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcp_config() -> GcpConfig:
    config = GcpConfig()
    config.project_id = PROJECT_ID
    return config


@pytest.fixture(scope="module")
def gcp_iam_service(gcp_config: GcpConfig) -> GcpIamService:
    return GcpIamService(config=gcp_config)


@pytest.fixture(scope="module")
def project_bindings(gcp_iam_service: GcpIamService) -> list[dict]:
    """Retrieve and cache the project-level IAM policy bindings."""
    return gcp_iam_service.get_project_bindings()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCiSaEventarcViewerRole:
    """MYTUBE-319: CI SA must have roles/eventarc.viewer at the project level."""

    def test_ci_sa_has_eventarc_viewer_role(
        self,
        gcp_iam_service: GcpIamService,
        project_bindings: list[dict],
    ) -> None:
        """Steps 1–3: Fetch project IAM policy and verify the CI SA has the required role.

        Failure here means the CI service account is missing ``roles/eventarc.viewer``
        (or an equivalent custom role), which will cause PERMISSION_DENIED when the
        CI pipeline attempts to describe Eventarc triggers.

        To fix, run:
            gcloud projects add-iam-policy-binding ai-native-478811 \\
              --member=serviceAccount:ai-teammate-gcloud@ai-native-478811.iam.gserviceaccount.com \\
              --role=roles/eventarc.viewer
        """
        has_role = gcp_iam_service.member_has_role(
            project_bindings, CI_SA_MEMBER, EXPECTED_ROLE
        )
        # Collect all roles the CI SA is bound to for diagnostic output on failure.
        sa_roles = [
            binding["role"]
            for binding in project_bindings
            if CI_SA_MEMBER in binding.get("members", [])
        ]
        assert has_role, (
            f"CI service account '{CI_SA_EMAIL}' does NOT have '{EXPECTED_ROLE}' "
            f"at the project level (project='{PROJECT_ID}').\n\n"
            f"Roles currently bound to this service account:\n"
            f"  {sa_roles if sa_roles else '(none found)'}\n\n"
            "To grant the required role:\n"
            f"  gcloud projects add-iam-policy-binding {PROJECT_ID} \\\n"
            f"    --member={CI_SA_MEMBER} \\\n"
            f"    --role={EXPECTED_ROLE}"
        )
