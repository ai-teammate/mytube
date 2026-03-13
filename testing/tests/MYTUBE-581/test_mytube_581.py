"""
MYTUBE-581: Recommendation API result limit — response contains no more than 8 videos.

Objective
---------
Verify that the recommendation endpoint enforces the maximum limit of 8 results.

Preconditions
-------------
At least 10 videos exist in the database sharing the same category as the target Video A.

Steps
-----
1. Send a GET request to /api/videos/[ID_of_Video_A]/recommendations.
2. Count the number of items in the returned array.

Expected Result
---------------
The response contains exactly 8 video objects (the configured maximum limit).

Architecture notes
------------------
- Seeds one test user + 1 target video + 11 candidate videos (all status='ready',
  hls_manifest_path set, same category_id) directly into the DB.
- Starts the Go API binary via ApiProcessService.
- Issues GET /api/videos/{id}/recommendations.
- Asserts that ``body["recommendations"]`` has exactly 8 items (the hard limit).
- Full teardown removes all seeded rows in FK-safe order.

Environment variables
---------------------
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
  Database connection settings with sensible defaults.
- API_BINARY : Path to pre-built Go binary
  (default: <repo_root>/api/mytube-api).
- FIREBASE_PROJECT_ID : Firebase project ID (required by the Go binary init;
  test is skipped when absent).
- GOOGLE_APPLICATION_CREDENTIALS : Path to service-account JSON.

Run from repo root:
    pytest testing/tests/MYTUBE-581/test_mytube_581.py -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error

import psycopg2
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
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18581
_STARTUP_TIMEOUT = 25.0

_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")

_DEFAULT_MOCK_CREDS = os.path.join(
    _REPO_ROOT, "testing", "fixtures", "mock_service_account.json"
)
_MOCK_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", _DEFAULT_MOCK_CREDS)
_RAW_UPLOADS_BUCKET = os.getenv("RAW_UPLOADS_BUCKET", "mytube-raw-uploads")

_TEST_FIREBASE_UID = "test-uid-mytube-581"
_TEST_USERNAME = "testuser_mytube581"

# Number of candidate videos to seed; with the 8-item hard limit this ensures
# the limit is actually enforced (11 candidates → only 8 returned).
_NUM_CANDIDATES = 11

# The hard limit enforced by the API (handler.recommendationsLimit = 8).
_EXPECTED_LIMIT = 8


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_binary() -> None:
    """Build the Go API binary if it is not already present."""
    if os.path.isfile(API_BINARY):
        return
    api_dir = os.path.join(_REPO_ROOT, "api")
    result = subprocess.run(
        ["go", "build", "-o", API_BINARY, "."],
        cwd=api_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(
            f"Failed to build API binary:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


def _get_or_create_category(cur, name: str) -> int:
    """Return the id of the named category, inserting it if it does not exist."""
    cur.execute("SELECT id FROM categories WHERE name = %s", (name,))
    row = cur.fetchone()
    if row:
        return int(row[0])
    cur.execute(
        "INSERT INTO categories (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id",
        (name,),
    )
    row = cur.fetchone()
    if row:
        return int(row[0])
    # Race: inserted by another session between SELECT and INSERT.
    cur.execute("SELECT id FROM categories WHERE name = %s", (name,))
    return int(cur.fetchone()[0])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_firebase_credentials():
    """Skip the entire module when FIREBASE_PROJECT_ID is not available."""
    if not _FIREBASE_PROJECT_ID:
        pytest.skip(
            "FIREBASE_PROJECT_ID not set — the API server cannot initialise "
            "the Firebase verifier without this variable."
        )


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig):
    """Build (if needed) and start the Go API server in a subprocess."""
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
            f"API server did not become ready within {_STARTUP_TIMEOUT}s.\n"
            f"Logs:\n{logs}"
        )

    yield svc
    svc.stop()


@pytest.fixture(scope="module")
def db_conn(db_config: DBConfig):
    """Open a direct psycopg2 connection for test-data setup and assertions."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_data(api_server, db_conn):
    """Seed:  user → 1 target video + 11 candidate videos (same category).

    All videos are status='ready' with a non-null hls_manifest_path so they
    qualify for the recommendations query.

    Teardown removes all seeded rows in FK-safe order.
    """
    with db_conn.cursor() as cur:
        # Ensure test user exists.
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO NOTHING
            """,
            (_TEST_FIREBASE_UID, _TEST_USERNAME),
        )
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (_TEST_FIREBASE_UID,),
        )
        row = cur.fetchone()
        if row is None:
            pytest.fail(
                f"Could not insert/find user for firebase_uid={_TEST_FIREBASE_UID!r}"
            )
        user_id = str(row[0])

        # Resolve category id (use 'Education' which is seeded in migrations).
        category_id = _get_or_create_category(cur, "Education")

        # Seed target video (the one we'll request recommendations for).
        cur.execute(
            """
            INSERT INTO videos (uploader_id, title, status, hls_manifest_path, category_id)
            VALUES (%s, %s, 'ready', %s, %s)
            RETURNING id
            """,
            (
                user_id,
                "Target Video for MYTUBE-581",
                "gs://bucket/target/manifest.m3u8",
                category_id,
            ),
        )
        target_video_id = str(cur.fetchone()[0])

        # Seed 11 candidate videos in the same category.
        candidate_ids = []
        for i in range(_NUM_CANDIDATES):
            cur.execute(
                """
                INSERT INTO videos (uploader_id, title, status, hls_manifest_path, category_id)
                VALUES (%s, %s, 'ready', %s, %s)
                RETURNING id
                """,
                (
                    user_id,
                    f"Candidate Video {i + 1} for MYTUBE-581",
                    f"gs://bucket/candidate{i}/manifest.m3u8",
                    category_id,
                ),
            )
            candidate_ids.append(str(cur.fetchone()[0]))

    yield {
        "user_id": user_id,
        "target_video_id": target_video_id,
        "candidate_ids": candidate_ids,
    }

    # Teardown — delete in FK-safe order.
    with db_conn.cursor() as cur:
        all_video_ids = [target_video_id] + candidate_ids
        fmt = ",".join(["%s"] * len(all_video_ids))
        cur.execute(f"DELETE FROM ratings  WHERE video_id IN ({fmt})", all_video_ids)
        cur.execute(f"DELETE FROM comments WHERE video_id IN ({fmt})", all_video_ids)
        cur.execute(f"DELETE FROM video_tags WHERE video_id IN ({fmt})", all_video_ids)
        cur.execute(
            f"DELETE FROM playlist_videos WHERE video_id IN ({fmt})", all_video_ids
        )
        cur.execute(f"DELETE FROM videos WHERE id IN ({fmt})", all_video_ids)
        cur.execute(
            "DELETE FROM users WHERE firebase_uid = %s", (_TEST_FIREBASE_UID,)
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRecommendationAPIResultLimit:
    """MYTUBE-581: GET /api/videos/{id}/recommendations must return ≤ 8 items."""

    def test_recommendations_capped_at_eight(self, seeded_data: dict) -> None:
        """
        Step 1: Send GET /api/videos/{target_id}/recommendations.
        Step 2: Count items in the returned array.
        Expected: exactly 8 video objects (hard limit enforced by the API).
        """
        target_id = seeded_data["target_video_id"]
        url = f"http://localhost:{_PORT}/api/videos/{target_id}/recommendations"

        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status_code = resp.status
                body_raw = resp.read().decode()
        except urllib.error.HTTPError as exc:
            pytest.fail(
                f"GET {url} returned HTTP {exc.code}.\n"
                f"Response body: {exc.read().decode()}"
            )
        except Exception as exc:
            pytest.fail(f"Failed to reach the API at {url}: {exc}")

        assert status_code == 200, (
            f"Expected HTTP 200, got {status_code}.\nBody: {body_raw}"
        )

        try:
            body = json.loads(body_raw)
        except json.JSONDecodeError as exc:
            pytest.fail(f"Response is not valid JSON: {exc}\nRaw: {body_raw}")

        assert isinstance(body, dict), (
            f"Expected JSON object, got {type(body).__name__}: {body_raw}"
        )
        assert "recommendations" in body, (
            f"'recommendations' key missing from response: {body_raw}"
        )

        recs = body["recommendations"]
        assert isinstance(recs, list), (
            f"'recommendations' should be a list, got {type(recs).__name__}: {body_raw}"
        )

        assert len(recs) == _EXPECTED_LIMIT, (
            f"Expected exactly {_EXPECTED_LIMIT} recommendations (limit enforced by API), "
            f"but got {len(recs)}.\n"
            f"Seeded {_NUM_CANDIDATES} candidate videos in the same category.\n"
            f"Full response: {body_raw}"
        )

    def test_each_recommendation_has_required_fields(self, seeded_data: dict) -> None:
        """Each item in the recommendations array must contain the required fields."""
        target_id = seeded_data["target_video_id"]
        url = f"http://localhost:{_PORT}/api/videos/{target_id}/recommendations"

        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode())
        except Exception as exc:
            pytest.fail(f"Failed to reach the API at {url}: {exc}")

        recs = body.get("recommendations", [])
        required_fields = {"id", "title", "view_count", "uploader_username", "created_at"}

        for i, item in enumerate(recs):
            missing = required_fields - set(item.keys())
            assert not missing, (
                f"Recommendation[{i}] is missing fields {missing}.\nItem: {item}"
            )

    def test_target_video_not_in_recommendations(self, seeded_data: dict) -> None:
        """The target video itself must not appear among its own recommendations."""
        target_id = seeded_data["target_video_id"]
        url = f"http://localhost:{_PORT}/api/videos/{target_id}/recommendations"

        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode())
        except Exception as exc:
            pytest.fail(f"Failed to reach the API at {url}: {exc}")

        recs = body.get("recommendations", [])
        rec_ids = [r["id"] for r in recs]

        assert target_id not in rec_ids, (
            f"Target video {target_id!r} appeared in its own recommendations list: {rec_ids}"
        )
