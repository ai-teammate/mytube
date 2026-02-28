"""
MYTUBE-50: Configure Eventarc trigger — file upload to raw bucket invokes Cloud Run job.

Objective:
    Verify that the Eventarc trigger is correctly configured to start the
    mytube-transcoder Cloud Run Job upon file upload to the mytube-raw-uploads
    GCS bucket.

Test structure:
    Part A — Local contract tests (always run):
        Verify the transcoder-trigger service binary builds successfully and
        its unit tests pass.  This confirms the handler is wired correctly to
        produce a Cloud Run Jobs API call when it receives a
        google.cloud.storage.object.v1.finalized event payload.

    Part B — Infrastructure smoke tests (skipped when GCP credentials absent):
        Use the EventarcService component to confirm:
        1. The mytube-transcoder Cloud Run Job is defined in the project.
        2. The mytube-gcs-finalize Eventarc trigger exists.
        3. The trigger listens for google.cloud.storage.object.v1.finalized events.
        4. The trigger filters on the mytube-raw-uploads bucket.
        5. The trigger routes to the mytube-transcoder-trigger Cloud Run Service.
"""

import os
import subprocess
import sys

import pytest

# Make the testing root importable regardless of where pytest is invoked from.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.services.eventarc_service import EventarcService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRIGGER_SERVICE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "infra", "transcoder-trigger"
)
TRIGGER_SERVICE_DIR = os.path.abspath(TRIGGER_SERVICE_DIR)

CLOUD_RUN_JOB_NAME = "mytube-transcoder"
TRIGGER_NAME = "mytube-gcs-finalize"
RAW_BUCKET = "mytube-raw-uploads"
TRIGGER_DESTINATION_SERVICE = "mytube-transcoder-trigger"
EXPECTED_EVENT_TYPE = "google.cloud.storage.object.v1.finalized"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcp_project() -> str:
    """GCP project ID from environment.  Skips module if not set."""
    project = os.environ.get("GCP_PROJECT_ID", "")
    if not project:
        pytest.skip("GCP_PROJECT_ID not set — infrastructure tests skipped")
    return project


@pytest.fixture(scope="module")
def gcp_region() -> str:
    """GCP region from environment.  Skips module if not set."""
    region = os.environ.get("GCP_REGION", "")
    if not region:
        pytest.skip("GCP_REGION not set — infrastructure tests skipped")
    return region


@pytest.fixture(scope="module")
def eventarc_service(gcp_project, gcp_region) -> EventarcService:
    """Provide an EventarcService backed by the test project and region."""
    return EventarcService(project=gcp_project, region=gcp_region)


# ---------------------------------------------------------------------------
# Part A — Local contract tests (always run, no GCP required)
# ---------------------------------------------------------------------------


