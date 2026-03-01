"""
MYTUBE-51: Verify Cloud Run IAM permissions — Service Account has restricted
read/write access.

Verifies that the Service Account used by the mytube-transcoder Cloud Run Job
has the minimal required IAM permissions:
 - roles/storage.objectViewer  on gs://mytube-raw-uploads
 - roles/storage.objectCreator on gs://mytube-hls-output

And no broader administrative roles on the buckets beyond what is required.

Prerequisites:
 - gcloud CLI authenticated with a principal that can read IAM policies
 - GCP_PROJECT_ID environment variable set

Environment variables:
 - GCP_PROJECT_ID: GCP project ID (required)
 - GCP_REGION: GCP region (default: us-central1)
 - GCP_RAW_BUCKET: raw uploads bucket name (default: mytube-raw-uploads)
 - GCP_HLS_BUCKET: HLS output bucket name (default: mytube-hls-output)
 - GCP_TRANSCODER_JOB: Cloud Run Job name (default: mytube-transcoder)
 - GCP_TRANSCODER_SA: Service Account short name (default: mytube-transcoder)
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcp_config import GcpConfig
from testing.components.gcp.gcp_iam_service import GcpIamService


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_RAW_ROLE = "roles/storage.objectViewer"
REQUIRED_HLS_ROLE = "roles/storage.objectCreator"

OVERLY_BROAD_ROLES = {
    "roles/storage.admin",
    "roles/storage.objectAdmin",
    "roles/editor",
    "roles/owner",
    "roles/storage.legacyBucketOwner",
    "roles/storage.legacyBucketWriter",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcp_config() -> GcpConfig:
    config = GcpConfig()
    if not config.project_id:
        pytest.skip("GCP_PROJECT_ID environment variable is not set — skipping infrastructure test")
    return config


@pytest.fixture(scope="module")
def gcp_iam(gcp_config: GcpConfig) -> GcpIamService:
    return GcpIamService(gcp_config)


@pytest.fixture(scope="module")
def service_account_email(gcp_iam: GcpIamService, gcp_config: GcpConfig) -> str:
    """Retrieve and return the SA email from the Cloud Run Job definition."""
    return gcp_iam.get_cloud_run_job_sa(gcp_config.transcoder_job)


@pytest.fixture(scope="module")
def sa_member(service_account_email: str) -> str:
    return f"serviceAccount:{service_account_email}"


@pytest.fixture(scope="module")
def raw_bucket_bindings(gcp_iam: GcpIamService, gcp_config: GcpConfig) -> list[dict]:
    return gcp_iam.get_bucket_bindings(gcp_config.raw_bucket)


@pytest.fixture(scope="module")
def hls_bucket_bindings(gcp_iam: GcpIamService, gcp_config: GcpConfig) -> list[dict]:
    return gcp_iam.get_bucket_bindings(gcp_config.hls_bucket)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCloudRunJobServiceAccount:
    """Step 1 — Verify the SA assigned to the mytube-transcoder Cloud Run Job."""

    def test_service_account_is_mytube_transcoder(
        self, service_account_email: str, gcp_config: GcpConfig
    ):
        """The Cloud Run Job must use the mytube-transcoder service account."""
        expected_email = (
            f"{gcp_config.transcoder_sa}@{gcp_config.project_id}.iam.gserviceaccount.com"
        )
        assert service_account_email == expected_email, (
            f"Expected service account '{expected_email}', "
            f"but Cloud Run Job uses '{service_account_email}'"
        )


class TestRawBucketPermissions:
    """Step 2 — Verify objectViewer permission on the raw uploads bucket."""

    def test_sa_has_object_viewer_on_raw_bucket(
        self, raw_bucket_bindings: list[dict], sa_member: str, gcp_iam: GcpIamService,
        gcp_config: GcpConfig
    ):
        """SA must have roles/storage.objectViewer on the raw uploads bucket."""
        has_role = gcp_iam.member_has_role(raw_bucket_bindings, sa_member, REQUIRED_RAW_ROLE)
        assert has_role, (
            f"Expected '{sa_member}' to have '{REQUIRED_RAW_ROLE}' "
            f"on gs://{gcp_config.raw_bucket}, but the binding was not found.\n"
            f"Current bindings: {raw_bucket_bindings}"
        )

    def test_sa_has_no_overly_broad_roles_on_raw_bucket(
        self, raw_bucket_bindings: list[dict], sa_member: str, gcp_iam: GcpIamService,
        gcp_config: GcpConfig
    ):
        """SA must NOT have administrative/write roles on the raw uploads bucket."""
        extra_roles = gcp_iam.member_has_any_role(raw_bucket_bindings, sa_member, OVERLY_BROAD_ROLES)
        assert not extra_roles, (
            f"SA '{sa_member}' has unexpected broad roles on gs://{gcp_config.raw_bucket}: "
            f"{extra_roles}. Only '{REQUIRED_RAW_ROLE}' should be granted."
        )


class TestHlsBucketPermissions:
    """Step 3 — Verify objectCreator permission on the HLS output bucket."""

    def test_sa_has_object_creator_on_hls_bucket(
        self, hls_bucket_bindings: list[dict], sa_member: str, gcp_iam: GcpIamService,
        gcp_config: GcpConfig
    ):
        """SA must have roles/storage.objectCreator on the HLS output bucket."""
        has_role = gcp_iam.member_has_role(hls_bucket_bindings, sa_member, REQUIRED_HLS_ROLE)
        assert has_role, (
            f"Expected '{sa_member}' to have '{REQUIRED_HLS_ROLE}' "
            f"on gs://{gcp_config.hls_bucket}, but the binding was not found.\n"
            f"Current bindings: {hls_bucket_bindings}"
        )

    def test_sa_has_no_overly_broad_roles_on_hls_bucket(
        self, hls_bucket_bindings: list[dict], sa_member: str, gcp_iam: GcpIamService,
        gcp_config: GcpConfig
    ):
        """SA must NOT have administrative roles on the HLS output bucket."""
        extra_roles = gcp_iam.member_has_any_role(hls_bucket_bindings, sa_member, OVERLY_BROAD_ROLES)
        assert not extra_roles, (
            f"SA '{sa_member}' has unexpected broad roles on gs://{gcp_config.hls_bucket}: "
            f"{extra_roles}. Only '{REQUIRED_HLS_ROLE}' should be granted."
        )
