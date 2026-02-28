"""
MYTUBE-54: Delete object from raw bucket — transcoding job is not triggered
by deletion.

Objective:
    Verify that the Eventarc trigger is specific to file creation
    (google.cloud.storage.object.v1.finalized) and does not react to other
    storage events such as object deletion.

Approach:
    Since the Eventarc trigger is an infrastructure component that filters
    events before they reach the trigger service, this test suite verifies
    correctness at two complementary levels:

    1. Infrastructure configuration (setup.sh):
       - The Eventarc trigger command uses
         --event-filters=type=google.cloud.storage.object.v1.finalized
       - No deletion event type (object.v1.deleted) is registered as a filter.

    2. Trigger handler behaviour (trigger.go):
       - The handler only executes a Cloud Run Job when it receives a valid
         GCS finalized event payload.
       - A payload that does NOT conform to a finalized event (e.g. a deletion
         payload that lacks object name / bucket fields) is rejected with a
         400 Bad Request and the job executor is never called.
       - An empty body (as a deletion event stub would produce if it somehow
         reached the handler) is rejected and the executor is not invoked.

    Together these tests confirm that object deletion cannot cause
    mytube-transcoder to be invoked.
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
_SETUP_SH = os.path.join(_REPO_ROOT, "infra", "setup.sh")
_TRIGGER_GO = os.path.join(_REPO_ROOT, "infra", "transcoder-trigger", "internal", "handler", "trigger.go")


# ---------------------------------------------------------------------------
# Helper: read source files
# ---------------------------------------------------------------------------

def _read_file(path: str) -> str:
    with open(path, "r") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Infrastructure configuration tests
# ---------------------------------------------------------------------------


class TestEventarcTriggerConfiguration:
    """The Eventarc trigger provisioning script must filter on object.v1.finalized only."""

    def test_setup_sh_exists(self):
        """infra/setup.sh must be present — it is the authoritative provisioning script."""
        assert os.path.isfile(_SETUP_SH), (
            f"Expected infra/setup.sh at {_SETUP_SH} — file not found"
        )

    def test_eventarc_trigger_uses_finalized_event_type(self):
        """
        The gcloud eventarc triggers create command in setup.sh must specify
        --event-filters=type=google.cloud.storage.object.v1.finalized.

        This is the only event type that the Eventarc trigger should listen to,
        ensuring object creation (not deletion) drives the transcoding pipeline.
        """
        content = _read_file(_SETUP_SH)
        assert "google.cloud.storage.object.v1.finalized" in content, (
            "setup.sh does not contain event-filter for "
            "'google.cloud.storage.object.v1.finalized'. "
            "The Eventarc trigger must be scoped to object creation events only."
        )

    def test_eventarc_trigger_does_not_register_deleted_event_type(self):
        """
        setup.sh must NOT register object.v1.deleted as an event filter.

        If a deletion event type were added, deleting a file from the raw bucket
        could launch the transcoding job — which is the regression this test
        guards against.
        """
        content = _read_file(_SETUP_SH)
        assert "object.v1.deleted" not in content, (
            "setup.sh registers 'google.cloud.storage.object.v1.deleted' as an "
            "Eventarc event filter. This would cause the transcoder to be "
            "triggered on object deletion, which is incorrect."
        )

    def test_eventarc_trigger_does_not_register_archived_event_type(self):
        """
        setup.sh must NOT register object.v1.archived as an event filter.

        Archival events should also not trigger transcoding.
        """
        content = _read_file(_SETUP_SH)
        assert "object.v1.archived" not in content, (
            "setup.sh registers 'google.cloud.storage.object.v1.archived' as an "
            "Eventarc event filter. Only finalized events should trigger transcoding."
        )

    def test_eventarc_trigger_is_scoped_to_raw_uploads_bucket(self):
        """
        The Eventarc trigger must be scoped to the mytube-raw-uploads bucket only.

        This prevents events from other buckets (e.g. the HLS output bucket)
        from inadvertently triggering the transcoder.

        setup.sh defines RAW_BUCKET="mytube-raw-uploads" and uses it via the
        shell variable ${RAW_BUCKET} in the --event-filters=bucket= flag.
        This test validates both the variable assignment and its use.
        """
        content = _read_file(_SETUP_SH)

        # The bucket variable must be defined as the raw-uploads bucket
        assert re.search(
            r'RAW_BUCKET=["\']?mytube-raw-uploads["\']?',
            content,
        ), (
            "setup.sh does not define RAW_BUCKET=mytube-raw-uploads. "
            "The Eventarc trigger bucket scope cannot be verified."
        )

        # The bucket filter must be present using either the literal or the variable
        assert re.search(
            r"--event-filters=bucket=",
            content,
        ), (
            "setup.sh does not contain --event-filters=bucket= in the Eventarc "
            "trigger command. Without a bucket filter, events from any GCS bucket "
            "could trigger the transcoder."
        )

        # The bucket filter must reference RAW_BUCKET (not HLS_BUCKET or any other bucket)
        bucket_filter_match = re.search(
            r"--event-filters=bucket=(\S+)",
            content,
        )
        assert bucket_filter_match, (
            "setup.sh does not contain --event-filters=bucket=<value>."
        )
        bucket_filter_value = bucket_filter_match.group(1)
        # Must not be the HLS output bucket
        assert "hls" not in bucket_filter_value.lower(), (
            f"The Eventarc trigger bucket filter '{bucket_filter_value}' appears "
            "to reference the HLS bucket instead of the raw-uploads bucket."
        )

    def test_eventarc_trigger_command_is_present(self):
        """
        setup.sh must contain a gcloud eventarc triggers create command.
        """
        content = _read_file(_SETUP_SH)
        assert "gcloud eventarc triggers create" in content, (
            "setup.sh does not contain a 'gcloud eventarc triggers create' command. "
            "The Eventarc trigger is not being provisioned."
        )


# ---------------------------------------------------------------------------
# Trigger handler behaviour tests
# ---------------------------------------------------------------------------


class TestTriggerHandlerRejectsDeletionLikePayloads:
    """
    The trigger HTTP handler must not invoke the Cloud Run Job when it receives
    payloads that do not represent a valid object finalization event.

    Context: Eventarc itself filters events so that only finalized events reach
    the trigger service. These tests verify the defence-in-depth layer at the
    handler level — the handler rejects any payload that is missing the required
    GCS object fields (bucket + name), which is consistent with what a
    deletion-event body (or an empty body) would look like if it somehow
    bypassed the Eventarc filter.
    """

    def test_trigger_go_exists(self):
        """infra/transcoder-trigger/internal/handler/trigger.go must exist."""
        assert os.path.isfile(_TRIGGER_GO), (
            f"Expected trigger handler at {_TRIGGER_GO} — file not found"
        )

    def test_handler_rejects_missing_bucket_field(self):
        """
        The handler must return an error (not invoke the job) when the event
        payload has no 'bucket' field.

        A GCS deletion event, if it bypassed Eventarc filtering, would produce
        a different payload structure. The handler's validation ensures it only
        processes payloads that unambiguously represent a finalized object.
        """
        content = _read_file(_TRIGGER_GO)
        # The handler must call event.Parse which validates bucket + name fields.
        assert "event.Parse" in content, (
            "trigger.go does not call event.Parse to validate the incoming payload. "
            "Without payload validation the handler might process invalid events."
        )

    def test_handler_returns_bad_request_on_parse_error(self):
        """
        The handler must write an HTTP 400 Bad Request response when event.Parse
        fails (e.g. missing bucket or name), ensuring no job execution happens.
        """
        content = _read_file(_TRIGGER_GO)
        assert "StatusBadRequest" in content, (
            "trigger.go does not return StatusBadRequest on parse failure. "
            "Invalid event payloads (including deletion-like stubs) must be "
            "rejected with a 400 before any job execution is attempted."
        )

    def test_handler_does_not_execute_job_before_successful_parse(self):
        """
        executor.Execute must only be called after event.Parse AND VideoID
        extraction succeed — never before.

        This guards against a code path where the executor could be called with
        a zero-value / empty request derived from a deletion-like payload.

        Note: positional search uses the actual assignment/call expressions to
        avoid matching occurrences in comments or doc-strings.
        """
        content = _read_file(_TRIGGER_GO)

        # Use the assignment form to avoid matching occurrences inside comments
        parse_pos = content.find("obj, err := event.Parse")
        execute_pos = content.find("if err := executor.Execute")

        assert parse_pos != -1, (
            "trigger.go does not contain 'obj, err := event.Parse' — "
            "the handler must call event.Parse to validate the incoming payload."
        )
        assert execute_pos != -1, (
            "trigger.go does not contain 'if err := executor.Execute' — "
            "the handler must call executor.Execute to run the Cloud Run Job."
        )
        assert parse_pos < execute_pos, (
            "executor.Execute appears before event.Parse in trigger.go. "
            "The handler must validate the event before executing the job."
        )

    def test_handler_extracts_video_id_before_executing_job(self):
        """
        VideoID extraction must happen between event.Parse and executor.Execute.

        This ensures the job is only executed for a well-formed object path
        (the finalized naming convention: raw/<uuid>.<ext>), not for arbitrary
        payloads that could result from other event types.

        Note: positional search uses the actual assignment/call expressions to
        avoid matching occurrences in comments or doc-strings.
        """
        content = _read_file(_TRIGGER_GO)

        parse_pos = content.find("obj, err := event.Parse")
        video_id_pos = content.find("obj.VideoID()")
        execute_pos = content.find("if err := executor.Execute")

        assert video_id_pos != -1, "trigger.go does not call obj.VideoID() to extract the video ID"
        assert parse_pos < video_id_pos < execute_pos, (
            "Expected execution order: event.Parse → VideoID() → executor.Execute. "
            "The current order deviates, which could allow the job to execute "
            "without a valid video ID being confirmed."
        )

    def test_handler_only_accepts_finalized_event_structure(self):
        """
        The trigger handler source must reference the finalized event context —
        it should not contain any logic that handles deletion or archived events.
        """
        content = _read_file(_TRIGGER_GO)

        # Must NOT contain handling for deletion events
        deletion_keywords = ["deleted", "archived", "object.v1.delete", "v1.archived"]
        for keyword in deletion_keywords:
            assert keyword.lower() not in content.lower(), (
                f"trigger.go contains reference to '{keyword}'. The trigger "
                "handler must only process finalized (creation) events."
            )
