"""
MYTUBE-150: Verify watch page metadata display — uploader link and tags are correct.

Verifies that the watch page (/v/:id) correctly renders all video metadata
and that the uploader name links to the correct user profile page.

Preconditions
-------------
- A video exists with a known title, description, tags, and uploader username.
- The video has status "ready" (only ready videos are served by the API).
- The web application is deployed and reachable at WEB_BASE_URL.
- The database is reachable at the configured DB_* env vars.

Test steps
----------
1. Seed a test user and a ready video with description and tags directly in
   the database (idempotent — safe to run multiple times).
2. Navigate to /v/<video_id> in a headless Chromium browser.
3. Wait for the metadata section to load.
4. Verify the title matches the database record.
5. Verify the description matches the database record.
6. Verify the tags (chip elements) match the database record.
7. Locate the uploader link and verify it points to /u/<username>.
8. Click the uploader link and assert the browser navigates to /u/<username>.

Environment variables
---------------------
- WEB_BASE_URL / APP_URL : Base URL of the deployed web app.
                           Default: https://ai-teammate.github.io/mytube
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                           Database connection settings (defaults match test DB).
- PLAYWRIGHT_HEADLESS    : Run browser headless (default: true).
- PLAYWRIGHT_SLOW_MO     : Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses WatchPage (Page Object) from testing/components/pages/watch_page/.
- Uses UserProfilePage (Page Object) for verifying the uploader profile redirect.
- Uses UserService and VideoService for idempotent test-data seeding.
- WebConfig and DBConfig centralise all env var access.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs, credentials, or sleeps.
"""
from __future__ import annotations

import os
import sys
import urllib.request
import urllib.error

import psycopg2
import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Route

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.core.config.db_config import DBConfig
from testing.components.pages.watch_page.watch_page import WatchPage
from testing.components.pages.user_profile_page.user_profile_page import (
    UserProfilePage,
)
from testing.components.services.user_service import UserService
from testing.components.services.video_service import VideoService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_METADATA_TIMEOUT = 20_000    # ms — max time for metadata section to appear

_API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8081")

