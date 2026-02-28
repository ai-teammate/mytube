"""
MYTUBE-49: Provision HLS output bucket with CDN — bucket is public and served
via Cloud CDN.

Verifies that the `mytube-hls-output` GCS bucket:
  1. Exists in GCS.
  2. Has public read access (allUsers roles/storage.objectViewer).
     NOTE: infra/setup.sh provisions CDN delivery via public GCS access —
     there is no separate GCP Cloud CDN load balancer infrastructure.
     This IAM binding IS the CDN-enablement step in the current infra.
  3. Serves objects via the CDN endpoint URL (CDN_BASE_URL env var).
     If CDN_BASE_URL is not set, the test skips with an explanatory message.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.services.gcs_service import GCSService
from testing.core.config.gcs_config import GCSConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcs_config() -> GCSConfig:
    return GCSConfig()


@pytest.fixture(scope="module")
def gcs_service(gcs_config: GCSConfig) -> GCSService:
    return GCSService(gcs_config)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHLSBucketProvisionedWithPublicAccess:
    """
    mytube-hls-output bucket must exist and be publicly accessible for
    CDN-based HLS delivery.
    """

    def test_hls_bucket_exists(self, gcs_service: GCSService, gcs_config: GCSConfig):
        """Step 1: The mytube-hls-output GCS bucket must exist."""
        assert gcs_service.bucket_exists(gcs_config.hls_bucket), (
            f"Bucket '{gcs_config.hls_bucket}' does not exist or is not accessible. "
            "Run infra/setup.sh to provision the bucket."
        )

    def test_hls_bucket_has_public_read_iam(self, gcs_service: GCSService, gcs_config: GCSConfig):
        """
        Step 2: allUsers must have roles/storage.objectViewer on the bucket.

        infra/setup.sh enables HLS delivery by granting this IAM binding —
        there is no separate GCP Cloud CDN load balancer in this project.
        This binding is the CDN-enablement configuration for the HLS bucket.
        """
        assert gcs_service.has_public_read_iam(gcs_config.hls_bucket), (
            f"Bucket '{gcs_config.hls_bucket}' does not grant allUsers "
            "roles/storage.objectViewer. This IAM binding is required for "
            "HLS delivery (see infra/setup.sh step 2)."
        )

    def test_object_served_via_cdn_url(self, gcs_service: GCSService, gcs_config: GCSConfig):
        """
        Step 3: A file uploaded to the bucket must be accessible via the
        Cloud CDN frontend URL (CDN_BASE_URL), confirming CDN delivery
        works end-to-end — not just direct GCS access.
        """
        if not gcs_config.cdn_base_url:
            pytest.skip(
                "CDN_BASE_URL is not set. Set it to the Cloud CDN frontend IP or CNAME "
                "(e.g. https://34.x.x.x or https://cdn.example.com) to verify CDN delivery."
            )

        object_name = gcs_service.upload_test_object(gcs_config.hls_bucket)
        try:
            response = gcs_service.fetch_object_via_cdn_url(object_name)
            assert response.status_code == 200, (
                f"Expected HTTP 200 from Cloud CDN URL, got {response.status_code}. "
                f"Object '{object_name}' is not reachable via CDN endpoint "
                f"'{gcs_config.cdn_base_url}'."
            )
            assert response.content == b"HLS test probe", (
                f"CDN response body mismatch. Expected b'HLS test probe', "
                f"got {response.content!r}"
            )
        finally:
            gcs_service.delete_object(gcs_config.hls_bucket, object_name)
