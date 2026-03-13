"""
MYTUBE-579: Retrieve video recommendations — results filtered by category or tags
and sorted by views.

Objective
---------
Verify that GET /api/videos/{id}/recommendations returns videos sharing the same
category or tags as the target video, prioritised by view_count (highest first).

Preconditions
-------------
* Video A (target)  — category 'Gaming', tags ['rpg', 'open-world']
* Video B           — category 'Gaming', view_count: 100
* Video C           — category 'Music',  tag 'rpg',    view_count: 50
* Video D           — category 'Education', no matching tags

Steps
-----
1. Send GET /api/videos/{ID_of_Video_A}/recommendations
2. Inspect the JSON response body.

Expected Result
---------------
* HTTP 200 OK.
* Response body contains a ``recommendations`` array.
* Video B and Video C are present; Video D is absent.
* Video B appears before Video C (view_count 100 > 50).

Architecture
------------
Two layers:

Layer A — Go unit tests (always runs; no DB or API required):
  Exercises the handler stub-layer to verify correct behaviour for the
  success path, empty results, repository errors, invalid IDs, wrong method,
  content-type, and field mapping.

Layer B — HTTP integration test (skipped when DB is unreachable):
  Seeds user + four videos with appropriate category_ids, tags, view_counts,
  and hls_manifest_path, then issues the real HTTP request and asserts the
  expected filtering and ordering.

Environment Variables
---------------------
API_BINARY              Pre-built Go binary (default: <repo_root>/api/mytube-api).
DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE
                        Database connection settings.
FIREBASE_PROJECT_ID     Firebase project (default: "ai-native-478811").
GOOGLE_APPLICATION_CREDENTIALS
                        GCS service-account JSON (default: testing/fixtures/mock_service_account.json).
RAW_UPLOADS_BUCKET      GCS bucket name (default: "mytube-raw-uploads").

Run from repo root:
    pytest testing/tests/MYTUBE-579/test_mytube_579.py -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_API_DIR = os.path.join(_REPO_ROOT, "api")
_DEFAULT_BINARY = os.path.join(_API_DIR, "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18579
_STARTUP_TIMEOUT = 20.0

_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "ai-native-478811")
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "ci-test-user-579")

_DEFAULT_MOCK_CREDS = os.path.join(_REPO_ROOT, "testing", "fixtures", "mock_service_account.json")
_MOCK_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", _DEFAULT_MOCK_CREDS)
_RAW_UPLOADS_BUCKET = os.getenv("RAW_UPLOADS_BUCKET", "mytube-raw-uploads")

_TEST_USERNAME = "testuser_rec_579"

# Fake HLS path so the DB constraint (chk_ready_requires_hls) is satisfied.
_FAKE_HLS_PATH = "gs://mytube-hls/ci-test-579/master.m3u8"


# ===========================================================================
# Helpers
# ===========================================================================


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


def _postgres_available(db_config: DBConfig) -> bool:
    """Return True if PostgreSQL is reachable at the configured host/port."""
    try:
        import psycopg2

        conn = psycopg2.connect(db_config.dsn())
        conn.close()
        return True
    except Exception:
        return False


def _get_recommendations(base_url: str, video_id: str) -> tuple[int, dict | None]:
    """GET /api/videos/{video_id}/recommendations; return (status_code, body_dict)."""
    url = f"{base_url}/api/videos/{video_id}/recommendations"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            return resp.status, body
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode())
        except Exception:
            body = None
        return exc.code, body
    except Exception:
        return 0, None


def _get_or_create_category(conn, name: str) -> int:
    """Return the id of the category with *name*, inserting it if absent."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM categories WHERE name = %s", (name,))
        row = cur.fetchone()
    if row:
        return row[0]
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO categories (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id",
            (name,),
        )
        row = cur.fetchone()
    if row:
        return row[0]
    # Already inserted concurrently; fetch again.
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM categories WHERE name = %s", (name,))
        return cur.fetchone()[0]


