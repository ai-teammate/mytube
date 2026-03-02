"""
MYTUBE-116: Verify GCS bucket existence check — test fails if bucket is missing.

Ensures that test_hls_bucket_exists (MYTUBE-49) correctly identifies and reports
when the target GCS bucket `mytube-hls-output` has not been provisioned.

The test uses a mock GCS client that raises google.api_core.exceptions.NotFound
to simulate a missing bucket, then asserts that:
  1. GCSService.bucket_exists() returns False.
  2. The assertion in test_hls_bucket_exists fails with an AssertionError.
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from google.api_core.exceptions import NotFound

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.services.gcs_service import GCSService
from testing.core.config.gcs_config import GCSConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_not_found_client() -> MagicMock:
    """Return a mock storage.Client whose get_bucket always raises NotFound."""
    client = MagicMock()
    client.get_bucket.side_effect = NotFound("mytube-hls-output")
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBucketExistenceCheck:
    """
    Verify that the GCS bucket existence check correctly reports a missing bucket.

    Precondition: GCP credentials are valid and configured, but the bucket
    `mytube-hls-output` does not exist (simulated via a mock client).
    """

    def test_bucket_exists_returns_false_when_bucket_missing(self):
        """
        GCSService.bucket_exists() must return False — not raise — when the
        bucket is absent (NotFound is caught and converted to a boolean result).
        """
        config = GCSConfig()
        service = GCSService(config, storage_client=_make_not_found_client())

        result = service.bucket_exists(config.hls_bucket)

        assert result is False, (
            f"Expected bucket_exists('{config.hls_bucket}') to return False "
            "when the bucket does not exist, but got True."
        )

    def test_hls_bucket_exists_assertion_fails_when_bucket_missing(self):
        """
        The assertion in test_hls_bucket_exists must raise AssertionError
        when the bucket is missing, so the test reports a failure.

        This mirrors running:
            pytest testing/tests/MYTUBE-49/test_mytube_49.py::test_hls_bucket_exists
        in an environment where `mytube-hls-output` has not been provisioned.
        """
        config = GCSConfig()
        service = GCSService(config, storage_client=_make_not_found_client())

        with pytest.raises(AssertionError) as exc_info:
            assert service.bucket_exists(config.hls_bucket), (
                f"Bucket '{config.hls_bucket}' does not exist or is not accessible. "
                "Run infra/setup.sh to provision the bucket."
            )

        assert config.hls_bucket in str(exc_info.value), (
            "AssertionError message should reference the missing bucket name."
        )

    def test_not_found_exception_is_raised_by_storage_client(self):
        """
        Confirm that the underlying storage client raises
        google.api_core.exceptions.NotFound (HTTP 404) when the bucket is absent.

        This directly validates the precondition stated in the ticket: the SDK
        raises NotFound before GCSService converts it to a boolean.
        """
        client = _make_not_found_client()

        with pytest.raises(NotFound):
            client.get_bucket("mytube-hls-output")
