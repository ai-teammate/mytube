"""
MYTUBE-302: Access to bucket via Signed URL — access granted despite Public Access Prevention.

Objective
---------
Verify that Public Access Prevention does not block time-limited access provided
via GCS Signed URLs as intended by security policy.

Preconditions
-------------
A private object exists in the ``mytube-raw-uploads`` bucket.

Test Steps
----------
1. Generate a GCS Signed URL for an object in the bucket using a valid service
   account key (V4 signature, 15-minute expiry).
2. Perform an HTTP GET request to the Signed URL from an unauthenticated client
   (no Authorization header, no GCP credentials).

Expected Result
---------------
The object is successfully retrieved (HTTP 200 OK).

Environment Variables
---------------------
- GOOGLE_APPLICATION_CREDENTIALS : Path to the service account JSON key used for
  signing. The service account MUST have ``storage.objects.get`` on the bucket.
  Defaults to ``gha-creds-c230da37cfc4bcbe.json`` at the repository root.
- GCS_RAW_UPLOADS_BUCKET          : Overrides the bucket name
  (default: ``mytube-raw-uploads``).
- GCP_PROJECT_ID                  : GCP project ID (default: ``ai-native-478811``).

Architecture Notes
------------------
- Uses ``GCSBucketService`` for all GCS SDK interactions (upload, delete,
  signed-URL generation, and unauthenticated HTTP fetch).
- A unique test object is uploaded as part of the test and deleted on teardown,
  so the precondition is always satisfied without relying on pre-existing objects.
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcs_config import GCSConfig
from testing.components.services.gcs_bucket_service import GCSBucketService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_CREDS = os.path.join(_REPO_ROOT, "gha-creds-c230da37cfc4bcbe.json")

CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", _DEFAULT_CREDS)
SIGNED_URL_EXPIRY_MINUTES = 15


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcs_config() -> GCSConfig:
    config = GCSConfig()
    if not config.project_id:
        config.project_id = "ai-native-478811"
    return config


@pytest.fixture(scope="module")
def sa_credentials():
    """Load service-account credentials used for signing URLs.

    Skips the test module if the credentials file is absent or the
    google-cloud-storage package is not installed.
    """
    try:
        from google.oauth2 import service_account as sa
    except ImportError:
        pytest.skip("google-auth is not installed — cannot sign URLs.")

    if not os.path.isfile(CREDENTIALS_PATH):
        pytest.skip(
            f"Service account key not found at {CREDENTIALS_PATH!r}. "
            "Set GOOGLE_APPLICATION_CREDENTIALS to a key file with "
            "storage.objects.get permission on the bucket."
        )

    creds = sa.Credentials.from_service_account_file(CREDENTIALS_PATH)
    return creds


@pytest.fixture(scope="module")
def storage_client(sa_credentials, gcs_config):
    """Authenticated GCS client used by GCSBucketService."""
    try:
        from google.cloud import storage as gcs_storage
    except ImportError:
        pytest.skip("google-cloud-storage is not installed.")

    return gcs_storage.Client(
        project=gcs_config.project_id,
        credentials=sa_credentials,
    )


@pytest.fixture(scope="module")
def gcs_bucket_service(storage_client, gcs_config) -> GCSBucketService:
    """Component that encapsulates all GCS interactions for this test."""
    return GCSBucketService(config=gcs_config, storage_client=storage_client)


@pytest.fixture(scope="module")
def test_object(gcs_bucket_service: GCSBucketService):
    """Upload a unique test object and yield its name; delete it on teardown."""
    object_name = f"test-signed-url-probe-{uuid.uuid4()}.txt"

    gcs_bucket_service.upload_object(
        object_name,
        b"MYTUBE-302 signed-URL probe content",
        content_type="text/plain",
    )

    yield object_name

    gcs_bucket_service.delete_object(object_name)


@pytest.fixture(scope="module")
def signed_url(gcs_bucket_service: GCSBucketService, sa_credentials, test_object) -> str:
    """Generate a V4 signed URL for the test object using the service account key."""
    return gcs_bucket_service.generate_signed_url(
        test_object,
        sa_credentials,
        expiry_minutes=SIGNED_URL_EXPIRY_MINUTES,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSignedUrlBypassesPAP:
    """MYTUBE-302: Signed URL access succeeds even when PAP is enforced."""

    def test_signed_url_returns_200(self, gcs_bucket_service: GCSBucketService, signed_url: str, test_object: str) -> None:
        """Step 2: HTTP GET to the Signed URL from an unauthenticated client
        must return HTTP 200 OK.

        The request is sent with NO Authorization header and NO GCP credentials,
        simulating an external unauthenticated client.  If PAP incorrectly blocks
        Signed-URL access, GCS will return HTTP 403 instead of 200.
        """
        result = gcs_bucket_service.fetch_signed_url(signed_url)
        assert result.http_status == 200, (
            f"Expected HTTP 200 OK from Signed URL for object '{test_object}', "
            f"but got HTTP {result.http_status}.\n"
            f"Response body: {result.error_message[:500]}\n\n"
            "This may indicate that:\n"
            "  1. The signing service account lacks storage.objects.get on the "
            "bucket, causing GCS to deny access via the signed URL.\n"
            "  2. Public Access Prevention is incorrectly blocking Signed URL "
            "requests (which should NOT happen — PAP targets anonymous/ACL access, "
            "not Signed URLs).\n"
            "  3. The signed URL expired before the GET request was issued."
        )

    def test_signed_url_response_body_contains_probe_content(
        self, gcs_bucket_service: GCSBucketService, signed_url: str, test_object: str
    ) -> None:
        """Verify the response body matches the uploaded probe content.

        Confirms that the correct object was retrieved, not a redirect or
        error document that happened to return 200.
        """
        result = gcs_bucket_service.fetch_signed_url(signed_url)
        if result.http_status != 200:
            pytest.skip(
                f"Skipping body check — signed URL returned HTTP {result.http_status}."
            )
        assert b"MYTUBE-302 signed-URL probe content" in result.content, (
            f"Expected the response body to contain the probe content, "
            f"but got: {result.content[:200]!r}"
        )
