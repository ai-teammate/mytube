"""
MYTUBE-309: CI service account IAM policy audit — both objectCreator and
objectViewer roles present on raw bucket.

Objective
---------
Ensure the CI service account has the necessary permissions to both upload
test fixtures and allow the transcoder to read them, preventing authorization
regressions between write (MYTUBE-79) and read (MYTUBE-307) requirements.

Test Steps
----------
1. Execute: gcloud storage buckets get-iam-policy gs://mytube-raw-uploads --format="json"
2. Inspect the JSON output for the ``bindings`` section.
3. Verify that ``serviceAccount:ai-teammate-gcloud@ai-native-478811.iam.gserviceaccount.com``
   is bound to ``roles/storage.objectCreator``.
4. Verify that the same member is also bound to ``roles/storage.objectViewer``.

Expected Result
---------------
The IAM policy explicitly includes both roles for the CI service account,
ensuring it can perform all operations required by the test suite and the
transcoding pipeline.

Environment Variables
---------------------
GCP_PROJECT_ID  GCP project ID (default: ai-native-478811).
GCP_REGION      GCP region (default: us-central1).
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcp_config import GcpConfig
from testing.components.gcp.gcp_iam_service import GcpIamService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CI_SA_MEMBER = (
    "serviceAccount:ai-teammate-gcloud@ai-native-478811.iam.gserviceaccount.com"
)
_ROLE_CREATOR = "roles/storage.objectCreator"
_ROLE_VIEWER = "roles/storage.objectViewer"
_RAW_BUCKET = "mytube-raw-uploads"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcp_config() -> GcpConfig:
    cfg = GcpConfig()
    if not cfg.project_id:
        cfg.project_id = "ai-native-478811"
    return cfg


@pytest.fixture(scope="module")
def iam_service(gcp_config: GcpConfig) -> GcpIamService:
    return GcpIamService(config=gcp_config)


@pytest.fixture(scope="module")
def raw_bucket_bindings(iam_service: GcpIamService) -> list[dict]:
    """Retrieve IAM bindings for the raw uploads bucket via gcloud CLI."""
    try:
        bindings = iam_service.get_bucket_bindings(_RAW_BUCKET)
    except RuntimeError as exc:
        pytest.fail(
            f"Failed to retrieve IAM policy for gs://{_RAW_BUCKET}.\n"
            f"Ensure gcloud is authenticated (GOOGLE_APPLICATION_CREDENTIALS or ADC).\n"
            f"Error: {exc}"
        )
    return bindings


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCIServiceAccountIAMPolicyAudit:
    """MYTUBE-309: CI SA must have both objectCreator and objectViewer on raw bucket."""

    def test_ci_sa_has_object_creator_role(
        self, raw_bucket_bindings: list[dict], iam_service: GcpIamService
    ) -> None:
        """Step 3: CI service account must be bound to roles/storage.objectCreator."""
        has_role = iam_service.member_has_role(
            raw_bucket_bindings, _CI_SA_MEMBER, _ROLE_CREATOR
        )
        assert has_role, (
            f"CI service account '{_CI_SA_MEMBER}' does NOT have "
            f"'{_ROLE_CREATOR}' on gs://{_RAW_BUCKET}.\n"
            f"Current bindings: {raw_bucket_bindings}\n\n"
            "This means the CI service account cannot upload test fixtures, "
            "which will break MYTUBE-79 fixture setup."
        )

    def test_ci_sa_has_object_viewer_role(
        self, raw_bucket_bindings: list[dict], iam_service: GcpIamService
    ) -> None:
        """Step 4: CI service account must be bound to roles/storage.objectViewer."""
        has_role = iam_service.member_has_role(
            raw_bucket_bindings, _CI_SA_MEMBER, _ROLE_VIEWER
        )
        assert has_role, (
            f"CI service account '{_CI_SA_MEMBER}' does NOT have "
            f"'{_ROLE_VIEWER}' on gs://{_RAW_BUCKET}.\n"
            f"Current bindings: {raw_bucket_bindings}\n\n"
            "This means the transcoder cannot read uploaded fixtures from the "
            "raw bucket, which will break MYTUBE-307 read requirements."
        )

    def test_both_roles_present(
        self, raw_bucket_bindings: list[dict], iam_service: GcpIamService
    ) -> None:
        """Consolidated audit: CI SA must hold BOTH objectCreator and objectViewer."""
        required_roles = {_ROLE_CREATOR, _ROLE_VIEWER}
        found_roles = set(
            iam_service.member_has_any_role(
                raw_bucket_bindings, _CI_SA_MEMBER, required_roles
            )
        )
        missing = required_roles - found_roles
        assert not missing, (
            f"CI service account '{_CI_SA_MEMBER}' is missing the following "
            f"role(s) on gs://{_RAW_BUCKET}: {sorted(missing)}\n"
            f"Roles found: {sorted(found_roles)}\n"
            f"Full bindings: {raw_bucket_bindings}"
        )
