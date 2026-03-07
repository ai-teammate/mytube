"""
MYTUBE-310: MP4 upload to raw bucket — transcoding Cloud Run job triggered automatically.

Objective
---------
Verify that granting ``roles/storage.objectCreator`` to the CI service account
allows the end-to-end integration to function: uploading an MP4 to the
``mytube-raw-uploads`` bucket must automatically trigger a new execution of the
``mytube-transcoder`` Cloud Run Job via Eventarc.

Preconditions
-------------
The CI service account has ``roles/storage.objectCreator`` on
``gs://mytube-raw-uploads``.

Test Steps
----------
1. Verify via IAM policy that the CI service account is bound to
   ``roles/storage.objectCreator`` on ``gs://mytube-raw-uploads``.
2. Record the list of existing Cloud Run Job executions for ``mytube-transcoder``
   (baseline snapshot taken immediately before the upload).
3. Upload a minimal valid MP4 file to ``gs://mytube-raw-uploads`` using the CI
   service account credentials.
4. Poll ``EventarcService.list_cloud_run_job_executions`` for the
   ``mytube-transcoder`` job until a new execution appears (created after the
   upload timestamp), or until ``CLOUD_RUN_TRIGGER_WAIT_SECONDS`` elapses.

Expected Result
---------------
A new Cloud Run Job execution for ``mytube-transcoder`` is found with a
``createTime`` after the upload timestamp, confirming that the Eventarc trigger
fired and that the ``roles/storage.objectCreator`` permission fix unblocks the
integration pipeline.

Environment Variables
---------------------
- GOOGLE_APPLICATION_CREDENTIALS   Path to the CI service account JSON key.
                                    Must be set explicitly — no default fallback.
- GCP_PROJECT_ID                   GCP project ID (default: ``ai-native-478811``).
- GCP_REGION                       GCP region (default: ``us-central1``).
- GCS_RAW_UPLOADS_BUCKET           Bucket name (default: ``mytube-raw-uploads``).
- GCP_TRANSCODER_JOB               Cloud Run Job name (default: ``mytube-transcoder``).
- CLOUD_RUN_TRIGGER_WAIT_SECONDS   How long to poll for the new execution
                                   (default: ``120``).

Architecture Notes
------------------
- ``GcpIamService`` is used for all IAM policy queries.
- ``GCSBucketService`` is used for the GCS upload and cleanup.
- ``EventarcService.list_cloud_run_job_executions`` is used to list executions.
- ``poll_until`` from ``testing.core.utils.polling`` drives the polling loop.
- All GCP credentials are injected via constructor; never hard-coded.
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcp_config import GcpConfig
from testing.core.config.gcs_config import GCSConfig
from testing.core.utils.polling import poll_until
from testing.components.gcp.gcp_iam_service import GcpIamService
from testing.components.services.eventarc_service import EventarcService
from testing.components.services.gcs_bucket_service import GCSBucketService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

# Minimal valid ftyp+mdat MP4 (ISO base media file format box header).
# This 32-byte sequence is enough to create a file with a valid MP4 container
# header so the filename is recognised as MP4 by the Eventarc handler.
_MINIMAL_MP4_BYTES = (
    b"\x00\x00\x00\x20"   # box size = 32
    b"ftyp"               # box type = ftyp
    b"isom"               # major brand
    b"\x00\x00\x02\x00"   # minor version
    b"isom"               # compatible brand 1
    b"iso2"               # compatible brand 2
    b"avc1"               # compatible brand 3
    b"mp41"               # compatible brand 4
)

TRIGGER_WAIT_SECONDS = int(os.getenv("CLOUD_RUN_TRIGGER_WAIT_SECONDS", "120"))
POLL_INTERVAL_SECONDS = 10


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcp_config() -> GcpConfig:
    config = GcpConfig()
    if not config.project_id:
        config.project_id = "ai-native-478811"
    if not config.region:
        config.region = "us-central1"
    return config


@pytest.fixture(scope="module")
def gcs_config(gcp_config: GcpConfig) -> GCSConfig:
    config = GCSConfig()
    if not config.project_id:
        config.project_id = gcp_config.project_id
    return config


@pytest.fixture(scope="module")
def sa_credentials():
    """Load CI service account credentials.

    Skips the entire module if the credentials file is absent or if
    google-auth is not installed.
    """
    try:
        from google.oauth2 import service_account as sa_module
    except ImportError:
        pytest.skip("google-auth is not installed — cannot load SA credentials.")

    if not os.path.isfile(CREDENTIALS_PATH):
        pytest.skip(
            f"Service account key not found at {CREDENTIALS_PATH!r}. "
            "Set GOOGLE_APPLICATION_CREDENTIALS to a key file with "
            "roles/storage.objectCreator on the bucket."
        )

    return sa_module.Credentials.from_service_account_file(CREDENTIALS_PATH)


@pytest.fixture(scope="module")
def sa_email(sa_credentials) -> str:
    """Return the service account email from the loaded credentials."""
    return sa_credentials.service_account_email


@pytest.fixture(scope="module")
def storage_client(sa_credentials, gcp_config):
    """Authenticated GCS client for GCSBucketService."""
    try:
        from google.cloud import storage as gcs_storage
    except ImportError:
        pytest.skip("google-cloud-storage is not installed.")

    return gcs_storage.Client(
        project=gcp_config.project_id,
        credentials=sa_credentials,
    )


@pytest.fixture(scope="module")
def gcs_bucket_service(storage_client, gcs_config) -> GCSBucketService:
    return GCSBucketService(config=gcs_config, storage_client=storage_client)


@pytest.fixture(scope="module")
def gcp_iam_service(gcp_config) -> GcpIamService:
    return GcpIamService(config=gcp_config)


@pytest.fixture(scope="module")
def eventarc_service(gcp_config) -> EventarcService:
    return EventarcService(project=gcp_config.project_id, region=gcp_config.region)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_create_time(execution: dict) -> datetime.datetime:
    """Parse the createTime field from a Cloud Run execution dict (UTC)."""
    raw = execution.get("metadata", {}).get("creationTimestamp", "") or \
          execution.get("createTime", "")
    if not raw:
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    # createTime can be RFC3339 with Z or +00:00
    raw = raw.replace("Z", "+00:00")
    try:
        return datetime.datetime.fromisoformat(raw)
    except ValueError:
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMP4UploadTriggersCloudRunJob:
    """MYTUBE-310: MP4 upload to raw bucket triggers transcoder Cloud Run Job."""

    def test_ci_sa_has_object_creator_role(
        self,
        gcp_iam_service: GcpIamService,
        gcs_config: GCSConfig,
        sa_email: str,
    ) -> None:
        """Step 1: CI service account must be bound to roles/storage.objectCreator
        on the raw-uploads bucket.

        This is the precondition described in the ticket: the permission must be
        present or the upload in Step 2 will fail and no Eventarc event fires.
        """
        bucket_name = gcs_config.raw_uploads_bucket
        bindings = gcp_iam_service.get_bucket_bindings(bucket_name)

        member = f"serviceAccount:{sa_email}"
        has_role = gcp_iam_service.member_has_role(
            bindings, member, "roles/storage.objectCreator"
        )
        assert has_role, (
            f"CI service account '{sa_email}' does NOT have "
            f"'roles/storage.objectCreator' on gs://{bucket_name}.\n"
            f"Current bindings: {json.dumps(bindings, indent=2)}\n\n"
            "Grant the role with:\n"
            f"  gcloud storage buckets add-iam-policy-binding gs://{bucket_name} "
            f"  --member=serviceAccount:{sa_email} "
            "  --role=roles/storage.objectCreator"
        )

    def test_upload_mp4_triggers_cloud_run_execution(
        self,
        gcp_config: GcpConfig,
        gcs_bucket_service: GCSBucketService,
        gcs_config: GCSConfig,
        eventarc_service: EventarcService,
    ) -> None:
        """Steps 2–4: Upload MP4 → wait for new Cloud Run Job execution.

        Procedure:
        1. Snapshot existing execution IDs (baseline).
        2. Record upload timestamp.
        3. Upload minimal MP4 to ``raw/<uuid>.mp4`` in the raw-uploads bucket.
        4. Use ``poll_until`` to call
           ``EventarcService.list_cloud_run_job_executions`` at
           ``POLL_INTERVAL_SECONDS`` intervals for up to
           ``CLOUD_RUN_TRIGGER_WAIT_SECONDS`` until an execution whose
           createTime is after the upload timestamp appears.

        A new execution appearing after the upload confirms that Eventarc fired
        and the ``roles/storage.objectCreator`` fix allows the pipeline to proceed.
        """
        job_name = gcp_config.transcoder_job
        bucket_name = gcs_config.raw_uploads_bucket

        # --- baseline snapshot -------------------------------------------
        baseline_executions = eventarc_service.list_cloud_run_job_executions(job_name)
        baseline_ids: set[str] = set()
        for ex in baseline_executions:
            name = ex.get("metadata", {}).get("name", "") or ex.get("name", "")
            if name:
                baseline_ids.add(name)

        # --- upload timestamp --------------------------------------------
        upload_time = datetime.datetime.now(datetime.timezone.utc)

        # --- upload minimal MP4 -----------------------------------------
        # Object name must match the handler's pattern: raw/<uuid>.mp4
        video_id = str(uuid.uuid4())
        object_name = f"raw/{video_id}.mp4"

        gcs_bucket_service.upload_object(
            object_name,
            _MINIMAL_MP4_BYTES,
            content_type="video/mp4",
        )

        # --- poll for new execution via component layer ------------------
        attempts = 0

        def _check_for_new_execution():
            nonlocal attempts
            attempts += 1
            for ex in eventarc_service.list_cloud_run_job_executions(job_name):
                name = ex.get("metadata", {}).get("name", "") or ex.get("name", "")
                created = _parse_create_time(ex)
                if name and name not in baseline_ids and created >= upload_time:
                    return (name, created)
            return None

        try:
            result = poll_until(
                _check_for_new_execution,
                timeout=TRIGGER_WAIT_SECONDS,
                interval=POLL_INTERVAL_SECONDS,
            )
        finally:
            # Cleanup: delete the uploaded test object regardless of outcome.
            gcs_bucket_service.delete_object(object_name)

        assert result is not None, (
            f"No new Cloud Run Job execution for '{job_name}' was detected "
            f"within {TRIGGER_WAIT_SECONDS}s after uploading "
            f"gs://{bucket_name}/{object_name} at {upload_time.isoformat()}.\n\n"
            f"Polling attempts: {attempts} (interval: {POLL_INTERVAL_SECONDS}s)\n"
            f"Baseline execution IDs ({len(baseline_ids)}): "
            f"{sorted(baseline_ids)[:5]}{'...' if len(baseline_ids) > 5 else ''}\n\n"
            "Possible causes:\n"
            "  1. The Eventarc trigger 'mytube-gcs-finalize' is not configured or "
            "     is not routing to the Cloud Run trigger service.\n"
            "  2. The 'mytube-transcoder-trigger' Cloud Run Service failed to "
            "     invoke the 'mytube-transcoder' job (check its logs).\n"
            "  3. The uploaded object name did not match the handler's expected "
            f"     pattern (expected: raw/<uuid>.mp4, uploaded: {object_name}).\n"
            "  4. The Eventarc delivery itself is delayed beyond the polling window.\n"
            f"  Verify manually: gcloud run jobs executions list "
            f"--job={job_name} --region={gcp_config.region} "
            f"--project={gcp_config.project_id}"
        )

        new_execution_name, new_execution_time = result

        # Extra assertion: log the found execution for traceability.
        assert new_execution_name, (
            "Found execution without a name — unexpected response format from "
            "gcloud run jobs executions list."
        )
        assert new_execution_time >= upload_time, (
            f"New execution '{new_execution_name}' has createTime "
            f"{new_execution_time.isoformat()} which is before the upload at "
            f"{upload_time.isoformat()}. This suggests a stale execution was "
            "incorrectly matched — check the execution list."
        )
