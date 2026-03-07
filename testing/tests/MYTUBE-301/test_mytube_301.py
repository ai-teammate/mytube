"""
MYTUBE-301: Update bucket IAM policy with public member — operation rejected
by Public Access Prevention.

Verifies that Public Access Prevention (PAP) actively blocks the addition of
public IAM permissions to the ``mytube-raw-uploads`` bucket by attempting to
add ``allUsers`` with ``roles/storage.objectViewer`` and asserting that the
operation is rejected with an appropriate error message.

Prerequisites:
  - GCP_PROJECT_ID env var set to the target GCP project (default: ai-native-478811).
  - ``gcloud`` CLI authenticated via ADC or GOOGLE_APPLICATION_CREDENTIALS with
    at least ``storage.buckets.setIamPolicy`` permission.
"""
import os
import sys
import subprocess
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcp_config import GcpConfig
from testing.components.gcp.gcp_iam_service import GcpIamService

BUCKET_NAME = "mytube-raw-uploads"
PUBLIC_MEMBER = "allUsers"
PUBLIC_ROLE = "roles/storage.objectViewer"

# Keywords expected in the error message when PAP rejects the operation.
PAP_ERROR_KEYWORDS = [
    "public access prevention",
    "allUsers",
]


@pytest.fixture(scope="module")
def gcp_config() -> GcpConfig:
    config = GcpConfig()
    if not config.project_id:
        pytest.skip(
            "GCP_PROJECT_ID is not set — skipping GCP IAM test. "
            "Set GCP_PROJECT_ID and ensure gcloud is authenticated."
        )
    return config


@pytest.fixture(scope="module")
def iam_service(gcp_config: GcpConfig) -> GcpIamService:
    return GcpIamService(config=gcp_config)


class TestPublicAccessPreventionBlocksIAMBinding:
    """PAP must reject any attempt to grant allUsers access to the bucket."""

    def test_add_public_member_is_rejected(self, gcp_config: GcpConfig):
        """Attempt to add allUsers/objectViewer must fail with a PAP error.

        Runs `gcloud storage buckets add-iam-policy-binding` and asserts:
          - The command exits with a non-zero status code.
          - The stderr contains keywords indicating PAP enforcement.
        """
        result = subprocess.run(
            [
                "gcloud", "storage", "buckets", "add-iam-policy-binding",
                f"gs://{BUCKET_NAME}",
                f"--member={PUBLIC_MEMBER}",
                f"--role={PUBLIC_ROLE}",
                "--project", gcp_config.project_id,
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0, (
            f"Expected gcloud to reject adding '{PUBLIC_MEMBER}' with "
            f"'{PUBLIC_ROLE}' to gs://{BUCKET_NAME} because Public Access "
            "Prevention is enforced, but the command succeeded (exit code 0). "
            "This means PAP is NOT enforced — the bucket is publicly accessible."
        )

        error_output = (result.stderr + result.stdout).lower()
        missing_keywords = [
            kw for kw in PAP_ERROR_KEYWORDS if kw.lower() not in error_output
        ]
        assert not missing_keywords, (
            f"Command failed as expected (exit code {result.returncode}), but "
            f"the error message did not mention Public Access Prevention. "
            f"Missing keywords: {missing_keywords}.\n"
            f"Actual stderr:\n{result.stderr.strip()}"
        )

    def test_allUsers_not_in_existing_bindings(self, iam_service: GcpIamService):
        """Cross-check: allUsers must not appear in any existing IAM binding.

        Reads the current IAM policy and asserts that ``allUsers`` is not
        already bound to any role — confirming the bucket was never made public.
        """
        bindings = iam_service.get_bucket_bindings(BUCKET_NAME)
        for binding in bindings:
            members = binding.get("members", [])
            assert PUBLIC_MEMBER not in members, (
                f"Found '{PUBLIC_MEMBER}' already bound to role "
                f"'{binding.get('role')}' on gs://{BUCKET_NAME}. "
                "The bucket has been made publicly accessible — "
                "this is a critical security misconfiguration."
            )
