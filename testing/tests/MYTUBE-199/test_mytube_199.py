"""
MYTUBE-199: Retrieve video rating metadata — average, count, and personal rating returned.

Verifies that GET /api/videos/:id/rating returns:
  1. For an authenticated user: the correct decimal average, the total
     count, and my_rating matching the user's previously submitted rating.
  2. For an unauthenticated guest: the correct average and count,
     with my_rating = null.

Preconditions
-------------
- Multiple users have rated a video (seeded directly into the test DB).
- The CI test user (FIREBASE_TEST_UID) has also rated the video.
- FIREBASE_TEST_TOKEN is available in the environment (generated at CI runtime
  via Firebase REST API).

Test steps
----------
1. Build and start the Go API server against the test database.
2. Seed:
     - 1 owner/uploader user
     - 3 extra rater users (u1 stars=3, u2 stars=5, u3 stars=4)
     - 1 CI test user (firebase_uid = FIREBASE_TEST_UID, stars=4)
     - 1 video (status=ready)
   Expected aggregate: average=4.0, count=4.
3. GET /api/videos/:id/rating without Authorization → guest path.
4. GET /api/videos/:id/rating with Authorization: Bearer <FIREBASE_TEST_TOKEN>
   → authenticated path (requires FIREBASE_TEST_TOKEN in env; skipped if absent).

Environment variables
---------------------
- FIREBASE_TEST_TOKEN  : Firebase ID token for the CI test user.
                         Generated at CI runtime — skip authenticated tests if absent.
- FIREBASE_TEST_UID    : Firebase UID of the CI test user (default: ci-test-user-001).
- FIREBASE_PROJECT_ID  : Firebase project ID (default: ai-native-478811).
                         Must match the real project to verify FIREBASE_TEST_TOKEN.
- API_BINARY           : Path to the pre-built Go binary
                         (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE : DB config.
"""
import json
import math
import os
import subprocess
import sys
import uuid

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService
from testing.components.services.user_service import UserService
from testing.components.services.video_service import VideoService
from testing.components.services.ratings_service import RatingsService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18199
_STARTUP_TIMEOUT = 25.0

# Mock service account lets the GCS SDK initialise without real GCP credentials.
# The rating endpoint never touches GCS, so this is safe.
_MOCK_SA_PATH = os.path.join(_REPO_ROOT, "testing", "fixtures", "mock_service_account.json")

# Rating values seeded into the DB:
#   rater1=3, rater2=5, rater3=4, ci_test_user=4
# Expected average: (3+5+4+4)/4 = 4.0, count=4
_RATER1_STARS = 3
_RATER2_STARS = 5
_RATER3_STARS = 4
_CI_USER_STARS = 4

_EXPECTED_COUNT = 4
_EXPECTED_AVERAGE = (_RATER1_STARS + _RATER2_STARS + _RATER3_STARS + _CI_USER_STARS) / 4  # 4.0


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


def _drop_all_tables(conn) -> None:
    """Drop all public tables so the API server starts against a clean schema."""
    with conn.cursor() as cur:
        cur.execute(
            """
            DO $$ DECLARE
                r RECORD;
            BEGIN
                FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                    EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                END LOOP;
            END $$;
            """
        )
        cur.execute("DROP FUNCTION IF EXISTS set_updated_at() CASCADE;")


