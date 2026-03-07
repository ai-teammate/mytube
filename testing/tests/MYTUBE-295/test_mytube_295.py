"""
MYTUBE-295: CI service account uploads MP4 to raw bucket — fixture setup succeeds.

Verifies that the CI service account (ai-teammate-gcloud@ai-native-478811.iam.gserviceaccount.com)
has the ``storage.objects.create`` permission required to upload test videos to
``gs://mytube-raw-uploads``, resolving the 403 Forbidden error that blocked MYTUBE-79.

Test sequence:
  1. Authenticate using the current GOOGLE_APPLICATION_CREDENTIALS.
  2. Build a minimal MP4 binary in-memory (ISO Base Media file format header).
  3. Upload the MP4 to gs://mytube-raw-uploads under a unique test path.
  4. Assert the upload completes without raising a 403 Forbidden / PermissionDenied error.
  5. Clean up the uploaded object.
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcp_config import GcpConfig
from testing.components.services.gcs_service import GCSService
from testing.core.config.gcs_config import GCSConfig

# ---------------------------------------------------------------------------
# Minimal valid MP4 bytes (ISO Base Media / ftyp box only — enough to satisfy
# GCS; actual codec validity is irrelevant for a permission check).
# ---------------------------------------------------------------------------
_MINIMAL_MP4_BYTES: bytes = (
    b"\x00\x00\x00\x18"  # box size = 24 bytes
    b"ftyp"              # box type = 'ftyp'
    b"isom"              # major brand
    b"\x00\x00\x02\x00"  # minor version
    b"isom"              # compatible brands[0]
    b"iso2"              # compatible brands[1]
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcp_config() -> GcpConfig:
    cfg = GcpConfig()
    if not cfg.project_id:
        pytest.skip(
            "GCP_PROJECT_ID is not set — cannot run GCS upload test. "
            "Set GCP_PROJECT_ID and GOOGLE_APPLICATION_CREDENTIALS to run this test."
        )
    return cfg


@pytest.fixture(scope="module")
def storage_client(gcp_config: GcpConfig):
    """Authenticated GCS client; skips if credentials are unavailable."""
    try:
        from google.cloud import storage as gcs_storage
        from google.auth.exceptions import DefaultCredentialsError
    except ImportError:
        pytest.skip("google-cloud-storage is not installed")

    try:
        client = gcs_storage.Client(project=gcp_config.project_id)
    except DefaultCredentialsError as exc:
        pytest.skip(
            f"GCP credentials not available: {exc}. "
            "Configure GOOGLE_APPLICATION_CREDENTIALS or Application Default Credentials."
        )
    return client


@pytest.fixture(scope="module")
def gcs_config(gcp_config: GcpConfig) -> GCSConfig:
    cfg = GCSConfig()
    # Align raw_uploads_bucket with GcpConfig so both configs are consistent.
    cfg.raw_uploads_bucket = gcp_config.raw_bucket
    return cfg


@pytest.fixture(scope="module")
def gcs_service(gcs_config: GCSConfig, storage_client) -> GCSService:
    return GCSService(config=gcs_config, storage_client=storage_client)


# ---------------------------------------------------------------------------
# Upload fixture: performs the upload and yields metadata; cleans up after.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def uploaded_mp4(gcs_service: GCSService, gcp_config: GcpConfig):
    """
    Upload a minimal MP4 binary to the raw-uploads bucket.

    Yields a dict with:
      - bucket: name of the destination bucket
      - object_name: the GCS object key that was uploaded
      - size_bytes: number of bytes uploaded
      - upload_succeeded: True if no exception was raised
      - error: exception instance if upload failed, else None
    """
    bucket_name = gcp_config.raw_bucket
    object_name = f"test-ci-permission/{uuid.uuid4()}/input.mp4"
    result = {
        "bucket": bucket_name,
        "object_name": object_name,
        "size_bytes": len(_MINIMAL_MP4_BYTES),
        "upload_succeeded": False,
        "error": None,
    }

    try:
        from google.api_core.exceptions import Forbidden
        bucket = gcs_service._client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        blob.upload_from_string(_MINIMAL_MP4_BYTES, content_type="video/mp4")
        result["upload_succeeded"] = True
    except Forbidden as exc:
        result["error"] = exc
    except Exception as exc:
        result["error"] = exc

    yield result

    # Teardown: remove the test object if upload succeeded.
    if result["upload_succeeded"]:
        try:
            gcs_service._client.bucket(bucket_name).blob(object_name).delete()
        except Exception:
            pass  # Best-effort cleanup; don't fail the test on teardown errors.


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCIServiceAccountUploadPermission:
    """
    Verifies that the CI service account has storage.objects.create on
    gs://mytube-raw-uploads, which is the prerequisite for MYTUBE-79's
    fixture setup to succeed.
    """

    def test_upload_does_not_raise_403(self, uploaded_mp4: dict):
        """
        The upload must not raise a 403 Forbidden / PermissionDenied error.
        If it does, the CI service account lacks storage.objects.create and
        MYTUBE-79's fixture will fail at the MP4 upload step.
        """
        error = uploaded_mp4["error"]
        if error is not None:
            try:
                from google.api_core.exceptions import Forbidden
                if isinstance(error, Forbidden):
                    pytest.fail(
                        f"HTTP 403 Forbidden received when uploading to "
                        f"gs://{uploaded_mp4['bucket']}/{uploaded_mp4['object_name']}.\n"
                        f"The CI service account lacks storage.objects.create permission.\n"
                        f"Error: {error}"
                    )
            except ImportError:
                pass
            pytest.fail(
                f"Upload to gs://{uploaded_mp4['bucket']}/{uploaded_mp4['object_name']} "
                f"failed with an unexpected error: {type(error).__name__}: {error}"
            )

    def test_upload_succeeded(self, uploaded_mp4: dict):
        """The upload flag must be True, confirming the object was written to GCS."""
        assert uploaded_mp4["upload_succeeded"] is True, (
            f"Upload to gs://{uploaded_mp4['bucket']}/{uploaded_mp4['object_name']} "
            f"did not succeed. Error: {uploaded_mp4['error']}"
        )

    def test_uploaded_object_exists_in_bucket(
        self, uploaded_mp4: dict, gcs_service: GCSService, gcp_config: GcpConfig
    ):
        """
        After a successful upload, attempt to verify the object is readable.
        Requires storage.objects.get; skip gracefully if that permission is absent
        since this ticket's scope is storage.objects.create only.
        """
        if not uploaded_mp4["upload_succeeded"]:
            pytest.skip("Upload did not succeed; skipping existence check.")

        try:
            from google.api_core.exceptions import Forbidden
            exists = gcs_service.blob_exists(
                gcp_config.raw_bucket, uploaded_mp4["object_name"]
            )
            assert exists, (
                f"Object gs://{gcp_config.raw_bucket}/{uploaded_mp4['object_name']} "
                f"was not found after upload."
            )
        except Forbidden:
            pytest.skip(
                "storage.objects.get permission not granted to the CI service account — "
                "existence check skipped. The primary permission (storage.objects.create) "
                "was verified by the upload test above."
            )
