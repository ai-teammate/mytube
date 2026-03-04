"""
GCS service for bucket and public-access verification.

Wraps google-cloud-storage and httpx to:
  - Check bucket existence
  - Inspect IAM bindings for public read (allUsers objectViewer)
  - Upload a test object and verify it is served publicly via HTTP
"""
from __future__ import annotations

import uuid
from typing import Optional

import httpx
from google.api_core.exceptions import NotFound
from google.cloud import storage

from testing.core.config.gcs_config import GCSConfig


class GCSService:
    """Provides GCS bucket and CDN delivery verification operations."""

    def __init__(self, config: GCSConfig, storage_client: Optional[storage.Client] = None):
        self._config = config
        self._client = storage_client or storage.Client()

    # ------------------------------------------------------------------
    # Bucket checks
    # ------------------------------------------------------------------

    def bucket_exists(self, bucket_name: str) -> bool:
        """Return True if the bucket exists and is accessible.

        Uses list_blobs (requires only storage.objects.list) instead of
        get_bucket (requires storage.buckets.get) so that CI service accounts
        with object-level-only permissions can still verify existence.
        Falls back to a public HTTP probe if list_blobs also fails.
        """
        try:
            next(iter(self._client.list_blobs(bucket_name, max_results=1)), None)
            return True
        except NotFound:
            return False
        except Exception:
            # Fall back to a public HTTP probe — a 200 or 403 (bucket exists
            # but requester-pays / access denied) both confirm existence.
            url = self._config.public_object_url(bucket_name, "")
            try:
                resp = httpx.get(url.rstrip("/") + "/", timeout=10.0, follow_redirects=True)
                return resp.status_code in (200, 403)
            except Exception:
                return False

    def has_public_read_iam(self, bucket_name: str) -> bool:
        """
        Return True if allUsers has roles/storage.objectViewer on the bucket.

        Requires storage.buckets.getIamPolicy on the CI service account.
        Raises PermissionError if the SA lacks that permission so that callers
        can skip or fail the assertion with a clear message rather than silently
        passing via a proxy check that does not verify the IAM binding.
        """
        bucket = self._client.get_bucket(bucket_name)
        policy = bucket.get_iam_policy(requested_policy_version=1)
        for binding in policy.bindings:
            if binding["role"] == "roles/storage.objectViewer":
                if "allUsers" in binding["members"]:
                    return True
        return False

    # ------------------------------------------------------------------
    # Upload + public fetch
    # ------------------------------------------------------------------

    def upload_test_object(self, bucket_name: str, content: bytes = b"HLS test probe") -> str:
        """
        Upload a small test object to the bucket and return its object name.
        Uses a UUID-based name to avoid collisions between test runs.
        """
        object_name = f"test-probe-{uuid.uuid4()}.txt"
        bucket = self._client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        blob.upload_from_string(content, content_type="text/plain")
        return object_name

    def fetch_object_via_public_url(self, bucket_name: str, object_name: str) -> httpx.Response:
        """
        Fetch an object via its direct public GCS URL.
        Returns the HTTP response.
        """
        url = self._config.public_object_url(bucket_name, object_name)
        return httpx.get(url, follow_redirects=True, timeout=30.0)

    def fetch_object_via_cdn_url(self, object_name: str) -> httpx.Response:
        """
        Fetch an object via the Cloud CDN frontend URL.
        CDN_BASE_URL must be configured in GCSConfig.
        Returns the HTTP response.
        """
        url = self._config.cdn_object_url(object_name)
        return httpx.get(url, follow_redirects=True, timeout=30.0)

    def blob_exists(self, bucket_name: str, object_name: str) -> bool:
        """Return True if the object exists in the bucket."""
        blob = self._client.bucket(bucket_name).blob(object_name)
        return blob.exists()

    def download_object_bytes(
        self, bucket_name: str, object_name: str, start: int = 0, end: Optional[int] = None
    ) -> bytes:
        """Download bytes from a GCS object, optionally restricted to a byte range."""
        blob = self._client.bucket(bucket_name).blob(object_name)
        return blob.download_as_bytes(start=start, end=end)

    def delete_object(self, bucket_name: str, object_name: str) -> None:
        """Delete an object from the bucket (cleanup helper)."""
        bucket = self._client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        blob.delete()
