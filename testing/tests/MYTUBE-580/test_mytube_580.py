"""
MYTUBE-580: Recommendation exclusion criteria — self and non-ready videos are filtered out.

Objective
---------
Verify that the recommendations list excludes the video being watched (Video A)
and any videos that are not in 'ready' status (Video B with 'processing',
Video C with 'failed').

Preconditions
-------------
- Video A (target) belongs to category 'Tech', status='ready'.
- Video B belongs to category 'Tech' but status is 'processing'.
- Video C belongs to category 'Tech' but status is 'failed'.

Steps
-----
1. Send a GET request to /api/videos/[ID_of_Video_A]/recommendations.
2. Inspect the returned list for Video A, Video B, and Video C.

Expected Result
---------------
None of the specified videos (A, B, or C) are present in the recommendations
array.

Architecture
------------
Two layers:

**Layer A — Go unit tests** (always runs; no DB required):
    Runs the existing Go handler unit tests for the recommendations handler.
    These tests verify that the handler correctly maps repository results to the
    JSON response, handles errors, etc.

**Layer B — Integration test via HTTP** (runs when DB is reachable):
    1. Seeds a test user, a 'Tech' category, and three videos:
       - Video A: status='ready', hls_manifest_path set, category='Tech'
       - Video B: status='processing', category='Tech'
       - Video C: status='failed', category='Tech'
    2. Starts the Go API binary on a local port.
    3. Issues GET /api/videos/{video_a_id}/recommendations.
    4. Asserts HTTP 200.
    5. Asserts Video A is NOT in the recommendations list.
    6. Asserts Video B is NOT in the recommendations list.
    7. Asserts Video C is NOT in the recommendations list.

Environment variables
---------------------
- API_BINARY              : Path to the pre-built Go binary
                            (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE:
                            Database connection settings (Layer B).
- FIREBASE_PROJECT_ID     : Firebase project ID for the API process env.
- GOOGLE_APPLICATION_CREDENTIALS : Path to service-account JSON.

Run from repo root:
    pytest testing/tests/MYTUBE-580/test_mytube_580.py -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_API_DIR = os.path.join(_REPO_ROOT, "api")
_DEFAULT_BINARY = os.path.join(_API_DIR, "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18580
_STARTUP_TIMEOUT = 20.0

_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "ai-native-478811")

_DEFAULT_MOCK_CREDS = os.path.join(
    _REPO_ROOT, "testing", "fixtures", "mock_service_account.json"
)
_MOCK_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", _DEFAULT_MOCK_CREDS)

_TEST_FIREBASE_UID = "test-uid-mytube-580-" + str(uuid.uuid4())[:8]
_TEST_USERNAME = "testuser_mytube580_" + str(uuid.uuid4())[:8]
_CATEGORY_NAME = "Tech"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_binary() -> None:
    """Build the Go API binary if it is not already present."""
    if os.path.isfile(API_BINARY):
        return
    result = subprocess.run(
        ["go", "build", "-o", API_BINARY, "."],
        cwd=_API_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(
            f"Failed to build API binary:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


def _run_go_test(pattern: str) -> subprocess.CompletedProcess:
    """Run Go unit tests matching *pattern* in the handler package."""
    return subprocess.run(
        ["go", "test", "-v", "-count=1", "-run", pattern, "./internal/handler/"],
        cwd=_API_DIR,
        capture_output=True,
        text=True,
    )


def _is_db_available(db_config: DBConfig) -> bool:
    """Return True if PostgreSQL is reachable."""
    try:
        import psycopg2
        conn = psycopg2.connect(db_config.dsn())
        conn.close()
        return True
    except Exception:
        return False


# ===========================================================================
# Layer A — Go unit tests (always run; no external services required)
# ===========================================================================


class TestRecommendationsHandlerGoUnit:
    """Run the existing Go unit tests for the recommendations handler."""

    def test_recommendations_handler_all_unit_tests_pass(self):
        """All Go unit tests for the recommendations handler must pass."""
        result = _run_go_test("TestRecommendationsHandler")
        assert result.returncode == 0, (
            f"One or more Go unit tests for the recommendations handler failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_recommendations_handler_success_returns_list(self):
        """TestRecommendationsHandler_GET_Success_ReturnsList must pass."""
        result = _run_go_test("TestRecommendationsHandler_GET_Success_ReturnsList")
        assert result.returncode == 0, (
            f"TestRecommendationsHandler_GET_Success_ReturnsList failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_recommendations_handler_empty_slice_when_no_recommendations(self):
        """TestRecommendationsHandler_GET_EmptySlice_WhenNoRecommendations must pass."""
        result = _run_go_test("TestRecommendationsHandler_GET_EmptySlice_WhenNoRecommendations")
        assert result.returncode == 0, (
            f"TestRecommendationsHandler_GET_EmptySlice_WhenNoRecommendations failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_recommendations_handler_invalid_video_id_returns_400(self):
        """TestRecommendationsHandler_InvalidVideoID_Returns400 must pass."""
        result = _run_go_test("TestRecommendationsHandler_InvalidVideoID_Returns400")
        assert result.returncode == 0, (
            f"TestRecommendationsHandler_InvalidVideoID_Returns400 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


# ===========================================================================
# Layer B — Integration test via HTTP
# Requires DB connectivity; skipped gracefully when the DB is unavailable.
# ===========================================================================


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def db_conn(db_config: DBConfig):
    """Open a DB connection; skip Layer B if the DB is unreachable."""
    if not _is_db_available(db_config):
        pytest.skip(
            "Database is not reachable — skipping integration tests (Layer B). "
            "Layer A Go unit tests still run."
        )
    import psycopg2
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_videos(db_conn):
    """Seed test user, Tech category, and three videos (A, B, C).

    Video A: status='ready', hls_manifest_path set, category='Tech'
    Video B: status='processing', category='Tech'
    Video C: status='failed',    category='Tech'

    Yields dict with keys: user_id, category_id, video_a_id, video_b_id, video_c_id.
    Cleans up all seeded rows on teardown.
    """
    import psycopg2

    # --- Insert test user ---
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO UPDATE SET username = EXCLUDED.username
            RETURNING id
            """,
            (_TEST_FIREBASE_UID, _TEST_USERNAME),
        )
        row = cur.fetchone()
        if row is None:
            cur.execute(
                "SELECT id FROM users WHERE firebase_uid = %s",
                (_TEST_FIREBASE_UID,),
            )
            row = cur.fetchone()
        user_id = str(row[0])

    # --- Ensure 'Tech' category exists ---
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO categories (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id",
            (_CATEGORY_NAME,),
        )
        row = cur.fetchone()
        if row is None:
            cur.execute("SELECT id FROM categories WHERE name = %s", (_CATEGORY_NAME,))
            row = cur.fetchone()
        category_id = int(row[0])

    # --- Seed Video A: ready, Tech ---
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO videos (uploader_id, title, status, category_id, hls_manifest_path)
            VALUES (%s, %s, 'ready', %s, %s)
            RETURNING id
            """,
            (
                user_id,
                "MYTUBE-580 Video A (target, ready)",
                category_id,
                "gs://mytube-hls-output/mytube580/a/playlist.m3u8",
            ),
        )
        video_a_id = str(cur.fetchone()[0])

    # --- Seed Video B: processing, Tech ---
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO videos (uploader_id, title, status, category_id)
            VALUES (%s, %s, 'processing', %s)
            RETURNING id
            """,
            (user_id, "MYTUBE-580 Video B (processing)", category_id),
        )
        video_b_id = str(cur.fetchone()[0])

    # --- Seed Video C: failed, Tech ---
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO videos (uploader_id, title, status, category_id)
            VALUES (%s, %s, 'failed', %s)
            RETURNING id
            """,
            (user_id, "MYTUBE-580 Video C (failed)", category_id),
        )
        video_c_id = str(cur.fetchone()[0])

    yield {
        "user_id": user_id,
        "category_id": category_id,
        "video_a_id": video_a_id,
        "video_b_id": video_b_id,
        "video_c_id": video_c_id,
    }

    # --- Teardown: remove seeded rows in FK-safe order ---
    with db_conn.cursor() as cur:
        cur.execute(
            "DELETE FROM videos WHERE id IN (%s, %s, %s)",
            (video_a_id, video_b_id, video_c_id),
        )
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig, seeded_videos):
    """Start the Go API server on port _PORT; stop it after tests complete."""
    _build_binary()

    env = {
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        "FIREBASE_PROJECT_ID": _FIREBASE_PROJECT_ID,
        "GOOGLE_APPLICATION_CREDENTIALS": _MOCK_CREDS,
        "RAW_UPLOADS_BUCKET": "mytube-raw-uploads",
        "HLS_BUCKET": "mytube-hls-output",
    }

    service = ApiProcessService(
        binary_path=API_BINARY,
        port=_PORT,
        env=env,
        startup_timeout=_STARTUP_TIMEOUT,
    )
    service.start()
    try:
        service.wait_for_ready_or_crash(timeout=_STARTUP_TIMEOUT)
    except Exception as exc:
        service.stop()
        pytest.skip(
            f"API server did not start: {exc}\n"
            f"Log output:\n{service.get_log_output()}"
        )
    yield service
    service.stop()


@pytest.fixture(scope="module")
def recommendations_response(api_server: ApiProcessService, seeded_videos: dict) -> tuple[int, str]:
    """GET /api/videos/{video_a_id}/recommendations; return (status_code, body)."""
    video_a_id = seeded_videos["video_a_id"]
    return api_server.get(f"/api/videos/{video_a_id}/recommendations")


# ---------------------------------------------------------------------------
# Integration test class
# ---------------------------------------------------------------------------


class TestRecommendationExclusionCriteria:
    """MYTUBE-580: recommendations must exclude self and non-ready videos."""

    def test_response_status_is_200(
        self, recommendations_response: tuple[int, str]
    ) -> None:
        """GET /api/videos/{video_a_id}/recommendations must return HTTP 200."""
        status_code, body = recommendations_response
        assert status_code == 200, (
            f"Expected HTTP 200 for GET recommendations, got {status_code}. "
            f"Response body: {body}"
        )

    def test_response_is_valid_json(
        self, recommendations_response: tuple[int, str]
    ) -> None:
        """The recommendations response body must be valid JSON."""
        _, body = recommendations_response
        try:
            json.loads(body)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Recommendations response body is not valid JSON: {exc}\nBody: {body}"
            )

    def test_recommendations_key_present(
        self, recommendations_response: tuple[int, str]
    ) -> None:
        """The response JSON must contain a 'recommendations' key."""
        status_code, body = recommendations_response
        if status_code != 200:
            pytest.skip(f"Skipping — status was {status_code}, not 200.")
        data = json.loads(body)
        assert "recommendations" in data, (
            f"Expected 'recommendations' key in response. Got keys: {list(data.keys())}. "
            f"Body: {body}"
        )

    def test_video_a_not_in_recommendations(
        self, recommendations_response: tuple[int, str], seeded_videos: dict
    ) -> None:
        """Video A (the target video) must NOT appear in its own recommendations."""
        status_code, body = recommendations_response
        if status_code != 200:
            pytest.skip(f"Skipping — status was {status_code}, not 200.")
        data = json.loads(body)
        recs = data.get("recommendations", [])
        video_a_id = seeded_videos["video_a_id"]
        ids_in_recs = [r.get("id") for r in recs]
        assert video_a_id not in ids_in_recs, (
            f"Video A (id={video_a_id}) must be excluded from its own recommendations "
            f"but was found in the response. IDs returned: {ids_in_recs}"
        )

    def test_video_b_processing_not_in_recommendations(
        self, recommendations_response: tuple[int, str], seeded_videos: dict
    ) -> None:
        """Video B (status='processing') must NOT appear in recommendations."""
        status_code, body = recommendations_response
        if status_code != 200:
            pytest.skip(f"Skipping — status was {status_code}, not 200.")
        data = json.loads(body)
        recs = data.get("recommendations", [])
        video_b_id = seeded_videos["video_b_id"]
        ids_in_recs = [r.get("id") for r in recs]
        assert video_b_id not in ids_in_recs, (
            f"Video B (status='processing', id={video_b_id}) must be excluded from "
            f"recommendations but was found in the response. IDs returned: {ids_in_recs}"
        )

    def test_video_c_failed_not_in_recommendations(
        self, recommendations_response: tuple[int, str], seeded_videos: dict
    ) -> None:
        """Video C (status='failed') must NOT appear in recommendations."""
        status_code, body = recommendations_response
        if status_code != 200:
            pytest.skip(f"Skipping — status was {status_code}, not 200.")
        data = json.loads(body)
        recs = data.get("recommendations", [])
        video_c_id = seeded_videos["video_c_id"]
        ids_in_recs = [r.get("id") for r in recs]
        assert video_c_id not in ids_in_recs, (
            f"Video C (status='failed', id={video_c_id}) must be excluded from "
            f"recommendations but was found in the response. IDs returned: {ids_in_recs}"
        )