def _insert_video(
    conn,
    uploader_id: str,
    title: str,
    category_id: int | None,
    view_count: int,
    tags: list[str],
) -> str:
    """Insert a ready video with a fake HLS path; return its UUID string."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO videos
                (uploader_id, title, status, category_id, view_count, hls_manifest_path)
            VALUES (%s, %s, 'ready', %s, %s, %s)
            RETURNING id
            """,
            (uploader_id, title, category_id, view_count, _FAKE_HLS_PATH),
        )
        video_id = str(cur.fetchone()[0])
    for tag in tags:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO video_tags (video_id, tag) VALUES (%s, %s)",
                (video_id, tag),
            )
    return video_id


def _cleanup(conn, user_id: str, video_ids: list[str]) -> None:
    """Remove seeded rows in FK-safe order."""
    with conn.cursor() as cur:
        if video_ids:
            id_ph = ",".join(["%s"] * len(video_ids))
            cur.execute(f"DELETE FROM video_tags WHERE video_id IN ({id_ph})", video_ids)
            cur.execute(f"DELETE FROM videos WHERE id IN ({id_ph})", video_ids)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))


# ===========================================================================
# Layer A — Go unit tests (always run; no external services required)
# ===========================================================================


class TestRecommendationsHandler_GoUnit:
    """Go unit tests covering the recommendations HTTP handler."""

    def test_success_returns_list(self) -> None:
        """TestRecommendationsHandler_GET_Success_ReturnsList must pass."""
        result = _run_go_test("TestRecommendationsHandler_GET_Success_ReturnsList")
        assert result.returncode == 0, (
            f"Go unit test TestRecommendationsHandler_GET_Success_ReturnsList failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_empty_slice_when_no_recommendations(self) -> None:
        """TestRecommendationsHandler_GET_EmptySlice_WhenNoRecommendations must pass."""
        result = _run_go_test("TestRecommendationsHandler_GET_EmptySlice_WhenNoRecommendations")
        assert result.returncode == 0, (
            f"Go unit test TestRecommendationsHandler_GET_EmptySlice_WhenNoRecommendations failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_repository_error_returns_500(self) -> None:
        """TestRecommendationsHandler_GET_RepositoryError_Returns500 must pass."""
        result = _run_go_test("TestRecommendationsHandler_GET_RepositoryError_Returns500")
        assert result.returncode == 0, (
            f"Go unit test TestRecommendationsHandler_GET_RepositoryError_Returns500 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_unsupported_method_returns_405(self) -> None:
        """TestRecommendationsHandler_UnsupportedMethod_Returns405 must pass."""
        result = _run_go_test("TestRecommendationsHandler_UnsupportedMethod_Returns405")
        assert result.returncode == 0, (
            f"Go unit test TestRecommendationsHandler_UnsupportedMethod_Returns405 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_invalid_video_id_returns_400(self) -> None:
        """TestRecommendationsHandler_InvalidVideoID_Returns400 must pass."""
        result = _run_go_test("TestRecommendationsHandler_InvalidVideoID_Returns400")
        assert result.returncode == 0, (
            f"Go unit test TestRecommendationsHandler_InvalidVideoID_Returns400 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_content_type_is_json(self) -> None:
        """TestRecommendationsHandler_GET_ContentTypeIsJSON must pass."""
        result = _run_go_test("TestRecommendationsHandler_GET_ContentTypeIsJSON")
        assert result.returncode == 0, (
            f"Go unit test TestRecommendationsHandler_GET_ContentTypeIsJSON failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_all_fields_mapped_correctly(self) -> None:
        """TestRecommendationsHandler_GET_AllFieldsMappedCorrectly must pass."""
        result = _run_go_test("TestRecommendationsHandler_GET_AllFieldsMappedCorrectly")
        assert result.returncode == 0, (
            f"Go unit test TestRecommendationsHandler_GET_AllFieldsMappedCorrectly failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


# ===========================================================================
# Layer B — HTTP integration test
# Requires a reachable PostgreSQL database; skipped gracefully when absent.
# ===========================================================================


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def require_db(db_config: DBConfig):
    """Skip Layer B tests when PostgreSQL is not reachable."""
    if not _postgres_available(db_config):
        pytest.skip(
            f"PostgreSQL not reachable at {db_config.host}:{db_config.port} — "
            "skipping Layer B integration tests."
        )


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig, require_db):
    """Build (if needed) and start the Go API server; stop on teardown."""
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
        "RAW_UPLOADS_BUCKET": _RAW_UPLOADS_BUCKET,
    }
    svc = ApiProcessService(
        binary_path=API_BINARY,
        port=_PORT,
        env=env,
        startup_timeout=_STARTUP_TIMEOUT,
    )
    svc.start()
    ready = svc.wait_for_ready(path="/health")
    if not ready:
        logs = svc.get_log_output()
        svc.stop()
        pytest.fail(
            f"API server did not become ready within {_STARTUP_TIMEOUT}s.\nLogs:\n{logs}"
        )
    yield svc
    svc.stop()


@pytest.fixture(scope="module")
def db_conn(db_config: DBConfig, require_db):
    """Open a direct psycopg2 connection to the test database."""
    try:
        import psycopg2
    except ImportError:
        pytest.skip("psycopg2 not installed — skipping Layer B integration test.")

    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_data(api_server, db_conn):
    """
    Seed the four test videos and yield a dict with their IDs.

    Video A — target video: category 'Gaming', tags ['rpg', 'open-world']
    Video B — category 'Gaming', view_count 100 (should appear first)
    Video C — category 'Music',  tag 'rpg',    view_count 50 (should appear second)
    Video D — category 'Education', no matching tags (should NOT appear)

    Teardown removes all seeded rows.
    """
    # Ensure test user exists.
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO NOTHING
            """,
            (_FIREBASE_TEST_UID, _TEST_USERNAME),
        )
        cur.execute("SELECT id FROM users WHERE firebase_uid = %s", (_FIREBASE_TEST_UID,))
        row = cur.fetchone()
    if row is None:
        pytest.fail(
            f"Could not insert or find user row for firebase_uid={_FIREBASE_TEST_UID!r}"
        )
    user_id = str(row[0])

    # Resolve category IDs from the seeded categories table.
    cat_gaming = _get_or_create_category(db_conn, "Gaming")
    cat_music = _get_or_create_category(db_conn, "Music")
    cat_education = _get_or_create_category(db_conn, "Education")

    # Insert videos.
    video_a = _insert_video(db_conn, user_id, "Video A — Gaming rpg open-world (target)", cat_gaming, 10, ["rpg", "open-world"])
    video_b = _insert_video(db_conn, user_id, "Video B — Gaming 100 views", cat_gaming, 100, [])
    video_c = _insert_video(db_conn, user_id, "Video C — Music rpg 50 views", cat_music, 50, ["rpg"])
    video_d = _insert_video(db_conn, user_id, "Video D — Education no match", cat_education, 200, [])

    yield {
        "user_id": user_id,
        "video_a": video_a,
        "video_b": video_b,
        "video_c": video_c,
        "video_d": video_d,
    }

    _cleanup(db_conn, user_id, [video_a, video_b, video_c, video_d])


@pytest.fixture(scope="module")
def recommendations_response(api_server, seeded_data) -> tuple[int, dict]:
    """Issue GET /api/videos/{video_a}/recommendations; return (status_code, body)."""
    os.environ["API_BASE_URL"] = f"http://127.0.0.1:{_PORT}"
    base_url = f"http://127.0.0.1:{_PORT}"
    video_a = seeded_data["video_a"]
    status_code, body = _get_recommendations(base_url, video_a)
    if status_code == 0:
        pytest.fail(
            f"GET /api/videos/{video_a}/recommendations returned status 0 — "
            "the API server appears to be unreachable."
        )
    return status_code, body


# ---------------------------------------------------------------------------
# Integration test class
# ---------------------------------------------------------------------------


class TestRecommendationsFiltering:
    """Integration tests for GET /api/videos/{id}/recommendations."""

    def test_status_code_is_200(self, recommendations_response: tuple[int, dict], seeded_data: dict) -> None:
        """The endpoint must return HTTP 200 OK."""
        status_code, body = recommendations_response
        assert status_code == 200, (
            f"Expected HTTP 200 from GET /api/videos/{seeded_data['video_a']}/recommendations, "
            f"got {status_code}. Body: {json.dumps(body)}"
        )

    def test_response_has_recommendations_key(self, recommendations_response: tuple[int, dict], seeded_data: dict) -> None:
        """Response body must contain a 'recommendations' key."""
        _, body = recommendations_response
        assert body is not None and "recommendations" in body, (
            f"Expected 'recommendations' key in response body. "
            f"Got: {json.dumps(body)}"
        )

    def test_recommendations_is_list(self, recommendations_response: tuple[int, dict]) -> None:
        """'recommendations' value must be a JSON array."""
        _, body = recommendations_response
        recs = body.get("recommendations")
        assert isinstance(recs, list), (
            f"Expected 'recommendations' to be a list, got {type(recs).__name__}. "
            f"Body: {json.dumps(body)}"
        )

    def test_video_b_is_present(self, recommendations_response: tuple[int, dict], seeded_data: dict) -> None:
        """Video B (same category 'Gaming') must appear in recommendations."""
        _, body = recommendations_response
        recs = body.get("recommendations", [])
        rec_ids = [r.get("id") for r in recs]
        assert seeded_data["video_b"] in rec_ids, (
            f"Expected Video B (id={seeded_data['video_b']!r}) to be in recommendations "
            f"(same category 'Gaming' as Video A), but it was absent. "
            f"Returned IDs: {rec_ids}"
        )

    def test_video_c_is_present(self, recommendations_response: tuple[int, dict], seeded_data: dict) -> None:
        """Video C (shares tag 'rpg') must appear in recommendations."""
        _, body = recommendations_response
        recs = body.get("recommendations", [])
        rec_ids = [r.get("id") for r in recs]
        assert seeded_data["video_c"] in rec_ids, (
            f"Expected Video C (id={seeded_data['video_c']!r}) to be in recommendations "
            f"(shares tag 'rpg' with Video A), but it was absent. "
            f"Returned IDs: {rec_ids}"
        )

    def test_video_d_is_absent(self, recommendations_response: tuple[int, dict], seeded_data: dict) -> None:
        """Video D (category 'Education', no shared tags) must NOT appear."""
        _, body = recommendations_response
        recs = body.get("recommendations", [])
        rec_ids = [r.get("id") for r in recs]
        assert seeded_data["video_d"] not in rec_ids, (
            f"Expected Video D (id={seeded_data['video_d']!r}) to be absent from "
            f"recommendations (different category 'Education' and no shared tags), "
            f"but it was present. Returned IDs: {rec_ids}"
        )

    def test_video_a_is_absent(self, recommendations_response: tuple[int, dict], seeded_data: dict) -> None:
        """The target video itself must NOT appear in its own recommendations."""
        _, body = recommendations_response
        recs = body.get("recommendations", [])
        rec_ids = [r.get("id") for r in recs]
        assert seeded_data["video_a"] not in rec_ids, (
            f"Expected Video A (id={seeded_data['video_a']!r}) to be absent from "
            f"its own recommendations, but it appeared. Returned IDs: {rec_ids}"
        )

    def test_video_b_before_video_c(self, recommendations_response: tuple[int, dict], seeded_data: dict) -> None:
        """Video B (view_count=100) must appear before Video C (view_count=50) in results."""
        _, body = recommendations_response
        recs = body.get("recommendations", [])
        rec_ids = [r.get("id") for r in recs]
        video_b = seeded_data["video_b"]
        video_c = seeded_data["video_c"]
        if video_b not in rec_ids or video_c not in rec_ids:
            pytest.skip("Both Video B and Video C must be present to test ordering.")
        idx_b = rec_ids.index(video_b)
        idx_c = rec_ids.index(video_c)
        assert idx_b < idx_c, (
            f"Expected Video B (view_count=100, index={idx_b}) to appear before "
            f"Video C (view_count=50, index={idx_c}) in the recommendations list "
            f"(results should be sorted by view_count DESC). "
            f"Returned IDs: {rec_ids}"
        )

    def test_each_recommendation_has_required_fields(
        self, recommendations_response: tuple[int, dict], seeded_data: dict
    ) -> None:
        """Each recommendation item must contain id, title, view_count, uploader_username, created_at."""
        _, body = recommendations_response
        recs = body.get("recommendations", [])
        required_fields = {"id", "title", "view_count", "uploader_username", "created_at"}
        for item in recs:
            missing = required_fields - set(item.keys())
            assert not missing, (
                f"Recommendation item is missing fields {missing}. "
                f"Item: {json.dumps(item)}"
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
