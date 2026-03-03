"""
MYTUBE-197: Submit and update video rating — rating is upserted and average calculated correctly.

Objective:
    Verify that an authenticated user can submit a star rating (1-5) and that a
    subsequent rating by the same user updates (upserts) their existing score.
    The returned summary must reflect the correct average_rating, rating_count,
    and my_rating after each operation.

Preconditions
-------------
- User is authenticated with a valid Firebase ID token.
- A video exists in the database.

Test steps
----------
1. Send POST /api/videos/:id/rating with { "stars": 5 }.
2. Verify the response contains average_rating=5.0, rating_count=1, my_rating=5.
3. Send another POST to the same endpoint with { "stars": 2 }.
4. Verify the upserted response: average_rating=2.0, rating_count=1, my_rating=2.

Layer A — Go unit tests (always runs; no Firebase token or DB required):
    Runs all Go handler unit tests for the rating handler to verify the handler
    logic (valid stars, upsert response shape, 401 without auth, 422 for
    out-of-range stars, etc.).

Layer B — Integration test via HTTP (runs when FIREBASE_TEST_TOKEN is set):
    Starts the full Go API server, pre-seeds a user and video row in the DB,
    issues two authenticated POST requests, and asserts the expected summaries.

Environment variables
---------------------
- FIREBASE_TEST_TOKEN     : Valid Firebase ID token (Layer B only).
- FIREBASE_PROJECT_ID     : Firebase project (Layer B; default: "ai-native-478811").
- FIREBASE_TEST_UID       : Firebase UID of the test user (Layer B; default: "ci-test-user-001").
- API_BINARY              : Path to the pre-built Go binary
                            (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE:
                            Database connection settings (Layer B).
- GOOGLE_APPLICATION_CREDENTIALS: Path to GCS service-account JSON
                            (Layer B; falls back to testing/fixtures/mock_service_account.json).
- RAW_UPLOADS_BUCKET      : GCS bucket name (Layer B; default: "mytube-raw-uploads").

Architecture notes
------------------
- Layer A invokes `go test ./internal/handler/ -run TestRatingHandler` via subprocess.
- Layer B uses ApiProcessService (subprocess + HTTP) and AuthService to issue
  authenticated POST requests without raw HTTP calls inline.
- DB seeding is done via psycopg2 with ON CONFLICT DO NOTHING for idempotency.
- Test ratings are deleted in fixture teardown to keep the DB clean.
- No hardcoded values — all config comes from environment variables.
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
from testing.components.services.auth_service import AuthService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_API_DIR = os.path.join(_REPO_ROOT, "api")
_DEFAULT_BINARY = os.path.join(_API_DIR, "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18197
_STARTUP_TIMEOUT = 20.0

_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "ai-native-478811")
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")

_DEFAULT_MOCK_CREDS = os.path.join(
    _REPO_ROOT, "testing", "fixtures", "mock_service_account.json"
)
_MOCK_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", _DEFAULT_MOCK_CREDS)
_RAW_UPLOADS_BUCKET = os.getenv("RAW_UPLOADS_BUCKET", "mytube-raw-uploads")

_TEST_USERNAME = "testuser197"
_TEST_VIDEO_TITLE = "Test Video MYTUBE-197"


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


# ===========================================================================
# Layer A — Go unit tests (always run; no external services required)
# ===========================================================================


class TestRatingHandler_GoUnit:
    """Run the existing Go unit tests for the rating handler."""

    def test_rating_handler_all_unit_tests_pass(self):
        """All Go unit tests for the rating handler must pass.

        Runs TestRatingHandler* to cover:
          - GET returns summary
          - POST with valid stars returns updated summary
          - POST without auth returns 401
          - POST with invalid stars (0, 6, -1) returns 422
          - POST upsert path
          - Video not found returns 404
        """
        result = _run_go_test("TestRatingHandler")
        assert result.returncode == 0, (
            f"One or more Go unit tests for the rating handler failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_post_valid_stars_returns_updated_summary(self):
        """TestRatingHandler_POST_ValidStars_ReturnsUpdatedSummary must pass."""
        result = _run_go_test("TestRatingHandler_POST_ValidStars_ReturnsUpdatedSummary")
        assert result.returncode == 0, (
            f"Go unit test TestRatingHandler_POST_ValidStars_ReturnsUpdatedSummary failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_post_all_valid_star_values(self):
        """TestRatingHandler_POST_AllValidStarValues must pass (stars 1-5)."""
        result = _run_go_test("TestRatingHandler_POST_AllValidStarValues")
        assert result.returncode == 0, (
            f"Go unit test TestRatingHandler_POST_AllValidStarValues failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_post_no_auth_returns_401(self):
        """TestRatingHandler_POST_NoAuth_Returns401 must pass."""
        result = _run_go_test("TestRatingHandler_POST_NoAuth_Returns401")
        assert result.returncode == 0, (
            f"Go unit test TestRatingHandler_POST_NoAuth_Returns401 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_post_invalid_stars_returns_422(self):
        """TestRatingHandler_POST_InvalidStars_Returns422 must pass."""
        result = _run_go_test("TestRatingHandler_POST_InvalidStars_Returns422")
        assert result.returncode == 0, (
            f"Go unit test TestRatingHandler_POST_InvalidStars_Returns422 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


# ===========================================================================
# Layer B — Integration test via HTTP
# Requires FIREBASE_TEST_TOKEN; skipped gracefully when absent.
# ===========================================================================


@pytest.fixture(scope="module")
def firebase_token() -> str:
    """Load the Firebase test token; skip the Layer B tests if absent."""
    token = os.getenv("FIREBASE_TEST_TOKEN", "")
    if not token:
        pytest.skip(
            "FIREBASE_TEST_TOKEN is not set — skipping HTTP integration tests "
            "(Layer A Go unit tests still run)."
        )
    return token


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


def _postgres_available(db_config: DBConfig) -> bool:
    """Return True if PostgreSQL is reachable at the configured host/port."""
    try:
        import psycopg2
        conn = psycopg2.connect(db_config.dsn())
        conn.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def require_db(db_config: DBConfig):
    """Skip Layer B tests when PostgreSQL is not reachable."""
    if not _postgres_available(db_config):
        pytest.skip(
            f"PostgreSQL is not reachable at {db_config.host}:{db_config.port} — "
            "skipping Layer B integration tests. "
            "Ensure DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME are set and "
            "the database is running."
        )


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig, firebase_token: str, require_db):
    """Build (if needed) and start the Go API server; yield it; stop on teardown."""
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
def seeded_test_data(api_server, db_conn):
    """Seed a user and a video row; yield (video_id, user_id); clean up ratings on teardown.

    Uses ON CONFLICT DO NOTHING for idempotency so repeated runs don't fail.
    Deletes only the ratings created by this test, leaving users and videos intact.
    """
    import psycopg2

    # Seed user
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO NOTHING
            """,
            (_FIREBASE_TEST_UID, _TEST_USERNAME),
        )
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (_FIREBASE_TEST_UID,),
        )
        row = cur.fetchone()

    if row is None:
        pytest.fail(
            f"Could not insert or find user row for firebase_uid={_FIREBASE_TEST_UID!r}"
        )
    user_id = str(row[0])

    # Seed video
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO videos (uploader_id, title, status) VALUES (%s, %s, %s) RETURNING id",
            (user_id, _TEST_VIDEO_TITLE, "ready"),
        )
        video_id = str(cur.fetchone()[0])

    yield {"video_id": video_id, "user_id": user_id}

    # Teardown: delete only the ratings created by this test to keep DB clean.
    with db_conn.cursor() as cur:
        cur.execute(
            "DELETE FROM ratings WHERE video_id = %s AND user_id = %s",
            (video_id, user_id),
        )
    # Delete the test video row as well (cascade deletes ratings if any remain).
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM videos WHERE id = %s", (video_id,))


