"""
MYTUBE-376: Transcoder failure with CLEANUP_ON_TRANSCODE_FAILURE=false — artifacts retained.

Objective
---------
Verify that the transcoder cleanup logic respects the configuration flag to
disable object deletion on failure.  When CLEANUP_ON_TRANSCODE_FAILURE is set
to "false", partial HLS artifacts that exist in the output bucket at the time of
failure must NOT be deleted by the transcoder.

Preconditions
-------------
* Environment variable CLEANUP_ON_TRANSCODE_FAILURE is set to "false" (injected
  via the Cloud Run Job execute command for this test run).

Test Steps
----------
1. Pre-seed fake partial HLS artifacts under ``videos/{TEST_VIDEO_ID}/`` in the
   ``mytube-hls-output`` bucket to simulate files created by a partially
   completed transcoding run.
2. Trigger a transcoding Cloud Run Job that fails permanently:
   - Uses a non-existent RAW_OBJECT_PATH so the download step fails immediately.
   - Sets CLEANUP_ON_TRANSCODE_FAILURE=false.
3. The job exits with a non-zero exit code (permanent failure).
4. Check the ``mytube-hls-output`` bucket: the pre-seeded partial HLS artifacts
   under ``videos/{TEST_VIDEO_ID}/`` must still be present.

Expected Result
---------------
The job fails and exits, but the partial HLS artifacts in the GCS bucket are
retained (not deleted) because CLEANUP_ON_TRANSCODE_FAILURE=false.

Environment Variables
---------------------
- GOOGLE_APPLICATION_CREDENTIALS  Path to the CI service account JSON key.
                                   Required; test skipped if absent.
- GCP_PROJECT_ID                  GCP project ID (default: ai-native-478811).
- GCP_REGION                      GCP region (default: us-central1).
- GCP_HLS_BUCKET                  HLS output bucket (default: mytube-hls-output).
- GCP_RAW_BUCKET                  Raw uploads bucket (default: mytube-raw-uploads).
- GCP_TRANSCODER_JOB              Cloud Run Job name (default: mytube-transcoder).
- CDN_BASE_URL                    CDN base URL (default: https://cdn.example.com).
- TRANSCODER_FAILURE_WAIT_SECONDS How long (max) to wait for job failure confirmation
                                  (default: 300).

Architecture Notes
------------------
- ``HLSTranscoderService`` is used to execute the Cloud Run Job and list bucket
  objects; its ``run_transcoding_job`` method is called with a known-invalid
  raw object path and ``extra_env_vars={"CLEANUP_ON_TRANSCODE_FAILURE": "false"}``
  to force a permanent download failure while disabling cleanup.
- ``GCSService`` (google-cloud-storage) is used to pre-seed and verify the
  partial artifact files in the HLS bucket.
- All GCP credentials are injected via constructor; never hard-coded.
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcp_config import GcpConfig
from testing.components.services.hls_transcoder_service import (
    HLSTranscoderService,
    JobExecutionResult,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_PROJECT_ID = "ai-native-478811"

# An object path that is guaranteed not to exist; forces a download failure
# so the transcoder exits early (before generating any real HLS output).
_INVALID_RAW_OBJECT_PATH = "raw/mytube-376-nonexistent-file-that-will-never-exist.mp4"

# Simulated partial HLS artifacts pre-seeded into the HLS bucket to represent
# output from a previously started (but not completed) transcoding run.
_PARTIAL_ARTIFACT_NAMES = [
    "index.m3u8",
    "360p.m3u8",
    "seg-0000.ts",
]

_PARTIAL_ARTIFACT_CONTENT = b"#EXTM3U\n# partial HLS artifact - MYTUBE-376 test probe\n"

_FAILURE_WAIT_SECONDS = int(os.environ.get("TRANSCODER_FAILURE_WAIT_SECONDS", "300"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcp_config() -> GcpConfig:
    cfg = GcpConfig()
    if not cfg.project_id:
        cfg.project_id = _DEFAULT_PROJECT_ID
    return cfg


@pytest.fixture(scope="module")
def storage_client(gcp_config: GcpConfig):
    """Create an authenticated GCS client; skip if credentials are unavailable."""
    try:
        from google.cloud import storage as gcs_storage
        from google.auth.exceptions import DefaultCredentialsError
    except ImportError:
        pytest.skip("google-cloud-storage is not installed")

    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not creds_path or not os.path.isfile(creds_path):
        pytest.skip(
            "GOOGLE_APPLICATION_CREDENTIALS is not set or file not found — "
            "skipping MYTUBE-376 (requires GCS access)."
        )

    try:
        client = gcs_storage.Client(project=gcp_config.project_id)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"GCP credentials not available: {exc}")

    return client


@pytest.fixture(scope="module")
def transcoder_service(gcp_config: GcpConfig, storage_client) -> HLSTranscoderService:
    return HLSTranscoderService(config=gcp_config, storage_client=storage_client)


@pytest.fixture(scope="module")
def test_video_id() -> str:
    """A unique VIDEO_ID for this test run — ensures no collision with real data."""
    return f"mytube-376-test-{uuid.uuid4()}"


@pytest.fixture(scope="module")
def seeded_artifacts(gcp_config: GcpConfig, storage_client, test_video_id: str) -> list[str]:
    """
    Pre-seed fake partial HLS artifacts into ``mytube-hls-output`` bucket under
    ``videos/{test_video_id}/`` and yield the list of object names seeded.

    Teardown deletes the seeded artifacts (best-effort) so the bucket stays clean.
    """
    bucket = storage_client.bucket(gcp_config.hls_bucket)
    seeded: list[str] = []

    for artifact_name in _PARTIAL_ARTIFACT_NAMES:
        object_name = f"videos/{test_video_id}/{artifact_name}"
        blob = bucket.blob(object_name)
        blob.upload_from_string(_PARTIAL_ARTIFACT_CONTENT, content_type="application/octet-stream")
        seeded.append(object_name)

    yield seeded

    # Teardown: remove seeded artifacts regardless of test outcome.
    for object_name in seeded:
        try:
            bucket.blob(object_name).delete()
        except Exception:
            pass


@pytest.fixture(scope="module")
def failed_job_result(
    transcoder_service: HLSTranscoderService,
    test_video_id: str,
    seeded_artifacts,  # ensures artifacts are seeded before job runs
) -> JobExecutionResult:
    """
    Execute the Cloud Run Job in failure mode via HLSTranscoderService:
    - RAW_OBJECT_PATH points to a non-existent GCS object (causes download failure).
    - CLEANUP_ON_TRANSCODE_FAILURE=false (disables GCS cleanup on failure).
    """
    return transcoder_service.run_transcoding_job(
        video_id=test_video_id,
        raw_object_path=_INVALID_RAW_OBJECT_PATH,
        timeout_seconds=_FAILURE_WAIT_SECONDS,
        extra_env_vars={"CLEANUP_ON_TRANSCODE_FAILURE": "false"},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTranscoderCleanupDisabled:
    """
    MYTUBE-376 — When CLEANUP_ON_TRANSCODE_FAILURE=false and a transcoding job
    fails permanently, partial HLS artifacts in the output bucket must be retained.
    """

    # ---- Step 1: Verify pre-seeded artifacts exist before job runs --------

    def test_partial_artifacts_seeded_in_hls_bucket(
        self,
        transcoder_service: HLSTranscoderService,
        test_video_id: str,
        seeded_artifacts: list[str],
    ) -> None:
        """Step 1 — Partial HLS artifacts must be present in the bucket before the job runs."""
        objects = transcoder_service.list_output_objects(test_video_id)
        assert len(objects) > 0, (
            f"Expected pre-seeded artifacts under 'videos/{test_video_id}/' "
            f"but the prefix is empty.  Seeded: {seeded_artifacts}"
        )

    # ---- Step 2: Trigger a permanently failing transcoding job -----------

    def test_job_fails_permanently(
        self,
        failed_job_result: JobExecutionResult,
    ) -> None:
        """
        Step 2 — The Cloud Run Job must fail (non-zero exit code) when the
        raw object does not exist, confirming a permanent transcoding failure.
        """
        assert not failed_job_result.success, (
            "Expected the Cloud Run Job to fail because RAW_OBJECT_PATH points "
            f"to a non-existent GCS object ('{_INVALID_RAW_OBJECT_PATH}'), but "
            f"the job exited successfully (exit_code={failed_job_result.exit_code})."
        )
        assert failed_job_result.exit_code != 0 or failed_job_result.error_message, (
            "Job did not produce a non-zero exit code or error message. "
            f"stdout={failed_job_result.stdout!r} "
            f"stderr={failed_job_result.stderr!r}"
        )

    # ---- Step 3: Verify artifacts are retained in the HLS bucket ---------

    def test_partial_artifacts_retained_after_failure(
        self,
        gcp_config: GcpConfig,
        transcoder_service: HLSTranscoderService,
        test_video_id: str,
        seeded_artifacts: list[str],
        failed_job_result: JobExecutionResult,  # ensures job ran before this check
    ) -> None:
        """
        Step 3 — After the job fails with CLEANUP_ON_TRANSCODE_FAILURE=false,
        each pre-seeded partial HLS artifact must still exist in the bucket by
        exact object name.

        This is the core assertion of MYTUBE-376: cleanup logic is skipped when
        the flag is false, so no GCS objects are deleted on failure.
        """
        objects = transcoder_service.list_output_objects(test_video_id)
        object_set = set(objects)

        for expected_object in seeded_artifacts:
            assert expected_object in object_set, (
                f"Seeded artifact '{expected_object}' is missing from bucket "
                f"'{gcp_config.hls_bucket}' after the transcoding job failed.\n"
                f"CLEANUP_ON_TRANSCODE_FAILURE=false should have prevented its deletion.\n"
                f"Bucket prefix 'videos/{test_video_id}/' currently contains: {sorted(object_set)}"
            )
