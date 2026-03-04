"""
MYTUBE-182: CI service account missing storage.buckets.get permission on
mytube-raw-uploads bucket.

Root cause (see outputs/rca.md):
  1. infra/setup.sh creates mytube-raw-uploads with --no-public-access-prevention
     instead of --public-access-prevention, so public_access_prevention is
     'inherited' (not 'enforced') — the MYTUBE-48 test expects 'enforced'.
  2. infra/setup.sh never grants any read permission to the CI service account
     (ai-teammate-gcloud) on mytube-raw-uploads, causing 403 Forbidden when
     test_bucket_exists and test_public_access_prevention_enforced run in CI.

Tests in this module:

  TestSetupShProvisionsBucketCorrectly
    — Validates that infra/setup.sh contains the two required fixes.
      These tests FAIL against the original script and PASS after the fix.

  TestGCSBucketServiceForbiddenPropagation
    — Documents the 403 failure mode: GCSBucketService must propagate
      Forbidden (not swallow it) when the storage client returns 403.
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

from testing.components.services.gcs_bucket_service import GCSBucketService
from testing.core.config.gcs_config import GCSConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SETUP_SH = Path(__file__).resolve().parents[3] / "infra" / "setup.sh"

# The CI service account that needs read access to the raw uploads bucket.
CI_SA_NAME = "ai-teammate-gcloud"
CI_SA_ROLE = "roles/storage.legacyBucketReader"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _raw_bucket_create_block(content: str) -> str:
    """Extract the gcloud command that creates the raw uploads bucket from setup.sh.

    Returns the multi-line command string from 'buckets create "gs://${RAW_BUCKET}"'
    through the closing '--project' flag.
    """
    match = re.search(
        r"gcloud storage buckets create ['\"]gs://\$\{RAW_BUCKET\}['\"].*?--project[^\n]*",
        content,
        re.DOTALL,
    )
    assert match is not None, (
        "Could not locate the raw bucket creation command in infra/setup.sh. "
        "Expected: gcloud storage buckets create \"gs://${RAW_BUCKET}\" ..."
    )
    return match.group(0)


def _make_forbidden_client() -> MagicMock:
    """Return a mock GCS client that raises Forbidden on every metadata call.

    Simulates what CI observes when ai-teammate-gcloud lacks storage.buckets.get
    on mytube-raw-uploads.
    """
    client = MagicMock()
    err = Forbidden(
        message=(
            "ai-teammate-gcloud@ai-native-478811.iam.gserviceaccount.com does not have "
            "storage.buckets.get access to the Google Cloud Storage bucket. "
            "Permission 'storage.buckets.get' denied on resource (or it may not exist)."
        )
    )
    # bucket().exists() path (used by bucket_exists())
    client.bucket.return_value.exists.side_effect = err
    # get_bucket() path (used by get_iam_info())
    client.get_bucket.side_effect = err
    return client


# ---------------------------------------------------------------------------
# Tests — setup.sh content validation
# ---------------------------------------------------------------------------


class TestSetupShProvisionsBucketCorrectly:
    """infra/setup.sh must provision mytube-raw-uploads with enforced private access
    and grant the CI service account read permission.

    Both tests FAIL against the original setup.sh (the bug) and PASS after the fix.
    """

    def test_raw_bucket_created_with_public_access_prevention_enforced(self):
        """setup.sh must use --public-access-prevention (not --no-public-access-prevention)
        when creating the raw uploads bucket.

        --no-public-access-prevention results in public_access_prevention='inherited'.
        The MYTUBE-48 test_public_access_prevention_enforced asserts the value is
        'enforced', so the bucket must be created with --public-access-prevention.
        """
        content = SETUP_SH.read_text()
        raw_cmd = _raw_bucket_create_block(content)

        assert "--no-public-access-prevention" not in raw_cmd, (
            "infra/setup.sh must NOT use --no-public-access-prevention for "
            f"{SETUP_SH.name} raw bucket creation. "
            "Replace it with --public-access-prevention so that "
            "public_access_prevention is set to 'enforced'."
        )
        assert "--public-access-prevention" in raw_cmd, (
            "infra/setup.sh must use --public-access-prevention when creating "
            "the raw uploads bucket so that public_access_prevention='enforced'."
        )

    def test_ci_service_account_granted_bucket_reader_on_raw_bucket(self):
        """setup.sh must grant roles/storage.legacyBucketReader to the CI SA
        (ai-teammate-gcloud) on the raw uploads bucket.

        Without this grant the CI service account gets 403 Forbidden on every
        bucket metadata API call, causing test_bucket_exists and
        test_public_access_prevention_enforced to fail.
        """
        content = SETUP_SH.read_text()

        assert CI_SA_NAME in content, (
            f"infra/setup.sh must reference the CI service account '{CI_SA_NAME}' "
            f"and grant it read access to the raw uploads bucket."
        )
        assert CI_SA_ROLE in content, (
            f"infra/setup.sh must grant '{CI_SA_ROLE}' to the CI service account "
            f"({CI_SA_NAME}) on the raw uploads bucket. "
            "The MYTUBE-48 tests require storage.buckets.get permission."
        )


# ---------------------------------------------------------------------------
# Tests — GCSBucketService error propagation
# ---------------------------------------------------------------------------


class TestGCSBucketServiceForbiddenPropagation:
    """GCSBucketService must propagate Forbidden (403) from the storage client.

    Documents the failure mode observed in CI before the IAM fix:
    bucket_exists() and get_iam_info() both raise Forbidden when the service
    account lacks storage.buckets.get on the bucket.

    These tests run fully offline via a mock storage client and serve as
    regression guards for the service's error-propagation behaviour.
    """

    @pytest.fixture(scope="class")
    def config(self) -> GCSConfig:
        return GCSConfig()

    @pytest.fixture(scope="class")
    def service_with_forbidden_client(self, config: GCSConfig) -> GCSBucketService:
        return GCSBucketService(config=config, storage_client=_make_forbidden_client())

    def test_bucket_exists_raises_forbidden_when_sa_lacks_permission(
        self, service_with_forbidden_client: GCSBucketService
    ):
        """bucket_exists() must raise Forbidden when the SA lacks storage.buckets.get.

        This is the root failure seen in test_bucket_exists (MYTUBE-48) when the
        CI service account has no IAM binding on mytube-raw-uploads.
        """
        with pytest.raises(Forbidden):
            service_with_forbidden_client.bucket_exists()

    def test_get_iam_info_raises_forbidden_when_sa_lacks_permission(
        self, service_with_forbidden_client: GCSBucketService
    ):
        """get_iam_info() must raise Forbidden when the SA lacks storage.buckets.get.

        This is the root failure seen in test_public_access_prevention_enforced
        (MYTUBE-48) when the CI service account has no IAM binding.
        """
        with pytest.raises(Forbidden):
            service_with_forbidden_client.get_iam_info()

    def test_forbidden_error_carries_403_status_code(
        self, service_with_forbidden_client: GCSBucketService
    ):
        """Forbidden exception must carry HTTP status 403 (not a generic error)."""
        with pytest.raises(Forbidden) as exc_info:
            service_with_forbidden_client.bucket_exists()

        assert exc_info.value.code == 403, (
            f"Expected Forbidden.code == 403, got {exc_info.value.code}"
        )
