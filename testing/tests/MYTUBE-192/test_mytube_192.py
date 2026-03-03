"""
MYTUBE-192: View video list on dashboard — grid displays correct metadata and status badges.

Verifies that the video management dashboard (/dashboard) correctly renders the
list of user videos with all required visual elements.

Objective
---------
Verify that the dashboard at /dashboard displays a table or grid containing the
user's videos. Each item must correctly show the thumbnail (or placeholder), title,
status badge, view count, and formatted creation date.

Preconditions
-------------
- User is authenticated via Firebase.
- The user has at least two videos in the database: one "ready" and one "processing".
- The web application is deployed and reachable at WEB_BASE_URL.
- Firebase test credentials are available (FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD).
- The database is reachable at the configured DB_* env vars.

Test steps
----------
1. Resolve the real Firebase UID for the test user via the Firebase REST sign-in API.
2. Seed a test user in the DB (idempotent — matched by the resolved Firebase UID):
   - One video with status "ready" and title "MYTUBE-192 Ready Video".
   - One video with status "processing" and title "MYTUBE-192 Processing Video".
3. Log in via /login using FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD.
4. Navigate to /dashboard.
5. Wait for the video table to render.
6. Assert the video table is visible.
7. Assert the "ready" video title appears in the table.
8. Assert the status badge for the "ready" video shows "ready".
9. Assert the status badge for the "processing" video shows "processing".
10. Assert the thumbnail cell for the "ready" video contains an <img> or placeholder div.
11. Assert the view count cell for the "ready" video is non-empty.
12. Assert the creation date cell for the "ready" video contains at least one digit.

Environment variables
---------------------
FIREBASE_TEST_EMAIL    : Email of the registered Firebase test user (required).
FIREBASE_TEST_PASSWORD : Password of the registered Firebase test user (required).
FIREBASE_API_KEY       : Firebase web API key, used to resolve the real UID before seeding.
                         Falls back to FIREBASE_TEST_UID when not set.
FIREBASE_TEST_UID      : Fallback Firebase UID (default: ci-test-user-001).
WEB_BASE_URL / APP_URL : Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                         Database connection settings.
PLAYWRIGHT_HEADLESS    : Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO     : Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses DashboardPage (Page Object) from testing/components/pages/dashboard_page/.
- Uses LoginPage (Page Object) from testing/components/pages/login_page/.
- Uses UserService and VideoService for idempotent test-data seeding.
- WebConfig and DBConfig centralise all env var access.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs, credentials, or sleeps.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error

import psycopg2
import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.core.config.db_config import DBConfig
from testing.components.pages.dashboard_page.dashboard_page import DashboardPage
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.services.user_service import UserService
from testing.components.services.video_service import VideoService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000    # ms
_NAVIGATION_TIMEOUT = 20_000   # ms — max time to wait for post-login redirect
_TABLE_TIMEOUT = 30_000        # ms — max time to wait for the video table

# Fallback Firebase UID — used only when FIREBASE_API_KEY is unavailable.
_TEST_FIREBASE_UID_FALLBACK = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")
_TEST_USERNAME = "ci_test_mytube192"

# Unique video titles for this test so rows can be identified across runs.
_VIDEO_TITLE_READY = "MYTUBE-192 Ready Video"
_VIDEO_TITLE_PROCESSING = "MYTUBE-192 Processing Video"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_url_reachable(url: str, timeout: int = 10) -> bool:
    """Return True if *url* returns an HTTP 2xx/3xx response."""
    try:
        req = urllib.request.Request(url, method="GET")
        res = urllib.request.urlopen(req, timeout=timeout)
        return res.status < 400
    except Exception:
        return False


def _postgres_available(db_config: DBConfig) -> bool:
    """Return True if PostgreSQL is reachable using *db_config*."""
    try:
        conn = psycopg2.connect(db_config.dsn())
        conn.close()
        return True
    except psycopg2.OperationalError:
        return False


def _resolve_firebase_uid(email: str, password: str, api_key: str) -> str:
    """Sign in via Firebase REST API and return the real UID (localId).

    Calls ``accounts:signInWithPassword`` with the given credentials and
    returns ``localId`` from the response — the canonical Firebase UID that
    the backend extracts from the ID token when the browser makes API calls.
    This guarantees that the UID used for DB seeding matches the UID the
    frontend sends, eliminating the FIREBASE_TEST_UID mismatch.
    """
    payload = json.dumps(
        {"email": email, "password": password, "returnSecureToken": True}
    ).encode()
    req = urllib.request.Request(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    return data["localId"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module", autouse=True)
def require_credentials(web_config: WebConfig):
    """Skip the entire module when Firebase test credentials are not provided."""
    if not web_config.test_email:
        pytest.skip(
            "FIREBASE_TEST_EMAIL not set — skipping dashboard video list test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping dashboard video list test. "
            "Set FIREBASE_TEST_PASSWORD to run."
        )


@pytest.fixture(scope="module", autouse=True)
def require_reachable_app(web_config: WebConfig):
    """Skip the entire module when the deployed frontend is not reachable."""
    home_url = web_config.base_url.rstrip("/") + "/"
    if not _is_url_reachable(home_url):
        pytest.skip(
            f"Deployed frontend at {web_config.base_url} is not reachable — "
            "skipping dashboard tests. "
            "Set APP_URL to a live instance to run."
        )


@pytest.fixture(scope="module", autouse=True)
def require_postgres(db_config: DBConfig):
    """Skip the entire module when PostgreSQL is not reachable."""
    if not _postgres_available(db_config):
        pytest.skip(
            "PostgreSQL is not reachable — skipping dashboard video list tests. "
            "Set DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME to run."
        )


@pytest.fixture(scope="module")
def db_conn(db_config: DBConfig):
    """Open a psycopg2 connection to the test database (autocommit)."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_videos(db_conn, web_config: WebConfig) -> dict:
    """Seed a test user and two videos; return their IDs and titles.

    Resolves the **real** Firebase UID for the test user by calling the
    Firebase REST sign-in API (``accounts:signInWithPassword``) when
    ``FIREBASE_API_KEY`` is available.  This guarantees that the UID used
    for DB seeding matches the UID embedded in the Firebase ID token that
    the browser sends to the API — eliminating the mismatch that previously
    caused ``GET /api/me/videos`` to return zero results.

    Falls back to the ``FIREBASE_TEST_UID`` environment variable when
    ``FIREBASE_API_KEY`` is not set (e.g. local runs without full CI env).

    Seeds:
    - One video with status "ready" (title: MYTUBE-192 Ready Video)
    - One video with status "processing" (title: MYTUBE-192 Processing Video)

    Returns a dict with keys:
      - ``ready_video_id``, ``processing_video_id``
      - ``ready_title``, ``processing_title``
    """
    user_svc = UserService(db_conn)
    video_svc = VideoService(db_conn)

    # Resolve the real Firebase UID so DB seeding matches the token UID.
    api_key = os.getenv("FIREBASE_API_KEY", "")
    if api_key and web_config.test_email and web_config.test_password:
        try:
            firebase_uid = _resolve_firebase_uid(
                web_config.test_email, web_config.test_password, api_key
            )
        except Exception:
            firebase_uid = _TEST_FIREBASE_UID_FALLBACK
    else:
        firebase_uid = _TEST_FIREBASE_UID_FALLBACK

    # Find or create the CI test user by their Firebase UID.
    existing = user_svc.find_by_firebase_uid(firebase_uid)
    if existing is not None:
        user_id = existing["id"]
    else:
        user_id = user_svc.create_user(firebase_uid, _TEST_USERNAME)

    # Insert fresh videos with status-specific titles unique to MYTUBE-192.
    ready_row = video_svc.insert_video(
        uploader_id=user_id,
        title=_VIDEO_TITLE_READY,
        status="ready",
    )
    ready_id = str(ready_row[0])

    processing_row = video_svc.insert_video(
        uploader_id=user_id,
        title=_VIDEO_TITLE_PROCESSING,
        status="processing",
    )
    processing_id = str(processing_row[0])

    return {
        "ready_video_id": ready_id,
        "processing_video_id": processing_id,
        "ready_title": _VIDEO_TITLE_READY,
        "processing_title": _VIDEO_TITLE_PROCESSING,
    }


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    """Launch a Chromium browser instance for the test module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def authenticated_page(browser: Browser, web_config: WebConfig, seeded_videos) -> Page:
    """Open a browser context, log in once, and yield the authenticated page.

    ``seeded_videos`` is listed as a dependency to guarantee that DB rows exist
    before the browser attempts to load the dashboard.

    The login is performed exactly once for the module; all tests share the
    authenticated session.
    """
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    login = LoginPage(pg)
    login.navigate(web_config.login_url())
    login.login_as(web_config.test_email, web_config.test_password)
    login.wait_for_navigation_to(web_config.home_url(), timeout=_NAVIGATION_TIMEOUT)

    yield pg
    context.close()


@pytest.fixture(scope="module")
def loaded_dashboard(
    authenticated_page: Page,
    web_config: WebConfig,
    seeded_videos: dict,
) -> DashboardPage:
    """Navigate to /dashboard and wait for the video table to render.

    All tests in this module reuse this loaded page state — navigation and
    the initial API fetch happen exactly once.
    """
    dashboard = DashboardPage(authenticated_page)
    dashboard_url = web_config.base_url.rstrip("/") + "/dashboard/"
    dashboard.navigate(dashboard_url)
    dashboard.wait_for_videos_table(timeout=_TABLE_TIMEOUT)
    return dashboard


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDashboardVideoList:
    """MYTUBE-192: Dashboard grid displays correct metadata and status badges."""

    def test_video_table_is_visible(self, loaded_dashboard: DashboardPage):
        """The dashboard must render a <table> element containing video rows."""
        assert loaded_dashboard.is_table_visible(), (
            "Expected a video table to be visible on the /dashboard page, "
            "but the <table> element was not found. "
            "The dashboard may not have loaded or the user has no videos."
        )

    def test_ready_video_title_is_displayed(
        self, loaded_dashboard: DashboardPage, seeded_videos: dict
    ):
        """The seeded 'ready' video title must appear in the dashboard table."""
        titles = loaded_dashboard.get_all_titles()
        assert any(seeded_videos["ready_title"] in t for t in titles), (
            f"Expected to find title '{seeded_videos['ready_title']}' in the "
            f"dashboard table, but only found: {titles}"
        )

    def test_ready_video_status_badge_shows_ready(
        self, loaded_dashboard: DashboardPage, seeded_videos: dict
    ):
        """The status badge for the 'ready' video must display the text 'ready'."""
        badge_text = loaded_dashboard.get_status_badge_for_title(
            seeded_videos["ready_title"]
        )
        assert badge_text is not None, (
            f"Expected a status badge <span> in the row for "
            f"'{seeded_videos['ready_title']}', but none was found."
        )
        assert badge_text == "ready", (
            f"Expected status badge to show 'ready', but got '{badge_text}'."
        )

    def test_processing_video_status_badge_shows_processing(
        self, loaded_dashboard: DashboardPage, seeded_videos: dict
    ):
        """The status badge for the 'processing' video must display 'processing'."""
        badge_text = loaded_dashboard.get_status_badge_for_title(
            seeded_videos["processing_title"]
        )
        assert badge_text is not None, (
            f"Expected a status badge <span> in the row for "
            f"'{seeded_videos['processing_title']}', but none was found."
        )
        assert badge_text == "processing", (
            f"Expected status badge to show 'processing', but got '{badge_text}'."
        )

    def test_ready_video_has_thumbnail_element(
        self, loaded_dashboard: DashboardPage, seeded_videos: dict
    ):
        """The thumbnail cell for the 'ready' video must contain an <img> or placeholder."""
        has_thumb = loaded_dashboard.has_thumbnail_element_for_title(
            seeded_videos["ready_title"]
        )
        assert has_thumb, (
            f"Expected the thumbnail cell for '{seeded_videos['ready_title']}' "
            "to contain an <img> element or a placeholder <div>, but neither was found."
        )

    def test_ready_video_view_count_is_visible(
        self, loaded_dashboard: DashboardPage, seeded_videos: dict
    ):
        """The view count cell for the 'ready' video must be visible and non-empty."""
        view_count = loaded_dashboard.get_view_count_for_title(
            seeded_videos["ready_title"]
        )
        assert view_count is not None, (
            f"Expected a view count cell in the row for "
            f"'{seeded_videos['ready_title']}', but none was found."
        )
        assert view_count != "", (
            f"Expected a non-empty view count for '{seeded_videos['ready_title']}', "
            "but the cell was empty."
        )

    def test_ready_video_creation_date_is_visible(
        self, loaded_dashboard: DashboardPage, seeded_videos: dict
    ):
        """The creation date cell for the 'ready' video must be visible and formatted."""
        creation_date = loaded_dashboard.get_creation_date_for_title(
            seeded_videos["ready_title"]
        )
        assert creation_date is not None, (
            f"Expected a creation date cell in the row for "
            f"'{seeded_videos['ready_title']}', but none was found."
        )
        assert creation_date != "", (
            f"Expected a non-empty creation date for '{seeded_videos['ready_title']}', "
            "but the cell was empty."
        )
        # A formatted date (e.g., "3/3/2026") must contain at least one digit.
        assert any(c.isdigit() for c in creation_date), (
            f"Expected the creation date to contain at least one digit "
            f"(e.g., '3/3/2026'), but got '{creation_date}'."
        )
