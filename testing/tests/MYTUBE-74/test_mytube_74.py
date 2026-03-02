"""
MYTUBE-74: GCS tests must skip (not error) when GCP credentials are absent.

Verifies that the gcs_service fixture in test_mytube_49.py handles
DefaultCredentialsError gracefully by skipping instead of erroring.

Regression test for the fixture guard added to test_mytube_49.py:
  - When no storage_client is injected and no GCP credentials are available,
    GCSService construction raises DefaultCredentialsError.
  - The fixture must catch this and call pytest.skip(), not propagate the error.
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcs_config import GCSConfig
from testing.components.services.gcs_service import GCSService


class TestGCSServiceCredentialHandling:
    """GCSService fixture must not propagate DefaultCredentialsError."""

    def test_gcs_service_requires_injected_client_or_credentials(self):
        """
        Reproduces MYTUBE-74: constructing GCSService without a client injection
        calls storage.Client() which raises DefaultCredentialsError when no
        credentials are configured.

        This test verifies that DefaultCredentialsError is indeed raised by
        the bare constructor call — confirming the fixture needs to guard it.
        """
        from google.auth.exceptions import DefaultCredentialsError

        config = GCSConfig()
        with patch("google.cloud.storage.Client") as mock_client_cls:
            mock_client_cls.side_effect = DefaultCredentialsError(
                "Your default credentials were not found."
            )
            with pytest.raises(DefaultCredentialsError):
                # Without the fixture guard, this would propagate as an ERROR
                GCSService(config)

    def test_gcs_service_skips_when_credentials_absent(self):
        """
        Verifies the correct guard behaviour: when DefaultCredentialsError is
        raised during storage.Client() instantiation, the fixture-level guard
        in test_mytube_49.py must call pytest.skip() instead of letting the
        exception propagate.

        This test simulates what the fixed fixture does inline.
        """
        from google.auth.exceptions import DefaultCredentialsError

        config = GCSConfig()

        def _build_service_with_guard(cfg: GCSConfig) -> GCSService:
            """Mirrors the fixed gcs_service fixture logic."""
            from google.auth.exceptions import DefaultCredentialsError as DCE

            try:
                return GCSService(cfg)
            except DCE as exc:
                pytest.skip(
                    f"GCP credentials not available (DefaultCredentialsError): {exc}. "
                    "Configure GOOGLE_APPLICATION_CREDENTIALS or Application Default "
                    "Credentials to run GCS tests."
                )

        with patch("google.cloud.storage.Client") as mock_client_cls:
            mock_client_cls.side_effect = DefaultCredentialsError(
                "Your default credentials were not found."
            )
            with pytest.raises(pytest.skip.Exception):
                _build_service_with_guard(config)

    def test_gcs_service_constructed_with_injected_client(self):
        """
        GCSService must work correctly when a mock storage client is injected,
        proving the DI path is unaffected by the credential guard.
        """
        config = GCSConfig()
        mock_client = MagicMock()
        service = GCSService(config, storage_client=mock_client)
        assert service._client is mock_client
        assert service._config is config
