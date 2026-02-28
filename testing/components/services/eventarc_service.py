"""
EventarcService — wraps gcloud CLI calls to inspect Eventarc triggers and
Cloud Run Job definitions for the mytube transcoding pipeline.

Used by MYTUBE-50 to verify that the Eventarc trigger is configured to
invoke the mytube-transcoder Cloud Run Job on GCS object finalization.
"""

import json
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class CloudRunJobInfo:
    """Subset of Cloud Run Job metadata returned by gcloud."""
    name: str
    region: str
    project: str
    raw: dict


@dataclass
class EventarcTriggerInfo:
    """Subset of Eventarc trigger metadata returned by gcloud."""
    name: str
    event_type: str
    bucket_filter: Optional[str]
    destination_service: Optional[str]
    raw: dict


class EventarcService:
    """
    Service object that queries GCP infrastructure via the gcloud CLI.

    Constructor injects project and region so tests never hard-code them.
    Results are cached per name so repeated describe calls within a test
    session do not issue redundant gcloud invocations.
    """

    def __init__(self, project: str, region: str):
        self._project = project
        self._region = region
        self._job_cache: dict = {}
        self._trigger_cache: dict = {}

    # ------------------------------------------------------------------
    # Cloud Run Jobs
    # ------------------------------------------------------------------

    def describe_cloud_run_job(self, job_name: str) -> CloudRunJobInfo:
        """
        Return metadata for a Cloud Run Job.

        Results are cached; subsequent calls for the same job_name return
        the cached value without issuing another gcloud invocation.

        Raises subprocess.CalledProcessError if the job does not exist or
        the caller lacks permissions.
        """
        if job_name in self._job_cache:
            return self._job_cache[job_name]
        result = subprocess.run(
            [
                "gcloud", "run", "jobs", "describe", job_name,
                "--region", self._region,
                "--project", self._project,
                "--format", "json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        raw = json.loads(result.stdout)
        info = CloudRunJobInfo(
            name=job_name,
            region=self._region,
            project=self._project,
            raw=raw,
        )
        self._job_cache[job_name] = info
        return info

    def cloud_run_job_exists(self, job_name: str) -> bool:
        """Return True if the Cloud Run Job exists in the configured region."""
        try:
            self.describe_cloud_run_job(job_name)
            return True
        except subprocess.CalledProcessError:
            return False

    # ------------------------------------------------------------------
    # Eventarc Triggers
    # ------------------------------------------------------------------

    def describe_eventarc_trigger(self, trigger_name: str) -> EventarcTriggerInfo:
        """
        Return metadata for an Eventarc trigger.

        Results are cached; subsequent calls for the same trigger_name return
        the cached value without issuing another gcloud invocation.

        Raises subprocess.CalledProcessError if the trigger does not exist.
        """
        if trigger_name in self._trigger_cache:
            return self._trigger_cache[trigger_name]
        result = subprocess.run(
            [
                "gcloud", "eventarc", "triggers", "describe", trigger_name,
                "--location", self._region,
                "--project", self._project,
                "--format", "json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        raw = json.loads(result.stdout)

        # Extract event type from eventFilters list.
        event_type: Optional[str] = None
        bucket_filter: Optional[str] = None
        for f in raw.get("eventFilters", []):
            attr = f.get("attribute", "")
            val = f.get("value", "")
            if attr == "type":
                event_type = val
            elif attr == "bucket":
                bucket_filter = val

        # Destination Cloud Run service (short name).
        destination_service: Optional[str] = None
        dest = raw.get("destination", {})
        cloud_run = dest.get("cloudRun", {})
        svc_ref = cloud_run.get("service", "")
        if svc_ref:
            # Full resource name: projects/.../services/<name>
            destination_service = svc_ref.split("/")[-1]

        info = EventarcTriggerInfo(
            name=trigger_name,
            event_type=event_type,
            bucket_filter=bucket_filter,
            destination_service=destination_service,
            raw=raw,
        )
        self._trigger_cache[trigger_name] = info
        return info

    def eventarc_trigger_exists(self, trigger_name: str) -> bool:
        """Return True if the Eventarc trigger exists."""
        try:
            self.describe_eventarc_trigger(trigger_name)
            return True
        except subprocess.CalledProcessError:
            return False
