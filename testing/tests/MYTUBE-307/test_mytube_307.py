"""
MYTUBE-307: SA ai-teammate-gcloud missing roles/storage.objectViewer on
mytube-raw-uploads bucket.

Verifies that the provisioning scripts grant ``roles/storage.objectViewer``
to the CI service account (``ai-teammate-gcloud``) on the
``mytube-raw-uploads`` bucket so that ``storage.objects.get`` operations
(``blob.exists()`` / ``download_as_bytes()``) succeed.

Tests 1 and 2 are static-analysis checks — they read the provisioning scripts
as text and assert the required IAM binding command is present.  They fail
before the fix and pass after.

Test 3 is an optional GCP integration test that verifies the live IAM policy.
It is skipped automatically when ``GCP_PROJECT_ID`` is not set, so it never
blocks the CI pipeline in environments without GCP credentials.

Root cause
----------
``infra/setup.sh`` and ``.github/workflows/provision-gcs-buckets.yml``
granted only ``roles/storage.legacyBucketReader`` (list, not get) and
``roles/storage.objectCreator`` (write-only) to the CI SA.  Neither role
includes ``storage.objects.get``.  Only ``roles/storage.objectViewer``
grants that permission.

Fix
---
Add ``roles/storage.objectViewer`` IAM binding for the CI SA on
``gs://mytube-raw-uploads`` in both provisioning scripts.
"""
from __future__ import annotations

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcp_config import GcpConfig

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
SETUP_SH = os.path.join(REPO_ROOT, "infra", "setup.sh")
PROVISION_YML = os.path.join(
    REPO_ROOT, ".github", "workflows", "provision-gcs-buckets.yml"
)

_OBJECT_VIEWER_ROLE = "roles/storage.objectViewer"
_CI_SA_SHORT = "ai-teammate-gcloud"
_RAW_BUCKET = "mytube-raw-uploads"


# ---------------------------------------------------------------------------
# Static-analysis helpers
# ---------------------------------------------------------------------------


def _has_object_viewer_for_ci_sa(content: str) -> bool:
    """Return True if *content* contains an add-iam-policy-binding call that
    grants ``roles/storage.objectViewer`` to the CI SA on the raw-uploads bucket.

    Accepts both shell-variable references (``${CI_SA_EMAIL}``, ``$CI_SA``,
    ``ai-teammate-gcloud``) and GitHub Actions variable syntax
    (``${{ env.CI_SA }}``).
    """
    ci_sa_patterns = [
        r"\$\{?CI_SA(?:_EMAIL)?\}?",
        re.escape(_CI_SA_SHORT),
        r"\$\{\{\s*env\.CI_SA\s*\}\}",
    ]
    bucket_patterns = [
        r"\$\{?RAW_BUCKET\}?",
        re.escape(_RAW_BUCKET),
        r"\$\{\{\s*env\.RAW_BUCKET\s*\}\}",
    ]

    # Split by occurrences of the gcloud subcommand so each block covers
    # one add-iam-policy-binding call (handles multi-line commands with \).
    blocks = re.split(
        r"(?=gcloud\s+storage\s+buckets\s+add-iam-policy-binding)", content
    )
    for block in blocks:
        if not re.search(
            r"gcloud\s+storage\s+buckets\s+add-iam-policy-binding", block
        ):
            continue
        has_viewer = _OBJECT_VIEWER_ROLE in block
        has_ci_sa = any(re.search(p, block) for p in ci_sa_patterns)
        has_bucket = any(re.search(p, block) for p in bucket_patterns)
        if has_viewer and has_ci_sa and has_bucket:
            return True
    return False


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestSetupShGrantsCiSaObjectViewer(unittest.TestCase):
    """infra/setup.sh must grant objectViewer to the CI SA on raw-uploads."""

    def setUp(self) -> None:
        with open(SETUP_SH, "r") as fh:
            self.content = fh.read()

    def test_setup_sh_grants_object_viewer_to_ci_sa_on_raw_bucket(self) -> None:
        """infra/setup.sh must add roles/storage.objectViewer for the CI SA.

        Without this binding the CI SA lacks ``storage.objects.get`` and all
        read operations (``blob.exists()``, ``download_as_bytes()``) return
        HTTP 403 Forbidden.
        """
        found = _has_object_viewer_for_ci_sa(self.content)
        self.assertTrue(
            found,
            f"infra/setup.sh does not grant '{_OBJECT_VIEWER_ROLE}' to the "
            f"CI SA ('{_CI_SA_SHORT}') on gs://{_RAW_BUCKET}. "
            "Add a 'gcloud storage buckets add-iam-policy-binding' step "
            "with --member=serviceAccount:${CI_SA_EMAIL} "
            f"--role={_OBJECT_VIEWER_ROLE} targeting the raw-uploads bucket.",
        )


