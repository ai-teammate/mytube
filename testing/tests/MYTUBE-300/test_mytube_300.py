"""
MYTUBE-300: Authorized service account request — access to bucket objects granted.

Objective
---------
Verify that authorized service accounts can successfully access objects in the
``mytube-raw-uploads`` bucket while Public Access Prevention is enabled.

Preconditions
-------------
A service account with ``roles/storage.objectViewer`` is configured for the bucket.

Test Steps
----------
1. Upload a test file to the ``mytube-raw-uploads`` bucket using admin credentials.
2. Authenticate as the authorized service account.
3. Attempt to download the test file using the GCS API.

Expected Result
---------------
The file is successfully downloaded (HTTP 200 OK equivalent — download succeeds
without exception and returns the expected bytes).

Architecture
------------
- GCSService (testing/components/services/gcs_service.py) for upload, download,
  and cleanup operations.
- GCSConfig (testing/core/config/gcs_config.py) for bucket name and project ID.
- google-cloud-storage Python client authenticated via GOOGLE_APPLICATION_CREDENTIALS.

Environment Variables
---------------------
GOOGLE_APPLICATION_CREDENTIALS   Path to the service account JSON key file.
                                  The SA must have at least storage.objects.create
                                  (for upload) and storage.objects.get (for download).
GCP_PROJECT_ID                    GCP project ID.
GCS_RAW_UPLOADS_BUCKET            Override bucket name (default: mytube-raw-uploads).
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcs_config import GCSConfig
from testing.components.services.gcs_service import GCSService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TEST_CONTENT = b"MYTUBE-300 authorized service account probe"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcs_config() -> GCSConfig:
    """Return a GCSConfig loaded from environment variables."""
    return GCSConfig()


@pytest.fixture(scope="module")
def storage_client(gcs_config: GCSConfig):
    """Create an authenticated google-cloud-storage Client.

    Skips the entire module if GCP credentials or project ID are not configured.
    """
    try:
        from google.cloud import storage as gcs_storage
        from google.auth.exceptions import DefaultCredentialsError
    except ImportError:
        pytest.skip("google-cloud-storage is not installed")

    if not gcs_config.project_id:
        pytest.skip(
            "GCP_PROJECT_ID is not set — skipping MYTUBE-300 authenticated GCS test. "
            "Set GCP_PROJECT_ID and GOOGLE_APPLICATION_CREDENTIALS to run this test."
        )

    try:
        client = gcs_storage.Client(project=gcs_config.project_id)
    except Exception as exc:
        pytest.skip(
            f"GCP credentials not available: {exc}. "
            "Configure GOOGLE_APPLICATION_CREDENTIALS or Application Default Credentials."
        )

    return client


@pytest.fixture(scope="module")
def gcs_service(gcs_config: GCSConfig, storage_client) -> GCSService:
    """Return a GCSService backed by the authenticated storage client."""
    return GCSService(config=gcs_config, storage_client=storage_client)


@pytest.fixture(scope="module")
def uploaded_object(gcs_service: GCSService, gcs_config: GCSConfig) -> str:
    """Upload a test object (Step 1) and yield its name; delete it on teardown."""
    object_name = gcs_service.upload_test_object(
        bucket_name=gcs_config.raw_uploads_bucket,
        content=_TEST_CONTENT,
    )
    yield object_name
    # Teardown: remove the test object from the bucket.
    try:
        gcs_service.delete_object(gcs_config.raw_uploads_bucket, object_name)
    except Exception:
        pass  # best-effort cleanup


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuthorizedServiceAccountAccess:
    """MYTUBE-300: Authorized SA must be able to download objects from
    mytube-raw-uploads even with Public Access Prevention enforced."""

    def test_step1_upload_succeeds(
        self,
        uploaded_object: str,
        gcs_service: GCSService,
        gcs_config: GCSConfig,
    ) -> None:
        """Step 1 — upload a test file using admin credentials.

        Verifies that the object was created in the bucket and is accessible
        to the authenticated client.
        """
        assert uploaded_object, (
            "Step 1 failed: upload_test_object returned an empty object name."
        )
        # Confirm the object exists via the injected service (no inline client creation).
        exists = gcs_service.blob_exists(gcs_config.raw_uploads_bucket, uploaded_object)
        assert exists, (
            f"Step 1 failed: object '{uploaded_object}' was not found in bucket "
            f"'{gcs_config.raw_uploads_bucket}' after upload. "
            "The upload may have failed silently."
        )

    def test_step2_authorized_sa_authenticated(
        self,
        gcs_config: GCSConfig,
    ) -> None:
        """Step 2 — verify the authorized service account is authenticated.

        Confirms that GOOGLE_APPLICATION_CREDENTIALS points to a valid service
        account JSON key and that the credentials can be loaded successfully.
        """
        creds_path = gcs_config.credentials_path
        assert creds_path, (
            "Step 2 failed: GOOGLE_APPLICATION_CREDENTIALS is not set. "
            "An authorized service account must be configured to run this test."
        )
        assert os.path.isfile(creds_path), (
            f"Step 2 failed: credentials file '{creds_path}' does not exist. "
            "Ensure GOOGLE_APPLICATION_CREDENTIALS points to a valid service account key."
        )
        import json
        with open(creds_path) as fh:
            creds_data = json.load(fh)
        sa_email = creds_data.get("client_email", "")
        assert sa_email, (
            f"Step 2 failed: could not read 'client_email' from '{creds_path}'. "
            "The credentials file does not appear to be a valid service account key."
        )

    def test_step3_download_succeeds_http200(
        self,
        gcs_service: GCSService,
        gcs_config: GCSConfig,
        uploaded_object: str,
    ) -> None:
        """Step 3 — authorized SA can download the test file (HTTP 200 OK).

        Downloads the previously uploaded object via the authenticated GCS client
        and asserts:
        - No exception is raised (equivalent to HTTP 200 OK).
        - The downloaded bytes match the originally uploaded content.

        With Public Access Prevention enforced, anonymous access returns HTTP 403.
        Authenticated access by an SA with roles/storage.objectViewer must succeed.
        """
        downloaded = gcs_service.download_object_bytes(
            bucket_name=gcs_config.raw_uploads_bucket,
            object_name=uploaded_object,
        )
        assert downloaded == _TEST_CONTENT, (
            f"Step 3 failed: downloaded content does not match uploaded content. "
            f"Expected {_TEST_CONTENT!r}, got {downloaded!r}. "
            f"Object: '{uploaded_object}', bucket: '{gcs_config.raw_uploads_bucket}'."
        )
