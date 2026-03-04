"""
MYTUBE-173: CI SA lacks storage.buckets.get on mytube-hls-output — bucket
existence and IAM checks return 403 Forbidden.

Root cause: infra/setup.sh grants roles/storage.legacyBucketReader to the CI
service account (ai-teammate-gcloud) on mytube-raw-uploads (MYTUBE-182 fix)
but never on mytube-hls-output.  Without that IAM binding the GCS SDK's
get_bucket() raises 403 Forbidden when any CI test calls bucket_exists() or
has_public_read_iam() against the HLS bucket.

Tests in this module:

  TestSetupShGrantsCIReaderOnHLSBucket
    — Validates that infra/setup.sh grants roles/storage.legacyBucketReader
      to the CI service account on mytube-hls-output.
      FAILS against the original script and PASSES after the fix.

  TestGCSServiceForbiddenPropagation
    — Documents the 403 failure mode: GCSService.has_public_read_iam() must
      propagate Forbidden (not swallow it silently) so that the MYTUBE-49
      test can skip with an informative message rather than a bare crash.
      Runs fully offline via a mock storage client.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from google.api_core.exceptions import Forbidden

from testing.components.services.gcs_service import GCSService
from testing.core.config.gcs_config import GCSConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SETUP_SH = Path(__file__).resolve().parents[3] / "infra" / "setup.sh"

CI_SA_NAME = "ai-teammate-gcloud"
CI_SA_ROLE = "roles/storage.legacyBucketReader"
HLS_BUCKET_VAR = "HLS_BUCKET"
HLS_BUCKET_NAME = "mytube-hls-output"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hls_bucket_iam_section(content: str) -> str:
    """Extract the portion of setup.sh that grants IAM on the HLS bucket to
    any identity other than allUsers (i.e. service-account grants).

    We look for all `add-iam-policy-binding` calls that reference HLS_BUCKET
    or mytube-hls-output and capture the surrounding block.
    """
    pattern = (
        r"gcloud storage buckets add-iam-policy-binding\s+"
        r"['\"]gs://\$\{HLS_BUCKET\}['\"]"
        r".*?--project[^\n]*"
    )
    matches = re.findall(pattern, content, re.DOTALL)
    return "\n".join(matches)


def _make_forbidden_client() -> MagicMock:
    """Return a mock GCS client that raises Forbidden on every bucket
    metadata call, simulating a CI SA that lacks storage.buckets.get on
    mytube-hls-output.
    """
    client = MagicMock()
    err = Forbidden(
        message=(
            "ai-teammate-gcloud@ai-native-478811.iam.gserviceaccount.com does not have "
            "storage.buckets.get access to the Google Cloud Storage bucket. "
            "Permission 'storage.buckets.get' denied on resource "
            "(or it may not exist)."
        )
    )
    # get_bucket() path — used by has_public_read_iam()
    client.get_bucket.side_effect = err
    # list_blobs() path — used by bucket_exists() primary path
    client.list_blobs.side_effect = err
    return client


# ---------------------------------------------------------------------------
# Tests — setup.sh content validation
# ---------------------------------------------------------------------------


class TestSetupShGrantsCIReaderOnHLSBucket:
    """infra/setup.sh must grant roles/storage.legacyBucketReader to the CI
    service account on mytube-hls-output.

    Both tests FAIL against the original setup.sh (the bug) and PASS after
    the fix is applied.
    """

    def test_ci_service_account_granted_bucket_reader_on_hls_bucket(self):
        """setup.sh must grant roles/storage.legacyBucketReader to the CI SA
        (ai-teammate-gcloud) on the HLS output bucket (mytube-hls-output).

        Without this grant the CI SA gets 403 Forbidden on every bucket
        metadata API call, causing test_hls_bucket_exists and
        test_hls_bucket_has_public_read_iam (MYTUBE-49) to fail.
        """
        content = SETUP_SH.read_text()

        # The script must reference the CI SA
        assert CI_SA_NAME in content, (
            f"infra/setup.sh must reference the CI service account '{CI_SA_NAME}' "
            "and grant it read access to the HLS output bucket."
        )

        # The legacyBucketReader role must be granted on the HLS bucket
        hls_iam_block = _hls_bucket_iam_section(content)
        assert CI_SA_ROLE in hls_iam_block, (
            f"infra/setup.sh must grant '{CI_SA_ROLE}' to the CI service account "
            f"({CI_SA_NAME}) on the HLS output bucket (${{HLS_BUCKET}} / "
            f"{HLS_BUCKET_NAME}). "
            "Without this grant the CI SA lacks storage.buckets.get and every "
            "GCS metadata call against that bucket returns 403 Forbidden."
        )

    def test_hls_bucket_ci_grant_references_ci_sa_variable(self):
        """The legacyBucketReader grant for the HLS bucket must use $CI_SA_EMAIL
        (not a hard-coded address) so that it stays consistent with the variable
        defined at the top of setup.sh.
        """
        content = SETUP_SH.read_text()
        hls_iam_block = _hls_bucket_iam_section(content)

        # After the fix the block should contain the CI_SA_EMAIL variable
        assert "CI_SA_EMAIL" in hls_iam_block or CI_SA_NAME in hls_iam_block, (
            "The HLS bucket legacyBucketReader grant in infra/setup.sh must "
            "reference $CI_SA_EMAIL (or ai-teammate-gcloud) so the CI service "
            "account is correctly identified."
        )


# ---------------------------------------------------------------------------
# Tests — GCSService error propagation
# ---------------------------------------------------------------------------


class TestGCSServiceForbiddenPropagation:
    """GCSService must propagate Forbidden (403) from the storage client.

    Documents the failure mode observed in CI before the IAM fix:
    has_public_read_iam() raises Forbidden when the service account lacks
    storage.buckets.get on mytube-hls-output.

    These tests run fully offline via a mock storage client and serve as
    regression guards for the service's error-propagation behaviour.
    """

    @pytest.fixture(scope="class")
    def config(self) -> GCSConfig:
        return GCSConfig()

    @pytest.fixture(scope="class")
    def service_with_forbidden_client(self, config: GCSConfig) -> GCSService:
        return GCSService(config=config, storage_client=_make_forbidden_client())

    def test_has_public_read_iam_raises_forbidden_when_sa_lacks_permission(
        self, service_with_forbidden_client: GCSService, config: GCSConfig
    ):
        """has_public_read_iam() must raise Forbidden when the SA lacks
        storage.buckets.get.

        This is the root failure observed in test_hls_bucket_has_public_read_iam
        (MYTUBE-49) when the CI service account has no IAM binding on
        mytube-hls-output.
        """
        with pytest.raises(Forbidden):
            service_with_forbidden_client.has_public_read_iam(config.hls_bucket)

    def test_forbidden_error_carries_403_status_code(
        self, service_with_forbidden_client: GCSService, config: GCSConfig
    ):
        """Forbidden exception must carry HTTP status 403 (not a generic error)."""
        with pytest.raises(Forbidden) as exc_info:
            service_with_forbidden_client.has_public_read_iam(config.hls_bucket)

        assert exc_info.value.code == 403, (
            f"Expected Forbidden.code == 403, got {exc_info.value.code}"
        )