_TEST_FIREBASE_UID = "test-uid-mytube-150"
_TEST_USERNAME = "testuser_mytube150"
_VIDEO_TITLE = "MYTUBE-150 Test Video"
_VIDEO_DESCRIPTION = "This is the test description for MYTUBE-150."
_VIDEO_TAGS = ["automation", "mytube150", "qa"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_url_reachable(url: str, timeout: int = 10) -> bool:
    """Return True if the URL returns a non-4xx/5xx HTTP response."""
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


def _make_api_proxy_handler(api_base_url: str):
    """Return a Playwright route handler that proxies requests to *api_base_url*.

    When the frontend JS runs in the browser it makes XHR/fetch requests to the
    API URL that was baked in at build time.  If the frontend server and API
    server are on different ports the browser CORS policy blocks these requests.
    This handler intercepts the requests inside Playwright (before the CORS
    check) and forwards them to the API server using Python's urllib, then
    fulfills the route with the response — effectively bypassing CORS.
    """

    def handler(route: Route) -> None:
        req = urllib.request.Request(
            route.request.url,
            method=route.request.method,
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                route.fulfill(
                    status=resp.status,
                    headers={"content-type": resp.headers.get("Content-Type", "application/json")},
                    body=resp.read(),
                )
        except Exception:
            route.continue_()

    return handler


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
def require_reachable_app(web_config: WebConfig):
    """Skip the entire module when the deployed frontend is not reachable."""
    home_url = web_config.base_url + "/"
    if not _is_url_reachable(home_url):
        pytest.skip(
            f"Deployed frontend at {web_config.base_url} is not reachable — "
            "skipping watch page metadata tests. "
            "Set APP_URL to a live instance to run."
        )


@pytest.fixture(scope="module", autouse=True)
def require_postgres(db_config: DBConfig):
    """Skip the entire module when PostgreSQL is not reachable."""
    if not _postgres_available(db_config):
        pytest.skip(
            "PostgreSQL is not reachable — skipping watch page metadata tests. "
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
def seeded_video(db_conn) -> dict:
    """Seed a test user, video, and tags; return a dict with ids/values.

    The fixture is idempotent — if the user already exists it reuses it.
    A fresh video is always inserted so the test has a deterministic ID.
    Tags are inserted after the video row.

    Returns
    -------
    dict with keys: video_id, username, title, description, tags
    """
    user_svc = UserService(db_conn)
    video_svc = VideoService(db_conn)

    # Upsert the test user.
    existing = user_svc.find_by_firebase_uid(_TEST_FIREBASE_UID)
    if existing is not None:
        user_id = existing["id"]
    else:
        user_id = user_svc.create_user(_TEST_FIREBASE_UID, _TEST_USERNAME)

    # Insert a fresh video with description set via direct SQL
    # (VideoService.insert_video does not support description/tags, so we
    # use direct SQL for those columns).
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO videos (uploader_id, title, description, status)
            VALUES (%s, %s, %s, 'ready')
            RETURNING id
            """,
            (user_id, _VIDEO_TITLE, _VIDEO_DESCRIPTION),
        )
        video_id = str(cur.fetchone()[0])

    # Insert tags for the video.
    with db_conn.cursor() as cur:
        for tag in _VIDEO_TAGS:
            cur.execute(
                "INSERT INTO video_tags (video_id, tag) VALUES (%s, %s)",
                (video_id, tag),
            )

    return {
        "video_id": video_id,
        "username": _TEST_USERNAME,
        "title": _VIDEO_TITLE,
        "description": _VIDEO_DESCRIPTION,
        "tags": _VIDEO_TAGS,
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
def browser_context(browser: Browser) -> BrowserContext:
    """Open a browser context with an API proxy route to handle CORS.

    The watch page fetches video data from the API URL baked into the build.
    When frontend and API run on different ports, the browser blocks the request
    due to the same-origin policy.  We install a Playwright route handler that
    intercepts requests to the API URL and forwards them via Python's urllib,
    bypassing the browser CORS check entirely.
    """
    context = browser.new_context()
    # Proxy all requests to the API base URL to avoid CORS issues
    context.route(
        f"{_API_BASE_URL}/**",
        _make_api_proxy_handler(_API_BASE_URL),
    )
    yield context
    context.close()


@pytest.fixture(scope="module")
def page(browser_context: BrowserContext) -> Page:
    """Open a fresh page inside the CORS-proxy browser context."""
    pg = browser_context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg


@pytest.fixture(scope="module")
def watch_page(page: Page) -> WatchPage:
    return WatchPage(page)


@pytest.fixture(scope="module")
def loaded_watch_page(
    web_config: WebConfig,
    seeded_video: dict,
    watch_page: WatchPage,
) -> WatchPage:
    """Navigate to the seeded video's watch page once; all tests reuse the state."""
    watch_page.navigate_to_video(web_config.base_url, seeded_video["video_id"])
    watch_page.wait_for_metadata(timeout=_METADATA_TIMEOUT)
    return watch_page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWatchPageMetadata:
    """MYTUBE-150: Watch page renders correct video metadata."""

    def test_title_matches_database_record(
        self, loaded_watch_page: WatchPage, seeded_video: dict
    ):
        """The <h1> title on the watch page must match the video title in the DB."""
        displayed_title = loaded_watch_page.get_title()
        assert displayed_title is not None, (
            "Expected a video title <h1> to be visible on the watch page, "
            "but none was found."
        )
        assert displayed_title.strip() == seeded_video["title"], (
            f"Watch page title '{displayed_title.strip()}' does not match "
            f"database value '{seeded_video['title']}'."
        )

    def test_description_matches_database_record(
        self, loaded_watch_page: WatchPage, seeded_video: dict
    ):
        """The description block must match the video description in the DB."""
        displayed_description = loaded_watch_page.get_description()
        assert displayed_description is not None, (
            "Expected a video description to be visible on the watch page, "
            "but none was found."
        )
        assert displayed_description.strip() == seeded_video["description"], (
            f"Watch page description '{displayed_description.strip()}' does not match "
            f"database value '{seeded_video['description']}'."
        )

    def test_tags_match_database_record(
        self, loaded_watch_page: WatchPage, seeded_video: dict
    ):
        """All tag chips rendered on the watch page must match the DB tags (any order)."""
        displayed_tags = loaded_watch_page.get_tags()
        assert len(displayed_tags) > 0, (
            "Expected tag chip elements to be visible on the watch page, "
            "but none were found."
        )
        assert sorted(displayed_tags) == sorted(seeded_video["tags"]), (
            f"Watch page tags {sorted(displayed_tags)} do not match "
            f"database tags {sorted(seeded_video['tags'])}."
        )

    def test_uploader_link_text_matches_username(
        self, loaded_watch_page: WatchPage, seeded_video: dict
    ):
        """The uploader link text must display the uploader's username."""
        uploader_text = loaded_watch_page.get_uploader_username()
        assert uploader_text is not None, (
            "Expected an uploader link element on the watch page, but none was found."
        )
        assert uploader_text.strip() == seeded_video["username"], (
            f"Uploader link text '{uploader_text.strip()}' does not match "
            f"expected username '{seeded_video['username']}'."
        )

    def test_uploader_link_href_points_to_profile(
        self, loaded_watch_page: WatchPage, seeded_video: dict
    ):
        """The uploader link href must be /u/<username>."""
        href = loaded_watch_page.get_uploader_href()
        assert href is not None, (
            "Expected an uploader link with an href attribute, but none was found."
        )
        expected_href = f"/u/{seeded_video['username']}"
        assert href == expected_href, (
            f"Uploader link href '{href}' does not match expected '{expected_href}'."
        )


class TestWatchPageUploaderRedirect:
    """MYTUBE-150: Clicking the uploader link navigates to the user profile page."""

    @pytest.fixture(scope="class")
    def page_for_redirect(self, browser: Browser) -> Page:
        """Open a separate page (with API proxy) for the redirect test."""
        context = browser.new_context()
        context.route(
            f"{_API_BASE_URL}/**",
            _make_api_proxy_handler(_API_BASE_URL),
        )
        pg = context.new_page()
        pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        yield pg
        context.close()

    @pytest.fixture(scope="class")
    def watch_page_for_redirect(self, page_for_redirect: Page) -> WatchPage:
        return WatchPage(page_for_redirect)

    @pytest.fixture(scope="class")
    def after_uploader_click(
        self,
        web_config: WebConfig,
        seeded_video: dict,
        watch_page_for_redirect: WatchPage,
        page_for_redirect: Page,
    ) -> Page:
        """Navigate to the watch page, click the uploader link, yield the resulting page."""
        watch_page_for_redirect.navigate_to_video(
            web_config.base_url, seeded_video["video_id"]
        )
        watch_page_for_redirect.wait_for_metadata(timeout=_METADATA_TIMEOUT)
        watch_page_for_redirect.click_uploader_link()
        # Wait for navigation to settle.
        page_for_redirect.wait_for_load_state("domcontentloaded")
        return page_for_redirect

    def test_clicking_uploader_navigates_to_user_profile(
        self,
        after_uploader_click: Page,
        seeded_video: dict,
        web_config: WebConfig,
    ):
        """After clicking the uploader link the URL must contain /u/<username>."""
        current_url = after_uploader_click.url
        expected_path = f"/u/{seeded_video['username']}"
        assert expected_path in current_url, (
            f"Expected URL to contain '{expected_path}' after clicking the uploader "
            f"link, but current URL is '{current_url}'."
        )

    def test_user_profile_page_loads_without_error(
        self,
        after_uploader_click: Page,
        seeded_video: dict,
    ):
        """The user profile page must not show the 'User not found.' message."""
        user_profile = UserProfilePage(after_uploader_click)
        # The page should NOT show not-found; the user exists in the DB.
        not_found = user_profile.is_not_found(timeout=5_000)
        assert not not_found, (
            f"Navigating to /u/{seeded_video['username']} showed 'User not found.' "
            "but the user was seeded into the database for this test."
        )