def _db_is_reachable(config: DBConfig) -> bool:
    """Return True if a PostgreSQL connection can be established."""
    try:
        conn = psycopg2.connect(config.dsn(), connect_timeout=3)
        conn.close()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_db():
    """Skip entire module when the test database is not reachable."""
    cfg = DBConfig()
    if not _db_is_reachable(cfg):
        pytest.skip(
            f"PostgreSQL is not reachable at {cfg.host}:{cfg.port} — "
            "skipping integration test. Start the test database to run."
        )


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig):
    """
    Wipe the DB, build the binary if needed, and start the Go API server.

    The server runs its own migrations at startup; we drop all tables first so
    migrations execute cleanly.  All DB seeding happens AFTER the server is up
    (i.e. after migrations have run).

    Yields the ApiProcessService once /health is reachable, then stops on teardown.
    """
    # Wipe before starting so API migrations run on a clean schema.
    pre_conn = psycopg2.connect(db_config.dsn())
    pre_conn.autocommit = True
    try:
        _drop_all_tables(pre_conn)
    finally:
        pre_conn.close()

    _build_binary()

    env = {
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        # Use the real Firebase project ID so that FIREBASE_TEST_TOKEN can be
        # verified when the authenticated tests run.
        "FIREBASE_PROJECT_ID": os.getenv("FIREBASE_PROJECT_ID", "ai-native-478811"),
        # Mock service account satisfies the GCS SDK init; rating endpoint
        # never calls GCS.
        "GOOGLE_APPLICATION_CREDENTIALS": os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS", _MOCK_SA_PATH
        ),
        "RAW_UPLOADS_BUCKET": os.getenv("RAW_UPLOADS_BUCKET", "test-raw-bucket"),
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
def db_conn(db_config: DBConfig, api_server):
    """
    Open a direct psycopg2 connection for seeding.

    Depends on *api_server* so migrations have already run before we insert rows.
    """
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_data(db_conn):
    """
    Seed the DB with:
      - 1 owner user
      - 3 extra rater users rated with stars 3, 5, 4
      - 1 CI test user (firebase_uid=FIREBASE_TEST_UID) rated with stars 4
      - 1 ready video

    Returns a dict with video_id and ci_user_id.
    """
    firebase_test_uid = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")

    user_svc = UserService(db_conn)
    video_svc = VideoService(db_conn)
    ratings_svc = RatingsService(db_conn)

    # Unique suffix to avoid FK/unique conflicts across test runs on the same DB.
    suffix = uuid.uuid4().hex[:8]

    owner_id = user_svc.create_user(f"owner-uid-{suffix}", f"owner199-{suffix}")
    rater1_id = user_svc.create_user(f"rater1-uid-{suffix}", f"rater199a-{suffix}")
    rater2_id = user_svc.create_user(f"rater2-uid-{suffix}", f"rater199b-{suffix}")
    rater3_id = user_svc.create_user(f"rater3-uid-{suffix}", f"rater199c-{suffix}")

    # The CI test user's firebase_uid must match the token we send.
    # Use the existing user if already seeded by another test module sharing this DB.
    existing = user_svc.find_by_firebase_uid(firebase_test_uid)
    if existing:
        ci_user_id = existing["id"]
    else:
        ci_user_id = user_svc.create_user(firebase_test_uid, f"ci-user-199-{suffix}")

    video_row = video_svc.insert_video(owner_id, "Test Rating Video MYTUBE-199", "ready")
    video_id = str(video_row[0])

    ratings_svc.insert_rating(video_id, rater1_id, _RATER1_STARS)
    ratings_svc.insert_rating(video_id, rater2_id, _RATER2_STARS)
    ratings_svc.insert_rating(video_id, rater3_id, _RATER3_STARS)
    ratings_svc.insert_rating(video_id, ci_user_id, _CI_USER_STARS)

    return {
        "video_id": video_id,
        "ci_user_id": ci_user_id,
        "firebase_test_uid": firebase_test_uid,
    }


@pytest.fixture(scope="module")
def guest_response(api_server, seeded_data):
    """Issue GET /api/videos/:id/rating without any Authorization header."""
    status, body = api_server.get(f"/api/videos/{seeded_data['video_id']}/rating")
    return {"status": status, "body": body}


@pytest.fixture(scope="module")
def authed_response(api_server, seeded_data):
    """Issue GET /api/videos/:id/rating with a valid Firebase Bearer token.

    Skips if FIREBASE_TEST_TOKEN is not set in the environment.
    """
    token = os.getenv("FIREBASE_TEST_TOKEN", "")
    if not token:
        pytest.skip(
            "FIREBASE_TEST_TOKEN is not set. "
            "This token is generated at CI runtime via the Firebase REST API. "
            "Set FIREBASE_TEST_TOKEN to run the authenticated path locally."
        )
    status, body = api_server.get(
        f"/api/videos/{seeded_data['video_id']}/rating",
        headers={"Authorization": f"Bearer {token}"},
    )
    return {"status": status, "body": body}


# ---------------------------------------------------------------------------
# Tests — Guest (unauthenticated)
# ---------------------------------------------------------------------------