@pytest.fixture(scope="module")
def auth_client(firebase_token: str) -> AuthService:
    """Return an AuthService configured to hit the local test server."""
    return AuthService(base_url=f"http://127.0.0.1:{_PORT}", token=firebase_token)


@pytest.fixture(scope="module")
def first_rating_response(api_server, seeded_test_data, auth_client: AuthService) -> tuple[int, str]:
    """POST /api/videos/:id/rating with stars=5; return (status_code, body)."""
    video_id = seeded_test_data["video_id"]
    return auth_client.post(
        f"/api/videos/{video_id}/rating",
        {"stars": 5},
    )


@pytest.fixture(scope="module")
def updated_rating_response(
    first_rating_response: tuple[int, str],
    seeded_test_data,
    auth_client: AuthService,
) -> tuple[int, str]:
    """POST /api/videos/:id/rating with stars=2 (upsert); depends on first_rating_response.

    The explicit dependency on first_rating_response ensures the first POST
    fires before the upsert POST, making the ordering deterministic.
    """
    video_id = seeded_test_data["video_id"]
    return auth_client.post(
        f"/api/videos/{video_id}/rating",
        {"stars": 2},
    )


# ---------------------------------------------------------------------------
# Integration test class
# ---------------------------------------------------------------------------


class TestSubmitAndUpdateRating:
    """MYTUBE-197: POST /api/videos/:id/rating — initial rating and upsert."""

    # --- First POST (stars=5) ---

    def test_first_rating_status_200(self, first_rating_response: tuple[int, str]):
        """First POST /api/videos/:id/rating with stars=5 must return HTTP 200."""
        status_code, body = first_rating_response
        assert status_code == 200, (
            f"Expected HTTP 200 for first rating POST, got {status_code}. "
            f"Response body: {body}"
        )

    def test_first_rating_response_is_valid_json(self, first_rating_response: tuple[int, str]):
        """First rating response body must be parseable JSON."""
        _, body = first_rating_response
        try:
            json.loads(body)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"First rating response body is not valid JSON: {exc}\nBody: {body}"
            )

    def test_first_rating_fields_present(self, first_rating_response: tuple[int, str]):
        """First rating response must contain average_rating, rating_count, and my_rating."""
        status_code, body = first_rating_response
        if status_code != 200:
            pytest.skip(f"Skipping field assertions — status was {status_code}, not 200.")
        data = json.loads(body)
        for field in ("average_rating", "rating_count", "my_rating"):
            assert field in data, (
                f"Expected '{field}' in first rating response. "
                f"Got keys: {list(data.keys())}. Body: {body}"
            )

    def test_first_rating_average_is_5(self, first_rating_response: tuple[int, str]):
        """After submitting stars=5 as the sole rating, average_rating must be 5.0."""
        status_code, body = first_rating_response
        if status_code != 200:
            pytest.skip(f"Skipping assertion — status was {status_code}, not 200.")
        data = json.loads(body)
        assert data.get("average_rating") == 5.0, (
            f"Expected average_rating=5.0 after stars=5 (sole rating), "
            f"got {data.get('average_rating')!r}. Body: {body}"
        )

    def test_first_rating_count_is_1(self, first_rating_response: tuple[int, str]):
        """After the first rating, rating_count must be 1."""
        status_code, body = first_rating_response
        if status_code != 200:
            pytest.skip(f"Skipping assertion — status was {status_code}, not 200.")
        data = json.loads(body)
        assert data.get("rating_count") == 1, (
            f"Expected rating_count=1 after first rating, "
            f"got {data.get('rating_count')!r}. Body: {body}"
        )

    def test_first_rating_my_rating_is_5(self, first_rating_response: tuple[int, str]):
        """After submitting stars=5, my_rating must be 5."""
        status_code, body = first_rating_response
        if status_code != 200:
            pytest.skip(f"Skipping assertion — status was {status_code}, not 200.")
        data = json.loads(body)
        assert data.get("my_rating") == 5, (
            f"Expected my_rating=5 after stars=5, "
            f"got {data.get('my_rating')!r}. Body: {body}"
        )

    # --- Second POST (stars=2, upsert) ---

    def test_upsert_rating_status_200(self, updated_rating_response: tuple[int, str]):
        """Second POST (upsert) with stars=2 must return HTTP 200."""
        status_code, body = updated_rating_response
        assert status_code == 200, (
            f"Expected HTTP 200 for upsert rating POST, got {status_code}. "
            f"Response body: {body}"
        )

    def test_upsert_rating_response_is_valid_json(self, updated_rating_response: tuple[int, str]):
        """Upsert rating response body must be parseable JSON."""
        _, body = updated_rating_response
        try:
            json.loads(body)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Upsert rating response body is not valid JSON: {exc}\nBody: {body}"
            )

    def test_upsert_rating_fields_present(self, updated_rating_response: tuple[int, str]):
        """Upsert response must contain average_rating, rating_count, and my_rating."""
        status_code, body = updated_rating_response
        if status_code != 200:
            pytest.skip(f"Skipping field assertions — status was {status_code}, not 200.")
        data = json.loads(body)
        for field in ("average_rating", "rating_count", "my_rating"):
            assert field in data, (
                f"Expected '{field}' in upsert rating response. "
                f"Got keys: {list(data.keys())}. Body: {body}"
            )

    def test_upsert_rating_average_is_2(self, updated_rating_response: tuple[int, str]):
        """After upserting stars=2 (sole rater), average_rating must be 2.0."""
        status_code, body = updated_rating_response
        if status_code != 200:
            pytest.skip(f"Skipping assertion — status was {status_code}, not 200.")
        data = json.loads(body)
        assert data.get("average_rating") == 2.0, (
            f"Expected average_rating=2.0 after upsert to stars=2, "
            f"got {data.get('average_rating')!r}. Body: {body}"
        )

    def test_upsert_rating_count_remains_1(self, updated_rating_response: tuple[int, str]):
        """After upserting (same user), rating_count must remain 1."""
        status_code, body = updated_rating_response
        if status_code != 200:
            pytest.skip(f"Skipping assertion — status was {status_code}, not 200.")
        data = json.loads(body)
        assert data.get("rating_count") == 1, (
            f"Expected rating_count=1 after upsert (same user), "
            f"got {data.get('rating_count')!r}. Body: {body}"
        )

    def test_upsert_rating_my_rating_is_2(self, updated_rating_response: tuple[int, str]):
        """After upserting to stars=2, my_rating must be 2."""
        status_code, body = updated_rating_response
        if status_code != 200:
            pytest.skip(f"Skipping assertion — status was {status_code}, not 200.")
        data = json.loads(body)
        assert data.get("my_rating") == 2, (
            f"Expected my_rating=2 after upsert to stars=2, "
            f"got {data.get('my_rating')!r}. Body: {body}"
        )
