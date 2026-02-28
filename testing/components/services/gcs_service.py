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
        """Return True if the bucket exists and is accessible."""
        try:
            self._client.get_bucket(bucket_name)
            return True
        except NotFound:
            return False

    def has_public_read_iam(self, bucket_name: str) -> bool:
        """
        Return True if allUsers has roles/storage.objectViewer on the bucket.

        This confirms that the HLS output bucket is publicly readable,
        satisfying the CDN delivery requirement.
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
        Fetch an object via its public GCS URL (simulating CDN delivery).
        Returns the HTTP response.
        """
        url = self._config.public_object_url(bucket_name, object_name)
        return httpx.get(url, follow_redirects=True, timeout=30.0)

    def delete_object(self, bucket_name: str, object_name: str) -> None:
        """Delete an object from the bucket (cleanup helper)."""
        bucket = self._client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        blob.delete()
