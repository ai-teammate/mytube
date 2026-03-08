"""
MYTUBE-377: Verify Service Account IAM — delete permissions granted on GCS buckets.

Objective
---------
Ensure that the Service Accounts for the API server and the Transcoder Cloud Run Job
have the necessary IAM permissions to perform object deletion on both GCS buckets.

Steps
-----
1. Identify the Service Account (SA) for the API server (Cloud Run Service: mytube-api)
   and the Transcoder Cloud Run Job (mytube-transcoder).
2. Check IAM policy for the ``mytube-raw-uploads`` bucket — both SAs must have a role
   that includes ``storage.objects.delete``.
3. Check IAM policy for the ``mytube-hls-output`` bucket — both SAs must have a role
   that includes ``storage.objects.delete``.

Expected Result
---------------
Both SAs must have roles that include ``storage.objects.delete`` permission
(e.g., ``roles/storage.objectUser`` or ``roles/storage.objectAdmin``) for the
relevant buckets so that the cleanup logic does not fail with Access Denied.

Environment Variables
---------------------
- GCP_PROJECT_ID     : GCP project ID (required; default: ai-native-478811 if not set)
- GCP_REGION         : GCP region (default: us-central1)
- GCP_RAW_BUCKET     : Raw uploads bucket name (default: mytube-raw-uploads)
- GCP_HLS_BUCKET     : HLS output bucket name (default: mytube-hls-output)
- GCP_TRANSCODER_JOB : Cloud Run Job name for the transcoder (default: mytube-transcoder)
- GCP_API_SERVICE    : Cloud Run Service name for the API server (default: mytube-api)

Architecture Notes
------------------
- ``GcpIamService`` is used for all IAM and Cloud Run metadata queries.
- ``GcpConfig`` centralises all environment-variable access.
- Tests are arranged by SA × bucket to produce granular failure messages.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcp_config import GcpConfig
from testing.components.gcp.gcp_iam_service import GcpIamService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Roles that include the storage.objects.delete permission.
# https://cloud.google.com/storage/docs/access-control/iam-roles
_DELETE_CAPABLE_ROLES: frozenset[str] = frozenset({
    "roles/storage.objectAdmin",
    "roles/storage.objectUser",
    "roles/storage.admin",
    "roles/storage.legacyObjectOwner",
    "roles/storage.legacyBucketOwner",
})

_API_SERVICE_NAME: str = os.environ.get("GCP_API_SERVICE", "mytube-api")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcp_config() -> GcpConfig:
    config = GcpConfig()
    if not config.project_id:
        config.project_id = "ai-native-478811"
    return config


@pytest.fixture(scope="module")
def iam_service(gcp_config: GcpConfig) -> GcpIamService:
    return GcpIamService(config=gcp_config)


@pytest.fixture(scope="module")
def transcoder_sa_email(iam_service: GcpIamService, gcp_config: GcpConfig) -> str:
    """Service account email used by the mytube-transcoder Cloud Run Job."""
    return iam_service.get_cloud_run_job_sa(gcp_config.transcoder_job)


@pytest.fixture(scope="module")
def api_server_sa_email(iam_service: GcpIamService) -> str:
    """Service account email used by the mytube-api Cloud Run Service."""
    return iam_service.get_cloud_run_service_sa(_API_SERVICE_NAME)


@pytest.fixture(scope="module")
def raw_bucket_bindings(iam_service: GcpIamService, gcp_config: GcpConfig) -> list[dict]:
    """IAM bindings for the mytube-raw-uploads bucket."""
    return iam_service.get_bucket_bindings(gcp_config.raw_bucket)


@pytest.fixture(scope="module")
def hls_bucket_bindings(iam_service: GcpIamService, gcp_config: GcpConfig) -> list[dict]:
    """IAM bindings for the mytube-hls-output bucket."""
    return iam_service.get_bucket_bindings(gcp_config.hls_bucket)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_delete_permission(
    bindings: list[dict],
    member: str,
    bucket_name: str,
) -> tuple[bool, list[str]]:
    """Return (has_permission, granted_roles).

    Checks whether *member* holds any role that includes storage.objects.delete
    in the given *bindings*. Returns the matching roles for diagnostic messages.
    """
    granted: list[str] = []
    for binding in bindings:
        role = binding.get("role", "")
        members = binding.get("members", [])
        if member in members and role in _DELETE_CAPABLE_ROLES:
            granted.append(role)
    return bool(granted), granted


def _format_bindings(bindings: list[dict]) -> str:
    """Format IAM bindings as a compact JSON string for error messages."""
    return json.dumps(bindings, indent=2)


# ---------------------------------------------------------------------------
# Tests — Step 1: Identify service accounts
# ---------------------------------------------------------------------------


class TestIdentifyServiceAccounts:
    """Step 1: Confirm that both SAs can be discovered from the live GCP environment."""

    def test_transcoder_sa_can_be_identified(
        self,
        transcoder_sa_email: str,
        gcp_config: GcpConfig,
    ) -> None:
        """The mytube-transcoder Cloud Run Job must declare an explicit service account."""
        assert transcoder_sa_email, (
            f"Could not retrieve the service account for Cloud Run Job "
            f"'{gcp_config.transcoder_job}' in project '{gcp_config.project_id}'. "
            "Ensure the job exists and gcloud is authenticated."
        )
        assert "@" in transcoder_sa_email, (
            f"The retrieved service account '{transcoder_sa_email}' does not look "
            "like a valid email address. Expected format: <name>@<project>.iam.gserviceaccount.com"
        )

    def test_api_server_sa_can_be_identified(
        self,
        api_server_sa_email: str,
        gcp_config: GcpConfig,
    ) -> None:
        """The mytube-api Cloud Run Service must have a resolvable service account."""
        assert api_server_sa_email, (
            f"Could not retrieve the service account for Cloud Run Service "
            f"'{_API_SERVICE_NAME}' in project '{gcp_config.project_id}'. "
            "Ensure the service exists and gcloud is authenticated."
        )
        assert "@" in api_server_sa_email, (
            f"The retrieved service account '{api_server_sa_email}' does not look "
            "like a valid email address."
        )


# ---------------------------------------------------------------------------
# Tests — Step 2: mytube-raw-uploads bucket delete permissions
# ---------------------------------------------------------------------------


class TestDeletePermissionsOnRawUploadsBucket:
    """Step 2: Both SAs must have storage.objects.delete on gs://mytube-raw-uploads."""

    def test_transcoder_sa_has_delete_on_raw_bucket(
        self,
        transcoder_sa_email: str,
        raw_bucket_bindings: list[dict],
        gcp_config: GcpConfig,
    ) -> None:
        """mytube-transcoder SA must hold a delete-capable role on the raw-uploads bucket.

        Required for cleanup logic: after the transcoder processes a video, the raw
        source object in the uploads bucket must be deletable to avoid storage leakage.
        """
        member = f"serviceAccount:{transcoder_sa_email}"
        has_perm, granted = _has_delete_permission(
            raw_bucket_bindings, member, gcp_config.raw_bucket
        )
        assert has_perm, (
            f"Service account '{transcoder_sa_email}' does NOT have any role that "
            f"includes storage.objects.delete on gs://{gcp_config.raw_bucket}.\n\n"
            f"Roles checked: {sorted(_DELETE_CAPABLE_ROLES)}\n\n"
            f"Current bucket IAM bindings:\n{_format_bindings(raw_bucket_bindings)}\n\n"
            f"Remediation — grant one of the required roles, for example:\n"
            f"  gcloud storage buckets add-iam-policy-binding gs://{gcp_config.raw_bucket} \\\n"
            f"    --member=serviceAccount:{transcoder_sa_email} \\\n"
            f"    --role=roles/storage.objectUser \\\n"
            f"    --project={gcp_config.project_id}"
        )

    def test_api_server_sa_has_delete_on_raw_bucket(
        self,
        api_server_sa_email: str,
        raw_bucket_bindings: list[dict],
        gcp_config: GcpConfig,
    ) -> None:
        """mytube-api SA must hold a delete-capable role on the raw-uploads bucket.

        Required for cleanup logic: the API server must be able to delete objects
        (e.g., to remove failed or cancelled uploads) without Access Denied errors.
        """
        member = f"serviceAccount:{api_server_sa_email}"
        has_perm, granted = _has_delete_permission(
            raw_bucket_bindings, member, gcp_config.raw_bucket
        )
        assert has_perm, (
            f"Service account '{api_server_sa_email}' (API server) does NOT have "
            f"any role that includes storage.objects.delete on "
            f"gs://{gcp_config.raw_bucket}.\n\n"
            f"Roles checked: {sorted(_DELETE_CAPABLE_ROLES)}\n\n"
            f"Current bucket IAM bindings:\n{_format_bindings(raw_bucket_bindings)}\n\n"
            f"Remediation — grant one of the required roles, for example:\n"
            f"  gcloud storage buckets add-iam-policy-binding gs://{gcp_config.raw_bucket} \\\n"
            f"    --member=serviceAccount:{api_server_sa_email} \\\n"
            f"    --role=roles/storage.objectUser \\\n"
            f"    --project={gcp_config.project_id}"
        )


