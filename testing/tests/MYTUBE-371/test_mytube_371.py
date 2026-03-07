"""
MYTUBE-371: End-to-end silent video processing — video status transitions
to 'ready' and manifest URL is written.

Objective
---------
Validate the complete lifecycle of a silent video upload in a staging
environment:
  1. Upload the silent video via the REST API (POST /api/videos → signed URL,
     then PUT the bytes to GCS).
  2. Wait for the Eventarc trigger and Cloud Run transcoding job to complete.
  3. Query the database: assert status='ready' and hls_manifest_path IS NOT NULL.
  4. Assert the HLS manifest URL returned by the API is accessible via CDN
     (HTTP 200).

Prerequisites (environment variables)
--------------------------------------
FIREBASE_TEST_TOKEN  — Firebase ID token for the authenticated upload call.
                       Test is skipped when absent.
API_BASE_URL         — Base URL of the deployed API
                       (default: http://localhost:8080).
SILENT_VIDEO_PATH    — Optional path to a silent MP4 to upload.
                       When absent the test generates a minimal valid MP4
                       using ffmpeg (if installed) or a hard-coded tiny
                       binary blob.
E2E_POLL_TIMEOUT     — Seconds to wait for status='ready' (default: 600).
E2E_POLL_INTERVAL    — Seconds between status polls (default: 10).
DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE
                     — Database connection settings (all have sensible
                       test defaults).

Architecture notes
------------------
- AuthService issues the authenticated POST /api/videos request.
- A plain urllib PUT request uploads the video bytes to the signed GCS URL.
- VideoApiService polls GET /api/videos/:id for status='ready'.
- Direct psycopg2 connection verifies the DB columns.
- urllib.request verifies the CDN manifest URL returns HTTP 200.
- No hardcoded waits other than the configurable poll loop.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Optional

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.db_config import DBConfig
from testing.components.services.auth_service import AuthService
from testing.components.services.video_api_service import VideoApiService

# ---------------------------------------------------------------------------
# Constants / environment
# ---------------------------------------------------------------------------

_FIREBASE_TOKEN: str = os.getenv("FIREBASE_TEST_TOKEN", "")
_POLL_TIMEOUT: int = int(os.getenv("E2E_POLL_TIMEOUT", "600"))
_POLL_INTERVAL: int = int(os.getenv("E2E_POLL_INTERVAL", "10"))
_SILENT_VIDEO_PATH: str = os.getenv("SILENT_VIDEO_PATH", "")

_TEST_TITLE = "MYTUBE-371 silent video e2e test"
_MIME_TYPE = "video/mp4"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_minimal_mp4() -> bytes:
    """Return the bytes of a minimal valid silent MP4 file.

    1. Tries ffmpeg (produces a proper 1-second silent H.264/AAC clip).
    2. Downloads a real MP4 from a public CDN as a secondary fallback.
    3. Skips the test if both options are unavailable — uploading an
       unprocessable blob would cause a false pipeline failure.
    """
    # 1. Try ffmpeg
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-f", "lavfi", "-i", "color=black:s=320x240:r=1",
                "-t", "1",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-movflags", "+faststart",
                "-f", "mp4",
                "pipe:1",
            ],
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 2. Download a real MP4 from a public CDN
    try:
        with urllib.request.urlopen(
            "https://www.w3schools.com/html/mov_bbb.mp4", timeout=30
        ) as resp:
            return resp.read()
    except Exception:
        pass

    # 3. Skip rather than upload unprocessable garbage
    pytest.skip(
        "Cannot generate a valid silent MP4: ffmpeg is not installed and the "
        "public fallback URL is unreachable. Set SILENT_VIDEO_PATH to a valid "
        "silent .mp4 file to run this test."
    )


def _load_video_bytes() -> bytes:
    """Return the bytes to upload as the silent video."""
    if _SILENT_VIDEO_PATH and os.path.isfile(_SILENT_VIDEO_PATH):
        with open(_SILENT_VIDEO_PATH, "rb") as fh:
            return fh.read()
    return _generate_minimal_mp4()


def _put_to_signed_url(upload_url: str, data: bytes, content_type: str) -> int:
    """PUT *data* to a GCS signed URL; return the HTTP status code."""
    req = urllib.request.Request(
        upload_url,
        data=data,
        method="PUT",
        headers={"Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:
        return 0


def _poll_for_ready(
    video_svc: VideoApiService,
    video_id: str,
    timeout_s: int,
    interval_s: int,
) -> Optional[dict]:
    """Poll GET /api/videos/:id until status='ready' or *timeout_s* is reached.

    Returns the video detail dict when status is 'ready', or None on timeout.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        detail = video_svc.get_video(video_id)
        if detail and detail.get("status") == "ready":
            return detail
        time.sleep(interval_s)
    return None


