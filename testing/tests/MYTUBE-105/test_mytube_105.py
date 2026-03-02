"""
MYTUBE-105: Execute GCS integration tests on CI — tests pass without DefaultCredentialsError.

Verifies that the CI runner is correctly configured with GCP credentials so that:
  1. GOOGLE_APPLICATION_CREDENTIALS is set and points to a valid service account JSON file.
  2. storage.Client() initializes without raising DefaultCredentialsError.
  3. The gcs_service fixture from MYTUBE-49 can be constructed successfully
     (i.e. credentials reach GCSService via the injected storage client).
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.services.gcs_service import GCSService
from testing.core.config.gcs_config import GCSConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_gcs_imports():
    """Import GCS libs, skip the test if not installed."""
    try:
        from google.cloud import storage as gcs_storage
        from google.auth.exceptions import DefaultCredentialsError
        return gcs_storage, DefaultCredentialsError
    except ImportError:
        pytest.skip("google-cloud-storage is not installed")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGCSCredentialsConfiguredOnCI:
    """
    CI runner must have GOOGLE_APPLICATION_CREDENTIALS set to a valid service
    account JSON so that storage.Client() initialises without a
    DefaultCredentialsError and the gcs_service fixture reaches execution.
    """

    def test_google_application_credentials_env_var_is_set(self):
        """
        Precondition: GOOGLE_APPLICATION_CREDENTIALS must be set.

        Fails fast with a clear message when the CI runner is missing the
        environment variable entirely.
        """
        credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        assert credentials_path is not None, (
            "GOOGLE_APPLICATION_CREDENTIALS is not set. "
            "Configure the CI runner with a valid service account key file."
        )

    def test_google_application_credentials_file_exists(self):
        """
        The path in GOOGLE_APPLICATION_CREDENTIALS must point to an existing file.
        """
        credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if credentials_path is None:
            pytest.skip("GOOGLE_APPLICATION_CREDENTIALS is not set — covered by prior test")
        assert os.path.isfile(credentials_path), (
            f"GOOGLE_APPLICATION_CREDENTIALS points to a non-existent file: {credentials_path!r}. "
            "Ensure the service account JSON is present on the CI runner."
        )

    def test_google_application_credentials_file_is_valid_json(self):
        """
        The credentials file must be valid JSON with the expected service_account type.
        """
        credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not credentials_path or not os.path.isfile(credentials_path):
            pytest.skip("Valid credentials file not available — covered by prior tests")

        with open(credentials_path, "r") as fh:
            try:
                data = json.load(fh)
            except json.JSONDecodeError as exc:
                pytest.fail(
                    f"GOOGLE_APPLICATION_CREDENTIALS file is not valid JSON: {exc}. "
                    f"File: {credentials_path!r}"
                )

        assert data.get("type") == "service_account", (
            f"Expected credentials type 'service_account', got {data.get('type')!r}. "
            f"File: {credentials_path!r}"
        )

    def test_storage_client_initializes_without_default_credentials_error(self):
        """
        Core assertion: storage.Client() must not raise DefaultCredentialsError.

        This mirrors the gcs_service fixture in test_mytube_49.py. When
        GOOGLE_APPLICATION_CREDENTIALS is properly configured, ADC resolves the
        credentials automatically and the client is created successfully.
        """
        gcs_storage, DefaultCredentialsError = _require_gcs_imports()

        credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not credentials_path or not os.path.isfile(credentials_path):
            pytest.skip("Valid credentials file not available — covered by prior tests")

        try:
            client = gcs_storage.Client()
        except DefaultCredentialsError as exc:
            pytest.fail(
                f"storage.Client() raised DefaultCredentialsError — GCP credentials are not "
                f"properly configured on the CI runner.\n"
                f"GOOGLE_APPLICATION_CREDENTIALS={credentials_path!r}\n"
                f"Error: {exc}"
            )

        assert client is not None, "storage.Client() returned None unexpectedly."

    def test_gcs_service_fixture_constructed_with_ci_credentials(self):
        """
        End-to-end: GCSService must be constructible using the CI credentials,
        mirroring the full gcs_service fixture chain used in test_mytube_49.py:

          gcs_config -> storage_client -> gcs_service

        A successfully constructed GCSService confirms that the credential path
        is complete and the MYTUBE-49 tests will reach execution on CI (not skip
        or error due to missing credentials).
        """
        gcs_storage, DefaultCredentialsError = _require_gcs_imports()

        credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not credentials_path or not os.path.isfile(credentials_path):
            pytest.skip("Valid credentials file not available — covered by prior tests")

        try:
            storage_client = gcs_storage.Client()
        except DefaultCredentialsError as exc:
            pytest.fail(
                f"storage.Client() raised DefaultCredentialsError: {exc}"
            )

        config = GCSConfig()
        service = GCSService(config, storage_client=storage_client)

        assert service is not None
        assert service._client is storage_client
        assert service._config is config
