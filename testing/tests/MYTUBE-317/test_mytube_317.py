"""
MYTUBE-317: Validate Eventarc trigger configuration — mytube-gcs-finalize destination is correct.

Objective
---------
Verify the Eventarc trigger ``mytube-gcs-finalize`` is correctly wired to the
destination service and filtered for the correct bucket events to prevent
pipeline failure.

Test Steps
----------
1. Execute ``gcloud eventarc triggers describe mytube-gcs-finalize --location=us-central1``.
2. Confirm ``destination.cloudRunService.service`` is set to ``mytube-transcoder-trigger``.
3. Confirm ``eventFilters`` include the bucket ``mytube-raw-uploads`` and event
   type ``google.cloud.storage.object.v1.finalized``.

Expected Result
---------------
The trigger configuration parameters match the intended architecture, ensuring
events are delivered to the correct trigger service.

Environment Variables
---------------------
- GOOGLE_APPLICATION_CREDENTIALS   Path to the CI service account JSON key.
                                    Must be set explicitly — no default fallback.
- GCP_PROJECT_ID                   GCP project ID (default: ``ai-native-478811``).
- GCP_REGION                       GCP region (default: ``us-central1``).
- EVENTARC_TRIGGER_NAME            Trigger name (default: ``mytube-gcs-finalize``).
- EXPECTED_DESTINATION_SERVICE     Expected Cloud Run service short name
                                    (default: ``mytube-transcoder-trigger``).
- EXPECTED_BUCKET                  Expected GCS bucket in event filters
                                    (default: ``mytube-raw-uploads``).
- EXPECTED_EVENT_TYPE              Expected event type in event filters
                                    (default: ``google.cloud.storage.object.v1.finalized``).

Architecture Notes
------------------
- ``EventarcService`` from ``testing.components.services.eventarc_service`` is
  used for all gcloud calls. Raw JSON is inspected for ``cloudRunService``
  destination path in addition to the legacy ``cloudRun`` path.
- All GCP credentials are injected via environment variables; never hard-coded.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.services.eventarc_service import EventarcService

# ---------------------------------------------------------------------------
# Config — read from environment, fall back to defaults
# ---------------------------------------------------------------------------

PROJECT_ID: str = os.environ.get("GCP_PROJECT_ID", "ai-native-478811")
REGION: str = os.environ.get("GCP_REGION", "us-central1")
TRIGGER_NAME: str = os.environ.get("EVENTARC_TRIGGER_NAME", "mytube-gcs-finalize")
EXPECTED_DESTINATION_SERVICE: str = os.environ.get(
    "EXPECTED_DESTINATION_SERVICE", "mytube-transcoder-trigger"
)
EXPECTED_BUCKET: str = os.environ.get("EXPECTED_BUCKET", "mytube-raw-uploads")
EXPECTED_EVENT_TYPE: str = os.environ.get(
    "EXPECTED_EVENT_TYPE", "google.cloud.storage.object.v1.finalized"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_destination_service(raw: dict) -> str | None:
    """Extract the short Cloud Run service name from the trigger raw JSON.

    Handles both ``destination.cloudRunService.service`` (newer Eventarc
    resource representation) and the legacy ``destination.cloudRun.service``
    path, returning the leaf service name in either case.
    """
    dest = raw.get("destination", {})

    # Newer path: destination.cloudRunService.service
    cloud_run_service = dest.get("cloudRunService", {})
    svc_ref = cloud_run_service.get("service", "")
    if svc_ref:
        return svc_ref.split("/")[-1]

    # Legacy path: destination.cloudRun.service
    cloud_run = dest.get("cloudRun", {})
    svc_ref = cloud_run.get("service", "")
    if svc_ref:
        return svc_ref.split("/")[-1]

    return None


def _extract_event_filters(raw: dict) -> dict[str, str]:
    """Return a mapping of event-filter attribute → value from raw trigger JSON."""
    filters: dict[str, str] = {}
    for f in raw.get("eventFilters", []):
        attr = f.get("attribute", "")
        val = f.get("value", "")
        if attr:
            filters[attr] = val
    return filters


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def eventarc_service() -> EventarcService:
    return EventarcService(project=PROJECT_ID, region=REGION)


@pytest.fixture(scope="module")
def trigger_raw(eventarc_service: EventarcService) -> dict:
    """Describe the Eventarc trigger and return the raw JSON dict."""
    info = eventarc_service.describe_eventarc_trigger(TRIGGER_NAME)
    return info.raw


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEventarcTriggerConfiguration:
    """Validate that mytube-gcs-finalize is correctly configured."""

    def test_trigger_exists(self, eventarc_service: EventarcService) -> None:
        """Step 1: The trigger must exist and be describable."""
        assert eventarc_service.eventarc_trigger_exists(TRIGGER_NAME), (
            f"Eventarc trigger '{TRIGGER_NAME}' does not exist in "
            f"project='{PROJECT_ID}' location='{REGION}'."
        )

    def test_destination_service_is_correct(self, trigger_raw: dict) -> None:
        """Step 2: destination.cloudRunService.service must be mytube-transcoder-trigger."""
        service_name = _extract_destination_service(trigger_raw)
        assert service_name == EXPECTED_DESTINATION_SERVICE, (
            f"Expected destination service '{EXPECTED_DESTINATION_SERVICE}', "
            f"got '{service_name}'.\n"
            f"Raw destination: {trigger_raw.get('destination')}"
        )

    def test_event_filter_bucket_is_correct(self, trigger_raw: dict) -> None:
        """Step 3a: eventFilters must include bucket=mytube-raw-uploads."""
        filters = _extract_event_filters(trigger_raw)
        bucket = filters.get("bucket")
        assert bucket == EXPECTED_BUCKET, (
            f"Expected eventFilter bucket='{EXPECTED_BUCKET}', "
            f"got '{bucket}'.\nAll event filters: {filters}"
        )

    def test_event_filter_type_is_correct(self, trigger_raw: dict) -> None:
        """Step 3b: eventFilters must include type=google.cloud.storage.object.v1.finalized."""
        filters = _extract_event_filters(trigger_raw)
        event_type = filters.get("type")
        assert event_type == EXPECTED_EVENT_TYPE, (
            f"Expected eventFilter type='{EXPECTED_EVENT_TYPE}', "
            f"got '{event_type}'.\nAll event filters: {filters}"
        )
