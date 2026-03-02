"""
MYTUBE-114: Run GCS tests with insufficient IAM permissions — 403 Forbidden error handled.

Objective:
    Verify that when the service account lacks the required GCS IAM roles
    (storage.buckets.getIamPolicy or storage.objects.create), the test suite
    fails with google.api_core.exceptions.Forbidden (403) rather than a
    DefaultCredentialsError, ensuring the system correctly identifies
    authentication success but authorization failure.

Approach:
    Rather than requiring a real under-privileged service account (which is an
    environment concern), this test simulates the scenario by injecting a mock
    GCS client that raises google.api_core.exceptions.Forbidden on every GCS
    API call. It then verifies that GCSService propagates Forbidden correctly
    instead of swallowing it or converting it to a DefaultCredentialsError.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from google.api_core.exceptions import Forbidden

from testing.components.services.gcs_service import GCSService
from testing.core.config.gcs_config import GCSConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_forbidden_client() -> MagicMock:
    """Return a mock google.cloud.storage.Client that raises Forbidden on every call."""
    client = MagicMock()

    # get_bucket raises Forbidden (simulates missing storage.buckets.get)
    client.get_bucket.side_effect = Forbidden(
        message="The caller does not have permission (simulated 403 for test)"
    )

    # bucket().blob().upload_from_string raises Forbidden (simulates missing storage.objects.create)
    mock_blob = MagicMock()
    mock_blob.upload_from_string.side_effect = Forbidden(
        message="Insufficient permission to create object (simulated 403 for test)"
    )
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    client.bucket.return_value = mock_bucket

    return client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcs_config() -> GCSConfig:
    return GCSConfig()


@pytest.fixture(scope="module")
def forbidden_gcs_service(gcs_config: GCSConfig) -> GCSService:
    """GCSService backed by a mock client that always raises Forbidden (403)."""
    return GCSService(gcs_config, storage_client=_make_forbidden_client())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGCSForbiddenErrorHandling:
    """
    Verify that GCS calls raise google.api_core.exceptions.Forbidden (403)
    rather than DefaultCredentialsError when credentials are valid but the
    service account lacks the required IAM roles.
    """

    def test_bucket_exists_raises_forbidden_not_credentials_error(
        self, forbidden_gcs_service: GCSService, gcs_config: GCSConfig
    ):
        """
        bucket_exists() must propagate Forbidden (403) when the SA lacks
        storage.buckets.get or storage.buckets.getIamPolicy permission.

        This confirms the system distinguishes authentication failure
        (DefaultCredentialsError) from authorization failure (Forbidden/403).
        """
        from google.auth.exceptions import DefaultCredentialsError

        with pytest.raises(Forbidden):
            forbidden_gcs_service.bucket_exists(gcs_config.hls_bucket)

        # Explicitly confirm DefaultCredentialsError is NOT raised
        try:
            forbidden_gcs_service.bucket_exists(gcs_config.hls_bucket)
        except Forbidden:
            pass  # Expected — this is the correct error
        except DefaultCredentialsError as exc:
            pytest.fail(
                f"Expected Forbidden (403) but got DefaultCredentialsError: {exc}. "
                "The system should report an authorization failure, not a credentials failure."
            )

    def test_has_public_read_iam_raises_forbidden_not_credentials_error(
        self, forbidden_gcs_service: GCSService, gcs_config: GCSConfig
    ):
        """
        has_public_read_iam() must raise Forbidden (403) when the SA lacks
        storage.buckets.getIamPolicy permission.
        """
        from google.auth.exceptions import DefaultCredentialsError

        with pytest.raises(Forbidden):
            forbidden_gcs_service.has_public_read_iam(gcs_config.hls_bucket)

        try:
            forbidden_gcs_service.has_public_read_iam(gcs_config.hls_bucket)
        except Forbidden:
            pass
        except DefaultCredentialsError as exc:
            pytest.fail(
                f"Expected Forbidden (403) but got DefaultCredentialsError: {exc}."
            )

    def test_upload_test_object_raises_forbidden_not_credentials_error(
        self, forbidden_gcs_service: GCSService, gcs_config: GCSConfig
    ):
        """
        upload_test_object() must raise Forbidden (403) when the SA lacks
        storage.objects.create permission.
        """
        from google.auth.exceptions import DefaultCredentialsError

        with pytest.raises(Forbidden):
            forbidden_gcs_service.upload_test_object(gcs_config.hls_bucket)

        try:
            forbidden_gcs_service.upload_test_object(gcs_config.hls_bucket)
        except Forbidden:
            pass
        except DefaultCredentialsError as exc:
            pytest.fail(
                f"Expected Forbidden (403) but got DefaultCredentialsError: {exc}."
            )

    def test_forbidden_error_is_http_403(
        self, forbidden_gcs_service: GCSService, gcs_config: GCSConfig
    ):
        """
        Confirm the Forbidden exception represents an HTTP 403 status code,
        not a network or authentication error class.
        """
        with pytest.raises(Forbidden) as exc_info:
            forbidden_gcs_service.bucket_exists(gcs_config.hls_bucket)

        assert isinstance(exc_info.value, Forbidden), (
            f"Expected google.api_core.exceptions.Forbidden but got "
            f"{type(exc_info.value).__name__}"
        )
