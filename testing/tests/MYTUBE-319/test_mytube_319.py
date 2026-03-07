"""
MYTUBE-319: CI service account can access Eventarc triggers —
            project-level eventarc.viewer role is present.

Objective
---------
Verify that the CI service account has the necessary project-level permission
(``eventarc.triggers.list`` / ``eventarc.triggers.get``) to prevent
PERMISSION_DENIED errors when validating Eventarc configurations.

Test Steps
----------
1. Run ``gcloud eventarc triggers list --location <region> --project <project_id>``.
2. Verify the command exits with code 0 (permission is present even if the list
   is empty — PERMISSION_DENIED would be a non-zero exit).

Expected Result
---------------
The active credential can list Eventarc triggers, confirming that
``roles/eventarc.viewer`` (or an equivalent role) is bound to the CI
service account at the project level.

Why capability-based (not IAM-policy inspection)
-------------------------------------------------
Verifying the IAM binding directly via ``gcloud projects get-iam-policy``
requires ``resourcemanager.projects.getIamPolicy``, which is NOT included in
``roles/eventarc.viewer``.  A capability probe (attempt the actual Eventarc
operation) avoids this circular permission dependency and directly tests what
matters: can the service account access Eventarc resources?

Environment Variables
---------------------
- GCP_PROJECT_ID   GCP project ID (default: ``ai-native-478811``).
- GCP_REGION       GCP region (default: ``us-central1``).

Architecture Notes
------------------
- ``EventarcService.can_list_triggers`` issues ``gcloud eventarc triggers list``
  and returns (True, "") on success or (False, stderr) on failure.
- Credentials are picked up automatically by gcloud from the active
  configuration (``GOOGLE_APPLICATION_CREDENTIALS`` or ``gcloud auth``).
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.services.eventarc_service import EventarcService

# ---------------------------------------------------------------------------
# Config — read from environment, fall back to defaults
# ---------------------------------------------------------------------------

PROJECT_ID: str = os.environ.get("GCP_PROJECT_ID", "ai-native-478811")
REGION: str = os.environ.get("GCP_REGION", "us-central1")
CI_SA_EMAIL: str = os.environ.get(
    "CI_SA_EMAIL",
    "ai-teammate-gcloud@ai-native-478811.iam.gserviceaccount.com",
)
EXPECTED_ROLE: str = "roles/eventarc.viewer"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def eventarc_service() -> EventarcService:
    return EventarcService(project=PROJECT_ID, region=REGION)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCiSaEventarcViewerRole:
    """MYTUBE-319: CI SA must have roles/eventarc.viewer at the project level."""

    def test_ci_sa_can_list_eventarc_triggers(
        self,
        eventarc_service: EventarcService,
    ) -> None:
        """Verify the active credential can list Eventarc triggers.

        ``gcloud eventarc triggers list`` requires ``eventarc.triggers.list``,
        which is part of ``roles/eventarc.viewer``.  A successful call (exit 0)
        — even with an empty result — confirms the role is bound.  A
        PERMISSION_DENIED failure confirms the role is absent.

        To fix a failure, grant the required role:
            gcloud projects add-iam-policy-binding {PROJECT_ID} \\
              --member=serviceAccount:{CI_SA_EMAIL} \\
              --role={EXPECTED_ROLE}
        """
        can_list, stderr = eventarc_service.can_list_triggers()
        assert can_list, (
            f"CI service account '{CI_SA_EMAIL}' cannot list Eventarc triggers "
            f"in project '{PROJECT_ID}' (region '{REGION}').\n\n"
            f"gcloud error:\n  {stderr}\n\n"
            f"This means '{EXPECTED_ROLE}' (or an equivalent role granting "
            f"eventarc.triggers.list) is NOT bound to this service account.\n\n"
            "To grant the required role:\n"
            f"  gcloud projects add-iam-policy-binding {PROJECT_ID} \\\n"
            f"    --member=serviceAccount:{CI_SA_EMAIL} \\\n"
            f"    --role={EXPECTED_ROLE}"
        )