# ---------------------------------------------------------------------------
# Tests — Step 3: mytube-hls-output bucket delete permissions
# ---------------------------------------------------------------------------


class TestDeletePermissionsOnHlsOutputBucket:
    """Step 3: Both SAs must have storage.objects.delete on gs://mytube-hls-output."""

    def test_transcoder_sa_has_delete_on_hls_bucket(
        self,
        transcoder_sa_email: str,
        hls_bucket_bindings: list[dict],
        gcp_config: GcpConfig,
    ) -> None:
        """mytube-transcoder SA must hold a delete-capable role on the HLS-output bucket.

        Required for re-transcoding or cleanup: if a video is re-processed, the
        transcoder must overwrite or delete existing HLS segments.
        """
        member = f"serviceAccount:{transcoder_sa_email}"
        has_perm, granted = _has_delete_permission(
            hls_bucket_bindings, member, gcp_config.hls_bucket
        )
        assert has_perm, (
            f"Service account '{transcoder_sa_email}' does NOT have any role that "
            f"includes storage.objects.delete on gs://{gcp_config.hls_bucket}.\n\n"
            f"Roles checked: {sorted(_DELETE_CAPABLE_ROLES)}\n\n"
            f"Current bucket IAM bindings:\n{_format_bindings(hls_bucket_bindings)}\n\n"
            f"Remediation — grant one of the required roles, for example:\n"
            f"  gcloud storage buckets add-iam-policy-binding gs://{gcp_config.hls_bucket} \\\n"
            f"    --member=serviceAccount:{transcoder_sa_email} \\\n"
            f"    --role=roles/storage.objectUser \\\n"
            f"    --project={gcp_config.project_id}"
        )

    def test_api_server_sa_has_delete_on_hls_bucket(
        self,
        api_server_sa_email: str,
        hls_bucket_bindings: list[dict],
        gcp_config: GcpConfig,
    ) -> None:
        """mytube-api SA must hold a delete-capable role on the HLS-output bucket.

        Required for cleanup logic: the API server must be able to delete HLS output
        objects when a video is deleted or re-uploaded, without Access Denied errors.
        """
        member = f"serviceAccount:{api_server_sa_email}"
        has_perm, granted = _has_delete_permission(
            hls_bucket_bindings, member, gcp_config.hls_bucket
        )
        assert has_perm, (
            f"Service account '{api_server_sa_email}' (API server) does NOT have "
            f"any role that includes storage.objects.delete on "
            f"gs://{gcp_config.hls_bucket}.\n\n"
            f"Roles checked: {sorted(_DELETE_CAPABLE_ROLES)}\n\n"
            f"Current bucket IAM bindings:\n{_format_bindings(hls_bucket_bindings)}\n\n"
            f"Remediation — grant one of the required roles, for example:\n"
            f"  gcloud storage buckets add-iam-policy-binding gs://{gcp_config.hls_bucket} \\\n"
            f"    --member=serviceAccount:{api_server_sa_email} \\\n"
            f"    --role=roles/storage.objectUser \\\n"
            f"    --project={gcp_config.project_id}"
        )