class TestTriggerServiceContract:
    """
    Verifies that the transcoder-trigger Go service is correctly implemented.

    These tests run the existing Go unit-test suite for the trigger service via
    'go test ./...'.  A passing suite confirms that:
      - The handler correctly parses GCS finalization event payloads.
      - The handler extracts VIDEO_ID from the object name.
      - The handler calls the Cloud Run Jobs executor with correct parameters.
      - The handler returns 204 on success and 400/500 on errors.

    No GCP credentials are required.
    """

    def test_trigger_service_builds(self):
        """The transcoder-trigger Go module must build without errors."""
        result = subprocess.run(
            ["go", "build", "./..."],
            cwd=TRIGGER_SERVICE_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"go build failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    def test_trigger_service_unit_tests_pass(self):
        """
        The trigger service unit-test suite must pass.

        This exercises all handler paths end-to-end within the Go test
        infrastructure and acts as the primary automated verification that
        the Eventarc handler wiring is correct.
        """
        result = subprocess.run(
            ["go", "test", "-v", "-count=1", "./..."],
            cwd=TRIGGER_SERVICE_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"go test ./... failed.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    def test_handler_returns_204_for_valid_gcs_event(self):
        """
        The trigger handler must return HTTP 204 when receiving a valid
        google.cloud.storage.object.v1.finalized event payload.

        Verified by the Go test suite (TestTriggerHandler_Success).  This
        assertion confirms the test case is covered by the passing suite.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1", "-run",
                "TestTriggerHandler_Success",
                "./internal/handler/",
            ],
            cwd=TRIGGER_SERVICE_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestTriggerHandler_Success failed.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout, (
            f"Expected PASS in output.\nSTDOUT:\n{result.stdout}"
        )

    def test_handler_passes_correct_video_id_to_executor(self):
        """
        The trigger handler must extract the UUID from the object name
        (raw/<uuid>.mp4) and pass it as VIDEO_ID to the Cloud Run Job executor.

        Verified by TestTriggerHandler_PassesCorrectVideoID.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1", "-run",
                "TestTriggerHandler_PassesCorrectVideoID",
                "./internal/handler/",
            ],
            cwd=TRIGGER_SERVICE_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestTriggerHandler_PassesCorrectVideoID failed.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_handler_returns_400_for_invalid_payload(self):
        """
        The trigger handler must return HTTP 400 when the event payload is
        invalid (missing bucket, missing name, or invalid JSON).

        These cases verify the handler rejects malformed Eventarc deliveries
        and never attempts to run the Cloud Run Job.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1", "-run",
                "TestTriggerHandler_InvalidJSON_Returns400|"
                "TestTriggerHandler_MissingBucket_Returns400|"
                "TestTriggerHandler_MissingName_Returns400|"
                "TestTriggerHandler_EmptyBody_Returns400",
                "./internal/handler/",
            ],
            cwd=TRIGGER_SERVICE_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Bad-payload handler tests failed.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        # All four test functions must appear as PASS.
        assert result.stdout.count("--- PASS") == 4, (
            f"Expected 4 passing tests.\nSTDOUT:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# Part B — Infrastructure smoke tests (require GCP credentials)
# ---------------------------------------------------------------------------


class TestEventarcInfrastructure:
    """
    Smoke tests that verify the live GCP infrastructure matches the expected
    Eventarc configuration for MYTUBE-50.

    All tests in this class are automatically skipped when GCP_PROJECT_ID or
    GCP_REGION environment variables are not set.
    """

    def test_cloud_run_job_exists(self, eventarc_service):
        """
        The mytube-transcoder Cloud Run Job must exist in the GCP project.

        This is the prerequisite for the Eventarc trigger to have a valid
        job target.
        """
        assert eventarc_service.cloud_run_job_exists(CLOUD_RUN_JOB_NAME), (
            f"Cloud Run Job '{CLOUD_RUN_JOB_NAME}' does not exist. "
            f"Run infra/setup.sh to provision the environment."
        )

    def test_eventarc_trigger_exists(self, eventarc_service):
        """
        The mytube-gcs-finalize Eventarc trigger must exist.
        """
        assert eventarc_service.eventarc_trigger_exists(TRIGGER_NAME), (
            f"Eventarc trigger '{TRIGGER_NAME}' does not exist. "
            f"Follow step 8 in infra/setup.sh to create the trigger."
        )

    def test_trigger_listens_for_gcs_finalize_event(self, eventarc_service):
        """
        The Eventarc trigger must be configured for the
        google.cloud.storage.object.v1.finalized event type.
        """
        info = eventarc_service.describe_eventarc_trigger(TRIGGER_NAME)
        assert info.event_type == EXPECTED_EVENT_TYPE, (
            f"Trigger event type mismatch: expected '{EXPECTED_EVENT_TYPE}', "
            f"got '{info.event_type}'."
        )

    def test_trigger_filters_on_raw_uploads_bucket(self, eventarc_service):
        """
        The Eventarc trigger must filter on the mytube-raw-uploads bucket so
        that only uploads to that bucket invoke the transcoder job.
        """
        info = eventarc_service.describe_eventarc_trigger(TRIGGER_NAME)
        assert info.bucket_filter == RAW_BUCKET, (
            f"Trigger bucket filter mismatch: expected '{RAW_BUCKET}', "
            f"got '{info.bucket_filter}'."
        )

    def test_trigger_routes_to_correct_cloud_run_service(self, eventarc_service):
        """
        The Eventarc trigger must route events to the
        mytube-transcoder-trigger Cloud Run Service, which is the HTTP
        intermediary that calls the Cloud Run Jobs API.
        """
        info = eventarc_service.describe_eventarc_trigger(TRIGGER_NAME)
        assert info.destination_service == TRIGGER_DESTINATION_SERVICE, (
            f"Trigger destination mismatch: expected '{TRIGGER_DESTINATION_SERVICE}', "
            f"got '{info.destination_service}'."
        )