class TestProvisionWorkflowGrantsCiSaObjectViewer(unittest.TestCase):
    """provision-gcs-buckets.yml must grant objectViewer to the CI SA."""

    def setUp(self) -> None:
        with open(PROVISION_YML, "r") as fh:
            self.content = fh.read()

    def test_workflow_grants_object_viewer_to_ci_sa_on_raw_bucket(self) -> None:
        """.github/workflows/provision-gcs-buckets.yml must add objectViewer.

        The CI SA must receive ``roles/storage.objectViewer`` on the raw-uploads
        bucket so it can download objects during integration tests (MYTUBE-300).
        """
        found = _has_object_viewer_for_ci_sa(self.content)
        self.assertTrue(
            found,
            f"provision-gcs-buckets.yml does not grant '{_OBJECT_VIEWER_ROLE}' "
            f"to the CI SA ('{_CI_SA_SHORT}') on gs://{_RAW_BUCKET}. "
            "Add a step: "
            "'gcloud storage buckets add-iam-policy-binding gs://${{ env.RAW_BUCKET }} "
            "--member=serviceAccount:${CI_SA_EMAIL} "
            f"--role={_OBJECT_VIEWER_ROLE}'.",
        )


class TestCiSaObjectViewerLiveIam(unittest.TestCase):
    """Optional integration test — verifies the live IAM policy on GCP.

    Skipped automatically when GCP_PROJECT_ID is not set, so it does not
    block CI pipelines that run without GCP credentials.
    """

    @classmethod
    def setUpClass(cls) -> None:
        import pytest
        config = GcpConfig()
        if not config.project_id:
            raise unittest.SkipTest(
                "GCP_PROJECT_ID is not set — skipping live IAM check. "
                "Set GCP_PROJECT_ID and ensure gcloud is authenticated to run."
            )
        cls.config = config

    def test_ci_sa_has_object_viewer_on_raw_bucket(self) -> None:
        """Live check: CI SA must have roles/storage.objectViewer on raw-uploads.

        Reads the actual GCS bucket IAM policy via gcloud and asserts that
        the binding is present.  Fails if the provisioning workflow has not
        been (re-)run with the objectViewer grant applied.
        """
        from testing.components.gcp.gcp_iam_service import GcpIamService

        iam = GcpIamService(config=self.config)
        bindings = iam.get_bucket_bindings(self.config.raw_bucket)
        ci_sa_email = (
            f"{_CI_SA_SHORT}@{self.config.project_id}.iam.gserviceaccount.com"
        )
        member = f"serviceAccount:{ci_sa_email}"
        has_role = iam.member_has_role(bindings, member, _OBJECT_VIEWER_ROLE)
        self.assertTrue(
            has_role,
            f"CI SA '{ci_sa_email}' does not have '{_OBJECT_VIEWER_ROLE}' "
            f"on gs://{self.config.raw_bucket}. "
            "Re-run the provision-gcs-buckets.yml workflow to apply the "
            "missing IAM binding.",
        )


if __name__ == "__main__":
    unittest.main()
