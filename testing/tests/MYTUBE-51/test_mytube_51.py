"""
MYTUBE-51: Verify Cloud Run IAM permissions — Service Account has restricted
read/write access.

Verifies that the Service Account used by the mytube-transcoder Cloud Run Job
has the minimal required IAM permissions:
 - roles/storage.objectViewer  on gs://mytube-raw-uploads
 - roles/storage.objectCreator on gs://mytube-hls-output

And no broader administrative roles on the buckets beyond what is required.

Prerequisites:
 - gcloud CLI authenticated with a principal that can read IAM policies
 - GCP_PROJECT_ID environment variable set

Environment variables:
 - GCP_PROJECT_ID: GCP project ID (required)
 - GCP_REGION: GCP region (default: us-central1)
"""
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RAW_BUCKET = "mytube-raw-uploads"
HLS_BUCKET = "mytube-hls-output"
JOB_NAME = "mytube-transcoder"
SA_SHORT_NAME = "mytube-transcoder"

REQUIRED_RAW_ROLE = "roles/storage.objectViewer"
REQUIRED_HLS_ROLE = "roles/storage.objectCreator"

OVERLY_BROAD_ROLES = {
    "roles/storage.admin",
    "roles/storage.objectAdmin",
    "roles/editor",
    "roles/owner",
    "roles/storage.legacyBucketOwner",
    "roles/storage.legacyBucketWriter",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_gcloud(*args: str) -> subprocess.CompletedProcess:
    """Run a gcloud command and return the CompletedProcess result."""
    cmd = ["gcloud", *args]
    return subprocess.run(cmd, capture_output=True, text=True)


def _require_project() -> str:
    """Return GCP_PROJECT_ID or skip the test if it is not set."""
    project = os.environ.get("GCP_PROJECT_ID", "").strip()
    if not project:
        pytest.skip("GCP_PROJECT_ID environment variable is not set — skipping infrastructure test")
    return project


def _get_service_account_email(project: str) -> str:
    return f"{SA_SHORT_NAME}@{project}.iam.gserviceaccount.com"


def _get_bucket_iam_bindings(bucket: str, project: str) -> list[dict]:
    """
    Return the IAM bindings for a GCS bucket.

    Returns a list of dicts: [{"role": "...", "members": ["serviceAccount:...", ...]}, ...]
    """
    result = _run_gcloud(
        "storage", "buckets", "get-iam-policy",
        f"gs://{bucket}",
        "--project", project,
        "--format", "json",
    )
    if result.returncode != 0:
        pytest.fail(
            f"Failed to retrieve IAM policy for gs://{bucket}.\n"
            f"stderr: {result.stderr.strip()}"
        )
    policy = json.loads(result.stdout)
    return policy.get("bindings", [])


def _get_cloud_run_job_service_account(job_name: str, region: str, project: str) -> str:
    """
    Return the full service account email attached to a Cloud Run Job.
    """
    result = _run_gcloud(
        "run", "jobs", "describe", job_name,
        "--region", region,
        "--project", project,
        "--format", "json",
    )
    if result.returncode != 0:
        pytest.fail(
            f"Failed to describe Cloud Run Job '{job_name}'.\n"
            f"stderr: {result.stderr.strip()}"
        )
    job_config = json.loads(result.stdout)
    # Path: spec.template.spec.serviceAccountName
    try:
        sa = (
            job_config["spec"]["template"]["spec"]["serviceAccountName"]
        )
    except KeyError:
        pytest.fail(
            f"Could not find serviceAccountName in Cloud Run Job spec.\n"
            f"Job config keys: {list(job_config.keys())}"
        )
    # Normalise: short name → full email
    if "@" not in sa:
        sa = f"{sa}@{project}.iam.gserviceaccount.com"
    return sa


def _member_has_role(bindings: list[dict], member: str, role: str) -> bool:
    """Return True if `member` is bound to `role` in the given IAM bindings."""
    for binding in bindings:
        if binding.get("role") == role:
            members = binding.get("members", [])
            if member in members:
                return True
    return False


def _member_has_any_role(bindings: list[dict], member: str, roles: set[str]) -> list[str]:
    """Return the subset of `roles` that `member` is bound to (should be empty)."""
    found = []
    for binding in bindings:
        role = binding.get("role", "")
        if role in roles and member in binding.get("members", []):
            found.append(role)
    return found


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def project() -> str:
    return _require_project()


@pytest.fixture(scope="module")
def region() -> str:
    return os.environ.get("GCP_REGION", "us-central1")


@pytest.fixture(scope="module")
def service_account_email(project: str, region: str) -> str:
    """Retrieve and return the SA email from the Cloud Run Job definition."""
    return _get_cloud_run_job_service_account(JOB_NAME, region, project)


@pytest.fixture(scope="module")
def sa_member(service_account_email: str) -> str:
    return f"serviceAccount:{service_account_email}"


@pytest.fixture(scope="module")
def raw_bucket_bindings(project: str) -> list[dict]:
    return _get_bucket_iam_bindings(RAW_BUCKET, project)


@pytest.fixture(scope="module")
def hls_bucket_bindings(project: str) -> list[dict]:
    return _get_bucket_iam_bindings(HLS_BUCKET, project)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCloudRunJobServiceAccount:
    """Step 1 — Verify the SA assigned to the mytube-transcoder Cloud Run Job."""

    def test_service_account_is_mytube_transcoder(
        self, service_account_email: str, project: str
    ):
        """The Cloud Run Job must use the mytube-transcoder service account."""
        expected_email = _get_service_account_email(project)
        assert service_account_email == expected_email, (
            f"Expected service account '{expected_email}', "
            f"but Cloud Run Job uses '{service_account_email}'"
        )


class TestRawBucketPermissions:
    """Step 2 — Verify objectViewer permission on mytube-raw-uploads."""

    def test_sa_has_object_viewer_on_raw_bucket(
        self, raw_bucket_bindings: list[dict], sa_member: str
    ):
        """SA must have roles/storage.objectViewer on the raw uploads bucket."""
        has_role = _member_has_role(raw_bucket_bindings, sa_member, REQUIRED_RAW_ROLE)
        assert has_role, (
            f"Expected '{sa_member}' to have '{REQUIRED_RAW_ROLE}' "
            f"on gs://{RAW_BUCKET}, but the binding was not found.\n"
            f"Current bindings: {raw_bucket_bindings}"
        )

    def test_sa_has_no_overly_broad_roles_on_raw_bucket(
        self, raw_bucket_bindings: list[dict], sa_member: str
    ):
        """SA must NOT have administrative/write roles on the raw uploads bucket."""
        extra_roles = _member_has_any_role(raw_bucket_bindings, sa_member, OVERLY_BROAD_ROLES)
        assert not extra_roles, (
            f"SA '{sa_member}' has unexpected broad roles on gs://{RAW_BUCKET}: "
            f"{extra_roles}. Only '{REQUIRED_RAW_ROLE}' should be granted."
        )


class TestHlsBucketPermissions:
    """Step 3 — Verify objectCreator permission on mytube-hls-output."""

    def test_sa_has_object_creator_on_hls_bucket(
        self, hls_bucket_bindings: list[dict], sa_member: str
    ):
        """SA must have roles/storage.objectCreator on the HLS output bucket."""
        has_role = _member_has_role(hls_bucket_bindings, sa_member, REQUIRED_HLS_ROLE)
        assert has_role, (
            f"Expected '{sa_member}' to have '{REQUIRED_HLS_ROLE}' "
            f"on gs://{HLS_BUCKET}, but the binding was not found.\n"
            f"Current bindings: {hls_bucket_bindings}"
        )

    def test_sa_has_no_overly_broad_roles_on_hls_bucket(
        self, hls_bucket_bindings: list[dict], sa_member: str
    ):
        """SA must NOT have administrative roles on the HLS output bucket."""
        extra_roles = _member_has_any_role(hls_bucket_bindings, sa_member, OVERLY_BROAD_ROLES)
        assert not extra_roles, (
            f"SA '{sa_member}' has unexpected broad roles on gs://{HLS_BUCKET}: "
            f"{extra_roles}. Only '{REQUIRED_HLS_ROLE}' should be granted."
        )
