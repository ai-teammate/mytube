"""
MYTUBE-297: GCS raw-uploads bucket Public Access Prevention not enforced on
existing buckets.

Verifies that:
  1. infra/setup.sh enforces --public-access-prevention on buckets that
     already exist (i.e. contains a `buckets update` remediation command).
  2. .github/workflows/provision-gcs-buckets.yml likewise updates existing
     buckets rather than silently skipping them.
  3. GCSBucketService.attempt_public_access returns a result object that can
     distinguish HTTP 403 (expected) from HTTP 404 (security misconfiguration).

Tests 1 and 2 are static-analysis checks against the provisioning scripts —
they fail before the fix and pass after.  Test 3 is a pure-unit mock test
that exercises the service with injected HTTP responses.
"""
import os
import re
import sys
import unittest
from unittest.mock import patch, MagicMock
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcs_config import GCSConfig
from testing.components.services.gcs_bucket_service import (
    GCSBucketService,
    PublicAccessResult,
)

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
SETUP_SH = os.path.join(REPO_ROOT, "infra", "setup.sh")
PROVISION_YML = os.path.join(
    REPO_ROOT, ".github", "workflows", "provision-gcs-buckets.yml"
)


class TestSetupShRemediatesExistingBucket(unittest.TestCase):
    """setup.sh must enforce PAP on existing buckets, not just new ones."""

    def setUp(self):
        with open(SETUP_SH, "r") as fh:
            self.content = fh.read()

    def test_setup_sh_contains_buckets_update_with_pap(self):
        """infra/setup.sh must run `gcloud storage buckets update … --public-access-prevention`
        so that an already-provisioned bucket with PAP disabled is remediated.
        """
        # Match: gcloud storage buckets update ... --public-access-prevention
        # (must NOT be --no-public-access-prevention)
        pattern = (
            r"gcloud\s+storage\s+buckets\s+update\s+.*"
            r"--public-access-prevention(?![\w-])"
        )
        match = re.search(pattern, self.content, re.DOTALL)
        self.assertIsNotNone(
            match,
            "infra/setup.sh does not contain a 'gcloud storage buckets update "
            "... --public-access-prevention' remediation command. "
            "Existing buckets provisioned without PAP will remain insecure.",
        )

    def test_setup_sh_update_targets_raw_bucket(self):
        """The update command in setup.sh must target the RAW_BUCKET variable."""
        pattern = (
            r"gcloud\s+storage\s+buckets\s+update\s+.*"
            r"(?:RAW_BUCKET|\bmytube-raw-uploads\b).*"
            r"--public-access-prevention(?![\w-])"
        )
        match = re.search(pattern, self.content, re.DOTALL)
        # Allow brace-expansion too: ${RAW_BUCKET}
        pattern_brace = (
            r"gcloud\s+storage\s+buckets\s+update\s+.*"
            r"\$\{?RAW_BUCKET\}?.*"
            r"--public-access-prevention(?![\w-])"
        )
        match2 = re.search(pattern_brace, self.content, re.DOTALL)
        self.assertTrue(
            bool(match) or bool(match2),
            "The 'buckets update --public-access-prevention' command in "
            "infra/setup.sh does not reference RAW_BUCKET / mytube-raw-uploads.",
        )


class TestProvisionWorkflowRemediatesExistingBucket(unittest.TestCase):
    """provision-gcs-buckets.yml must enforce PAP on existing buckets."""

    def setUp(self):
        with open(PROVISION_YML, "r") as fh:
            self.content = fh.read()

    def test_workflow_contains_buckets_update_with_pap(self):
        """.github/workflows/provision-gcs-buckets.yml must run `gcloud storage
        buckets update … --public-access-prevention` for the raw-uploads bucket.
        """
        pattern = (
            r"gcloud\s+storage\s+buckets\s+update\s+.*"
            r"--public-access-prevention(?![\w-])"
        )
        match = re.search(pattern, self.content, re.DOTALL)
        self.assertIsNotNone(
            match,
            "provision-gcs-buckets.yml does not contain a "
            "'gcloud storage buckets update ... --public-access-prevention' "
            "remediation step. Already-provisioned buckets without PAP will "
            "remain insecure after the workflow runs.",
        )


class TestGCSBucketServicePublicAccess(unittest.TestCase):
    """Unit tests for GCSBucketService.attempt_public_access with mocked HTTP."""

    def _make_service(self) -> GCSBucketService:
        config = GCSConfig()
        config.raw_uploads_bucket = "mytube-raw-uploads"
        return GCSBucketService(config=config, storage_client=None)

    def test_http_403_is_access_denied(self):
        """HTTP 403 from GCS means access is correctly denied — bucket is secure."""
        service = self._make_service()
        exc = urllib.error.HTTPError(
            url="https://storage.googleapis.com/mytube-raw-uploads/probe.txt",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=None,
        )
        with patch("urllib.request.urlopen", side_effect=exc):
            result = service.attempt_public_access("probe.txt")

        self.assertEqual(result.http_status, 403)
        # The integration test assertion (from MYTUBE-48) must pass:
        self.assertEqual(
            result.http_status,
            403,
            "Expected HTTP 403 (Forbidden) — bucket has PAP enforced.",
        )

    def test_http_404_indicates_pap_not_enforced(self):
        """HTTP 404 from GCS means the bucket is reachable but the object is
        absent — PAP is NOT enforced.  This is the bug scenario: the bucket
        processes the anonymous request instead of blocking it with 403.
        """
        service = self._make_service()
        exc = urllib.error.HTTPError(
            url="https://storage.googleapis.com/mytube-raw-uploads/probe.txt",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )
        with patch("urllib.request.urlopen", side_effect=exc):
            result = service.attempt_public_access("probe.txt")

        self.assertEqual(result.http_status, 404)
        # Confirm that a 404 would fail the MYTUBE-48 security assertion:
        with self.assertRaises(AssertionError):
            assert result.http_status == 403, (
                f"Expected HTTP 403 but got HTTP {result.http_status}"
            )


if __name__ == "__main__":
    unittest.main()
