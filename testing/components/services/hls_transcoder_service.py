"""
HLS Transcoder Service — runs the Cloud Run transcoding job and inspects HLS output.

Wraps gcloud CLI to:
  - Execute the Cloud Run Job for a specific VIDEO_ID
  - Poll for job completion
  - Download and parse the HLS master playlist from the output bucket
"""
from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

from google.cloud import storage as gcs_storage

from testing.core.config.gcp_config import GcpConfig


@dataclass
class HLSRendition:
    """Represents a single stream entry in an HLS master playlist."""

    bandwidth: int          # BANDWIDTH attribute (bits/s)
    resolution: str         # RESOLUTION attribute (e.g. "1280x720")
    uri: str                # Relative URI to the rendition playlist


@dataclass
class HLSMasterPlaylist:
    """Parsed content of an HLS master playlist (index.m3u8)."""

    raw_content: str
    renditions: list[HLSRendition] = field(default_factory=list)


@dataclass
class JobExecutionResult:
    """Result of a Cloud Run Job execution attempt."""

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    error_message: str = ""


class HLSTranscoderService:
    """
    Service for triggering the Cloud Run transcoding job and verifying HLS output.

    Parameters
    ----------
    config:
        GcpConfig instance with project, region, and bucket configuration.
    storage_client:
        An authenticated ``google.cloud.storage.Client``.
        Must be injected by the caller — never instantiated internally.
    """

    # Bandwidth thresholds for the three required renditions (bits/s)
    REQUIRED_RENDITIONS = [
        {"label": "360p",  "min_bandwidth": 400_000,  "max_bandwidth": 600_000},
        {"label": "720p",  "min_bandwidth": 1_200_000, "max_bandwidth": 1_800_000},
        {"label": "1080p", "min_bandwidth": 2_400_000, "max_bandwidth": 3_600_000},
    ]

    def __init__(self, config: GcpConfig, storage_client: gcs_storage.Client) -> None:
        self._config = config
        self._client = storage_client

    # ------------------------------------------------------------------
    # Cloud Run Job execution
    # ------------------------------------------------------------------

    def run_transcoding_job(
        self,
        video_id: str,
        raw_object_path: str,
        db_dsn: str = "",
        timeout_seconds: int = 300,
        extra_env_vars: Optional[dict] = None,
    ) -> JobExecutionResult:
        """
        Execute the Cloud Run Job for the given VIDEO_ID and wait for completion.

        Parameters
        ----------
        video_id:
            The VIDEO_ID to pass to the job.
        raw_object_path:
            GCS object path of the raw video file (e.g. ``raw/abc123.mp4``).
        db_dsn:
            PostgreSQL DSN to pass as DB_DSN environment variable.
        timeout_seconds:
            Maximum seconds to wait for job completion.
        extra_env_vars:
            Optional additional environment variables to inject into the job
            via ``--update-env-vars``. Values are appended after the standard
            set, allowing callers to override or extend job configuration
            (e.g. ``{"CLEANUP_ON_TRANSCODE_FAILURE": "false"}``).

        Returns
        -------
        JobExecutionResult
            Success flag, exit code, and stdout/stderr output.
        """
        env_vars = (
            f"VIDEO_ID={video_id},"
            f"RAW_OBJECT_PATH={raw_object_path},"
            f"HLS_BUCKET={self._config.hls_bucket},"
            f"CDN_BASE_URL={self._config.cdn_base_url}"
        )
        if extra_env_vars:
            for key, value in extra_env_vars.items():
                env_vars += f",{key}={value}"

        cmd = [
            "gcloud", "run", "jobs", "execute",
            self._config.transcoder_job,
            f"--region={self._config.region}",
            f"--project={self._config.project_id}",
            "--wait",
            f"--update-env-vars={env_vars}",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            return JobExecutionResult(
                success=(result.returncode == 0),
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired:
            return JobExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="",
                error_message=f"Job timed out after {timeout_seconds}s",
            )
        except Exception as exc:  # noqa: BLE001
            return JobExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="",
                error_message=str(exc),
            )

    # ------------------------------------------------------------------
    # HLS output inspection
    # ------------------------------------------------------------------

    def list_output_objects(self, video_id: str) -> list[str]:
        """Return all GCS object names under ``videos/{video_id}/`` in the HLS bucket."""
        prefix = f"videos/{video_id}/"
        bucket = self._client.bucket(self._config.hls_bucket)
        blobs = list(self._client.list_blobs(bucket, prefix=prefix))
        return [blob.name for blob in blobs]

    def download_master_playlist(self, video_id: str) -> Optional[str]:
        """
        Download and return the raw text content of ``videos/{video_id}/index.m3u8``.

        Returns None if the file does not exist.
        """
        object_name = f"videos/{video_id}/index.m3u8"
        bucket = self._client.bucket(self._config.hls_bucket)
        blob = bucket.blob(object_name)
        if not blob.exists():
            return None
        return blob.download_as_text()

    def parse_master_playlist(self, content: str) -> HLSMasterPlaylist:
        """
        Parse an HLS master playlist and extract rendition stream entries.

        Handles ``#EXT-X-STREAM-INF`` tags followed by URI lines.
        """
        renditions: list[HLSRendition] = []
        lines = content.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXT-X-STREAM-INF:"):
                attrs = line[len("#EXT-X-STREAM-INF:"):]
                bandwidth = self._parse_int_attr(attrs, "BANDWIDTH")
                resolution = self._parse_str_attr(attrs, "RESOLUTION") or ""
                # Next non-empty line is the URI
                uri = ""
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith("#"):
                        uri = next_line
                        i = j  # advance past the URI line
                        break
                    j += 1
                renditions.append(
                    HLSRendition(bandwidth=bandwidth or 0, resolution=resolution, uri=uri)
                )
            i += 1
        return HLSMasterPlaylist(raw_content=content, renditions=renditions)

    def has_required_renditions(self, playlist: HLSMasterPlaylist) -> dict[str, bool]:
        """
        Check whether the playlist contains each required rendition.

        Returns a dict mapping label (e.g. ``"360p"``) to True/False.
        """
        results: dict[str, bool] = {}
        for req in self.REQUIRED_RENDITIONS:
            found = any(
                req["min_bandwidth"] <= r.bandwidth <= req["max_bandwidth"]
                for r in playlist.renditions
            )
            results[req["label"]] = found
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_int_attr(attrs: str, name: str) -> Optional[int]:
        """Extract an integer attribute value from an HLS attribute string."""
        match = re.search(rf"{name}=(\d+)", attrs)
        return int(match.group(1)) if match else None

    @staticmethod
    def _parse_str_attr(attrs: str, name: str) -> Optional[str]:
        """Extract a string attribute value (quoted or unquoted) from an HLS attribute string."""
        match = re.search(rf'{name}="([^"]+)"', attrs)
        if match:
            return match.group(1)
        match = re.search(rf"{name}=([^\s,]+)", attrs)
        return match.group(1) if match else None