class TestGuestRatingResponse:
    """GET /api/videos/:id/rating without auth returns correct aggregate and my_rating=null."""

    def test_returns_200(self, guest_response):
        """Guest GET must return HTTP 200."""
        assert guest_response["status"] == 200, (
            f"Expected HTTP 200, got {guest_response['status']}. "
            f"Body: {guest_response['body']}"
        )

    def test_response_is_valid_json(self, guest_response):
        """Response body must be valid JSON."""
        try:
            json.loads(guest_response["body"])
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Response is not valid JSON: {exc}\nBody: {guest_response['body']}"
            )

    def test_response_has_required_fields(self, guest_response):
        """Response must include average, count, and my_rating."""
        data = json.loads(guest_response["body"])
        for field in ("average", "count", "my_rating"):
            assert field in data, (
                f"Expected field '{field}' in response, got: {list(data.keys())}"
            )

    def test_rating_count_is_correct(self, guest_response):
        """count must equal the number of seeded ratings."""
        data = json.loads(guest_response["body"])
        assert data["count"] == _EXPECTED_COUNT, (
            f"Expected count={_EXPECTED_COUNT}, got {data['count']}. "
            f"Body: {guest_response['body']}"
        )

    def test_average_rating_is_correct(self, guest_response):
        """average must equal the arithmetic mean of all seeded ratings."""
        data = json.loads(guest_response["body"])
        assert math.isclose(data["average"], _EXPECTED_AVERAGE, abs_tol=0.01), (
            f"Expected average≈{_EXPECTED_AVERAGE}, got {data['average']}. "
            f"Body: {guest_response['body']}"
        )

    def test_my_rating_is_null_for_guest(self, guest_response):
        """my_rating must be null for an unauthenticated guest."""
        data = json.loads(guest_response["body"])
        assert data["my_rating"] is None, (
            f"Expected my_rating=null for unauthenticated guest, "
            f"got {data['my_rating']}. Body: {guest_response['body']}"
        )


# ---------------------------------------------------------------------------
# Tests — Authenticated
# ---------------------------------------------------------------------------


class TestAuthenticatedRatingResponse:
    """GET /api/videos/:id/rating with a valid Firebase token returns correct my_rating."""

    def test_returns_200(self, authed_response):
        """Authenticated GET must return HTTP 200."""
        assert authed_response["status"] == 200, (
            f"Expected HTTP 200, got {authed_response['status']}. "
            f"Body: {authed_response['body']}"
        )

    def test_response_is_valid_json(self, authed_response):
        """Response body must be valid JSON."""
        try:
            json.loads(authed_response["body"])
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Response is not valid JSON: {exc}\nBody: {authed_response['body']}"
            )

    def test_rating_count_is_correct(self, authed_response):
        """count must equal the total number of seeded ratings."""
        data = json.loads(authed_response["body"])
        assert data["count"] == _EXPECTED_COUNT, (
            f"Expected count={_EXPECTED_COUNT}, got {data['count']}. "
            f"Body: {authed_response['body']}"
        )

    def test_average_rating_is_correct(self, authed_response):
        """average must equal the arithmetic mean of all seeded ratings."""
        data = json.loads(authed_response["body"])
        assert math.isclose(data["average"], _EXPECTED_AVERAGE, abs_tol=0.01), (
            f"Expected average≈{_EXPECTED_AVERAGE}, got {data['average']}. "
            f"Body: {authed_response['body']}"
        )

    def test_my_rating_matches_user_previous_rating(self, authed_response):
        """my_rating must equal the authenticated user's previously submitted rating.

        The CI test user submitted stars={_CI_USER_STARS}.  The endpoint must
        identify this user via the Bearer token and return that value.

        If my_rating is null despite a valid token being sent, it likely means
        the GET /api/videos/{{id}}/rating handler is missing OptionalAuth
        middleware — so claims are never placed in the request context for GET.
        """
        data = json.loads(authed_response["body"])
        assert data["my_rating"] == _CI_USER_STARS, (
            f"Expected my_rating={_CI_USER_STARS} for authenticated user "
            f"(CI test user with stars={_CI_USER_STARS}), "
            f"got my_rating={data['my_rating']}. "
            f"Full response: {authed_response['body']}. "
            f"This may indicate that GET /api/videos/{{id}}/rating is not "
            f"wrapped with OptionalAuth middleware in main.go, so the Bearer "
            f"token is never processed and ClaimsFromContext always returns nil."
        )
