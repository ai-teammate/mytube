"""
MYTUBE-48: Provision raw uploads bucket — bucket is private and restricts
unauthorized access.

Verifies that the ``mytube-raw-uploads`` GCS bucket:
  1. Exists in the configured GCP project.
  2. Has Public Access Prevention set to 'enforced'.
  3. Returns HTTP 403 when an unauthenticated client tries to access an object
     via the bucket's public URL.

Prerequisites:
  - GCP_PROJECT_ID env var set to the target GCP project.
  - GOOGLE_APPLICATION_CREDENTIALS (or ADC) must be configured with at least
    ``storage.buckets.get`` and ``storage.buckets.getIamPolicy`` permissions
    for steps 1 and 2.
  - GCS_RAW_UPLOADS_BUCKET (optional) overrides the bucket name; defaults to
    ``mytube-raw-uploads``.

Step 3 (public URL check) does NOT require GCP credentials and always runs.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcs_config import GCSConfig
from testing.components.services.gcs_bucket_service import GCSBucketService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcs_config() -> GCSConfig:
    return GCSConfig()


@pytest.fixture(scope="module")
def storage_client(gcs_config: GCSConfig):
    """Create an authenticated google-cloud-storage Client.

    Skips only the authenticated tests if GCP credentials or project ID are
    not configured.  Step 3 (public URL check) is independent and always runs.
    """
    try:
        from google.cloud import storage as gcs_storage
        from google.auth.exceptions import DefaultCredentialsError
    except ImportError:
        pytest.skip("google-cloud-storage is not installed")

    if not gcs_config.project_id:
        pytest.skip(
            "GCP_PROJECT_ID is not set — skipping authenticated GCS tests. "
            "Set GCP_PROJECT_ID and GOOGLE_APPLICATION_CREDENTIALS to run steps 1 and 2."
        )

    try:
        client = gcs_storage.Client(project=gcs_config.project_id)
    except DefaultCredentialsError as exc:
        pytest.skip(
            f"GCP credentials not available (DefaultCredentialsError): {exc}. "
            "Configure GOOGLE_APPLICATION_CREDENTIALS or Application Default Credentials."
        )

    return client


@pytest.fixture(scope="module")
def bucket_service(gcs_config: GCSConfig, storage_client) -> GCSBucketService:
    return GCSBucketService(config=gcs_config, storage_client=storage_client)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRawUploadsBucketProvisioning:
    """mytube-raw-uploads must be provisioned as a private bucket."""

    def test_bucket_exists(self, bucket_service: GCSBucketService, gcs_config: GCSConfig):
        """Step 1 — the mytube-raw-uploads bucket must exist in the GCP project."""
        exists = bucket_service.bucket_exists()
        assert exists, (
            f"Bucket '{gcs_config.raw_uploads_bucket}' was not found in project "
            f"'{gcs_config.project_id}'. Ensure infra/setup.sh has been executed."
        )

    def test_public_access_prevention_enforced(
        self, bucket_service: GCSBucketService, gcs_config: GCSConfig
    ):
        """Step 2 — IAM policy must show Public Access Prevention = 'enforced'."""
        iam_info = bucket_service.get_iam_info()
        pap = iam_info.public_access_prevention

        assert pap == "enforced", (
            f"Expected Public Access Prevention to be 'enforced' on bucket "
            f"'{gcs_config.raw_uploads_bucket}', but got: '{pap}'. "
            "The bucket may have been created with --no-public-access-prevention."
        )

    def test_unauthorized_access_returns_403(self, gcs_config: GCSConfig):
        """Step 3 — unauthenticated HTTP GET on any object must return 403.

        This step does not require GCP credentials: it issues a plain HTTP
        request to the GCS storage XML API endpoint and verifies that access
        is denied with 403 Forbidden.
        """
        service = GCSBucketService(config=gcs_config, storage_client=None)
        result = service.attempt_public_access("probe.txt")
        assert result.http_status == 403, (
            f"Expected HTTP 403 (Forbidden) when accessing '{result.url}' without "
            f"authentication, but got HTTP {result.http_status}. "
            "The bucket may be publicly accessible, which is a security issue."
        )