def _check_url_reachable(url: str) -> tuple[int, str]:
    """GET *url* and return (status_code, error_message).

    Returns (200, "") on success; (status_code, message) otherwise.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "mytube-e2e-test"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, ""
    except urllib.error.HTTPError as exc:
        return exc.code, str(exc)
    except Exception as exc:
        return 0, str(exc)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    return APIConfig()


@pytest.fixture(scope="module")
def firebase_token() -> str:
    """Firebase ID token from FIREBASE_TEST_TOKEN; skips if absent."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN is not set — skipping e2e upload test. "
            "Set FIREBASE_TEST_TOKEN to a valid Firebase ID token to run this test."
        )
    return _FIREBASE_TOKEN


@pytest.fixture(scope="module")
def auth_service(api_config: APIConfig, firebase_token: str) -> AuthService:
    return AuthService(base_url=api_config.base_url, token=firebase_token)


@pytest.fixture(scope="module")
def video_api_service(api_config: APIConfig) -> VideoApiService:
    return VideoApiService(api_config)


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def uploaded_video(
    auth_service: AuthService,
    video_api_service: VideoApiService,
) -> dict:
    """Create a video record and upload the silent file via the signed URL.

    Returns a dict with keys: video_id, upload_status_code.
    Skips the test if the API is unreachable or returns an unexpected status.
    """
    video_bytes = _load_video_bytes()

    # Step 1 — Create the video record and obtain the signed upload URL.
    status_code, body = auth_service.post(
        "/api/videos",
        {
            "title": _TEST_TITLE,
            "description": "Automated e2e test — MYTUBE-371",
            "mime_type": _MIME_TYPE,
        },
    )

    if status_code == 0:
        pytest.skip(
            f"API is not reachable at {auth_service._base_url} — "
            "set API_BASE_URL to the deployed API endpoint."
        )

    if status_code == 401:
        pytest.skip(
            f"POST /api/videos returned 401 — FIREBASE_TEST_TOKEN may be "
            "expired or invalid. Obtain a fresh token and retry."
        )

    assert status_code == 201, (
        f"Expected HTTP 201 from POST /api/videos; got {status_code}.\n"
        f"Response body: {body}"
    )

    try:
        resp_json = json.loads(body)
    except json.JSONDecodeError as exc:
        pytest.fail(f"POST /api/videos returned non-JSON body: {body!r}\n{exc}")

    video_id: str = resp_json.get("video_id", "")
    upload_url: str = resp_json.get("upload_url", "")

    assert video_id, (
        f"POST /api/videos response did not include 'video_id'.\nBody: {body}"
    )
    assert upload_url, (
        f"POST /api/videos response did not include 'upload_url'.\nBody: {body}"
    )

    # Step 2 — PUT the video bytes to the GCS signed URL.
    put_status = _put_to_signed_url(upload_url, video_bytes, _MIME_TYPE)

    return {
        "video_id": video_id,
        "upload_url": upload_url,
        "upload_status_code": put_status,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSilentVideoE2EPipeline:
    """End-to-end silent video upload → transcoding → ready status."""

    # ------------------------------------------------------------------
    # Step 1 — API creates the video record and returns a signed URL
    # ------------------------------------------------------------------

    def test_api_returns_201_on_create(self, uploaded_video: dict) -> None:
        """POST /api/videos must return HTTP 201 and a non-empty video_id."""
        assert uploaded_video["video_id"], (
            "POST /api/videos did not return a video_id."
        )

    def test_api_returns_signed_upload_url(self, uploaded_video: dict) -> None:
        """POST /api/videos must return a non-empty upload_url."""
        assert uploaded_video["upload_url"], (
            "POST /api/videos did not return an upload_url."
        )

    # ------------------------------------------------------------------
    # Step 2 — Silent video is uploaded to GCS via the signed URL
    # ------------------------------------------------------------------

    def test_gcs_put_succeeds(self, uploaded_video: dict) -> None:
        """PUT to the signed GCS URL must return HTTP 200."""
        code = uploaded_video["upload_status_code"]
        assert code == 200, (
            f"PUT to signed GCS URL returned HTTP {code}; expected 200.\n"
            f"This means the video was not uploaded to GCS, so the Eventarc "
            f"trigger will never fire and the pipeline will not start."
        )

    # ------------------------------------------------------------------
    # Step 3 — Eventarc trigger and Cloud Run Job run; status → 'ready'
    # ------------------------------------------------------------------

    def test_video_transitions_to_ready(
        self, uploaded_video: dict, video_api_service: VideoApiService
    ) -> None:
        """Video status must transition to 'ready' within the poll timeout.

        Polls GET /api/videos/:id every E2E_POLL_INTERVAL seconds for up to
        E2E_POLL_TIMEOUT seconds (default 600 s / 10 s).
        """
        video_id = uploaded_video["video_id"]
        detail = _poll_for_ready(
            video_api_service, video_id, _POLL_TIMEOUT, _POLL_INTERVAL
        )
        # Capture the actual status for a useful failure message.
        actual_detail = video_api_service.get_video(video_id)
        actual_status = (actual_detail or {}).get("status", "<not found>")
        assert detail is not None, (
            f"Video {video_id!r} did not reach status='ready' within "
            f"{_POLL_TIMEOUT}s (last observed status: {actual_status!r}).\n"
            f"This indicates the Eventarc trigger did not fire, the Cloud Run "
            f"transcoding job failed, or the job did not complete in time."
        )

    # ------------------------------------------------------------------
    # Step 4 — Database reflects status='ready' and hls_manifest_path set
    # ------------------------------------------------------------------

    def test_db_status_is_ready(
        self, uploaded_video: dict, db_config: DBConfig
    ) -> None:
        """videos.status must equal 'ready' in the database."""
        try:
            import psycopg2
        except ImportError:
            pytest.skip("psycopg2 is not installed — skipping DB assertion.")

        video_id = uploaded_video["video_id"]
        try:
            conn = psycopg2.connect(db_config.dsn())
        except Exception as exc:
            pytest.skip(f"Database is not reachable: {exc}")

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status, hls_manifest_path FROM videos WHERE id = %s",
                    (video_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()

        assert row is not None, (
            f"No row found in videos table for id={video_id!r}."
        )
        status, hls_manifest_path = row
        assert status == "ready", (
            f"Expected videos.status='ready' for video_id={video_id!r}; "
            f"got {status!r}."
        )

    def test_db_hls_manifest_path_is_set(
        self, uploaded_video: dict, db_config: DBConfig
    ) -> None:
        """videos.hls_manifest_path must be non-null after transcoding."""
        try:
            import psycopg2
        except ImportError:
            pytest.skip("psycopg2 is not installed — skipping DB assertion.")

        video_id = uploaded_video["video_id"]
        try:
            conn = psycopg2.connect(db_config.dsn())
        except Exception as exc:
            pytest.skip(f"Database is not reachable: {exc}")

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT hls_manifest_path FROM videos WHERE id = %s",
                    (video_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()

        assert row is not None, (
            f"No row found in videos table for id={video_id!r}."
        )
        hls_manifest_path = row[0]
        assert hls_manifest_path, (
            f"videos.hls_manifest_path is NULL for video_id={video_id!r} "
            f"after status transitioned to 'ready'.\n"
            f"The transcoder must populate hls_manifest_path atomically with "
            f"setting status='ready'."
        )

    # ------------------------------------------------------------------
    # Step 5 — Manifest URL is accessible via CDN
    # ------------------------------------------------------------------

    def test_hls_manifest_url_accessible_via_cdn(
        self, uploaded_video: dict, video_api_service: VideoApiService
    ) -> None:
        """GET /api/videos/:id must return a non-null hls_manifest_url that
        returns HTTP 200 when fetched directly (CDN or GCS public URL).
        """
        video_id = uploaded_video["video_id"]
        detail = video_api_service.get_video(video_id)

        assert detail is not None, (
            f"GET /api/videos/{video_id} returned no data."
        )
        assert detail.get("status") == "ready", (
            f"Video {video_id!r} is not ready; "
            f"status={detail.get('status')!r}."
        )

        manifest_url: str = detail.get("hls_manifest_url") or ""
        assert manifest_url, (
            f"hls_manifest_url is null/empty in GET /api/videos/{video_id} "
            f"response even though status='ready'.\n"
            f"Full response: {json.dumps(detail, indent=2)}"
        )

        http_status, error_msg = _check_url_reachable(manifest_url)
        assert http_status == 200, (
            f"HLS manifest URL {manifest_url!r} returned HTTP {http_status} "
            f"(expected 200).\n"
            f"Error: {error_msg}\n"
            f"This indicates the manifest was not written to GCS/CDN correctly "
            f"or the CDN URL is misconfigured."
        )
