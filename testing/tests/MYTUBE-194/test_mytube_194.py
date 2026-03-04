"""
MYTUBE-194: Confirm video deletion via dashboard UI — video removed from listing.

Verifies the full video deletion workflow on the /dashboard page:
  1. The Delete button is visible for the test video.
  2. Clicking Delete shows an inline confirmation prompt (Confirm + Cancel buttons).
  3. During confirmation the original Delete button is hidden.
  4. Clicking Cancel dismisses the confirmation and restores the Delete button.
  5. Clicking Delete → Confirm removes the video row from the dashboard table.

Type: Web UI (Playwright, Chromium)

Preconditions
-------------
- FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD are set (CI test user credentials).
- The database is reachable (DB_HOST / DB_USER / DB_PASSWORD / DB_NAME).
- The CI test user (firebase_uid = FIREBASE_TEST_UID) exists in the DB, or can be
  created during test setup.

Skip conditions
---------------
- FIREBASE_TEST_EMAIL or FIREBASE_TEST_PASSWORD not set.
- Database not reachable (DB connectivity required to seed the test video).
- CI test user not found in DB and cannot be created.

Architecture
------------
- LoginPage    — testing/components/pages/login_page/
- DashboardPage — testing/components/pages/dashboard_page/
- WebConfig    — testing/core/config/web_config.py
- DBConfig     — testing/core/config/db_config.py
- Direct psycopg2 for idempotent test-data seeding.
- Playwright sync API with module-scoped fixtures.
"""
from __future__ import annotations

import os
import sys

import psycopg2
import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.core.config.db_config import DBConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.dashboard_page.dashboard_page import DashboardPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TEST_FIREBASE_UID: str = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")
_TEST_VIDEO_TITLE: str = "MYTUBE-194 Deletion Test Video"

_NAVIGATION_TIMEOUT: int = 30_000   # ms — max time for post-login redirect
_PAGE_LOAD_TIMEOUT: int = 30_000    # ms — max time for initial page load
_CONFIRM_TIMEOUT: int = 5_000       # ms — max time to wait for Confirm button
_DISAPPEAR_TIMEOUT: int = 10_000    # ms — max time for video row to vanish


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _db_is_reachable(cfg: DBConfig) -> bool:
    """Return True if a psycopg2 connection can be established."""
    try:
        conn = psycopg2.connect(cfg.dsn(), connect_timeout=3)
        conn.close()
        return True
    except Exception:
        return False


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
def require_credentials(web_config: WebConfig) -> None:
    """Skip the entire module when Firebase test credentials are absent."""
    if not web_config.test_email:
        pytest.skip(
            "FIREBASE_TEST_EMAIL not set — cannot authenticate as the CI test user. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run this test."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — cannot authenticate as the CI test user."
        )


@pytest.fixture(scope="module", autouse=True)
def require_db(db_config: DBConfig) -> None:
    """Skip the entire module when the test database is not reachable."""
    if not _db_is_reachable(db_config):
        pytest.skip(
            f"Database not reachable at {db_config.host}:{db_config.port} — "
            "cannot seed the test video. "
            "Set DB_HOST / DB_USER / DB_PASSWORD / DB_NAME and ensure the DB is accessible."
        )


@pytest.fixture(scope="module")
def db_conn(db_config: DBConfig):
    """Open a direct psycopg2 connection with autocommit enabled."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def test_video_data(db_conn, web_config: WebConfig) -> dict:
    """Ensure the CI test user exists in the DB and seed a test video.

    Yields a dict:
        {
            "video_id":    str,
            "video_title": str,
        }

    Performs best-effort cleanup on teardown — removes the video only if it
    was not already deleted by the test itself.
    """
    firebase_uid = _TEST_FIREBASE_UID

    # --- 1. Resolve the CI test user's DB id ---
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (firebase_uid,),
        )
        user_row = cur.fetchone()

    if user_row is None:
        # Try to create the user with a CI-safe username.
        # ON CONFLICT (firebase_uid) DO NOTHING keeps this idempotent.
        try:
            with db_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (firebase_uid, username) "
                    "VALUES (%s, %s) "
                    "ON CONFLICT (firebase_uid) DO NOTHING",
                    (firebase_uid, "ci_test_user_001"),
                )
            with db_conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM users WHERE firebase_uid = %s",
                    (firebase_uid,),
                )
                user_row = cur.fetchone()
        except Exception:
            user_row = None

    if user_row is None:
        pytest.skip(
            f"CI test user (firebase_uid={firebase_uid!r}) not found in DB and "
            "could not be created. "
            "Ensure the CI test user has registered via the app, or that the DB is accessible."
        )

    user_db_id = str(user_row[0])

    # --- 2. Find or create the test video ---
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM videos WHERE uploader_id = %s AND title = %s",
            (user_db_id, _TEST_VIDEO_TITLE),
        )
        video_row = cur.fetchone()

    if video_row is None:
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO videos (uploader_id, title, status) "
                "VALUES (%s, %s, 'ready') RETURNING id",
                (user_db_id, _TEST_VIDEO_TITLE),
            )
            video_row = cur.fetchone()

    if video_row is None:
        pytest.fail(
            f"Failed to find or create the test video (title={_TEST_VIDEO_TITLE!r}) in DB."
        )

    video_id = str(video_row[0])

    yield {"video_id": video_id, "video_title": _TEST_VIDEO_TITLE}

    # --- Teardown: remove the video if the test did not delete it ---
    try:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM videos WHERE id = %s", (video_id,))
    except Exception:
        pass  # best-effort cleanup; not critical if video was already removed


@pytest.fixture(scope="module")
def browser(web_config: WebConfig) -> Browser:
    """Launch a Chromium browser for the test module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def page(browser: Browser) -> Page:
    """Open a fresh browser context and page, shared across the module."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def authenticated_dashboard_page(
    web_config: WebConfig,
    page: Page,
    test_video_data: dict,  # ensures the video is seeded before navigation
) -> Page:
    """Log in as the CI test user and navigate to /dashboard.

    The ``test_video_data`` parameter guarantees the test video is seeded in
    the DB before the browser loads the dashboard so it appears in the listing.

    Returns the authenticated Playwright page already showing the dashboard.
    """
    login_page = LoginPage(page)
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)
    login_page.wait_for_navigation_to(web_config.home_url(), timeout=_NAVIGATION_TIMEOUT)

    dashboard_url = f"{web_config.base_url.rstrip('/')}/dashboard/"
    page.goto(dashboard_url, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)

    return page


@pytest.fixture(scope="module")
def dashboard_page(authenticated_dashboard_page: Page) -> DashboardPage:
    """Return a DashboardPage wrapping the authenticated /dashboard page."""
    return DashboardPage(authenticated_dashboard_page)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVideoDeletionViaUI:
    """MYTUBE-194: Verify the full video-deletion workflow on /dashboard.

    Tests run in definition order and share a single authenticated browser
    session (module-scoped fixtures).

    State progression
    -----------------
    test_1  Dashboard loaded; test video visible.
    test_2  Delete button visible for test video.
    test_3  Click Delete  →  Confirm + Cancel appear (page now in confirmation mode).
    test_4  (confirmation mode)  original Delete button is hidden.
    test_5  Click Cancel  →  Delete button restored; Confirm gone.
    test_6  Click Delete → Confirm  →  video row removed from table.
    """

    def test_dashboard_shows_test_video(
        self, dashboard_page: DashboardPage, test_video_data: dict
    ) -> None:
        """The seeded test video is visible in the dashboard table on load."""
        video_title = test_video_data["video_title"]
        assert dashboard_page.is_video_visible_by_title(video_title, timeout=10_000), (
            f"Expected '{video_title}' to appear in the dashboard table after login, "
            "but it was not found. "
            "The API may not have returned the seeded video, or the user mismatch."
        )

    def test_delete_button_initially_visible(
        self, dashboard_page: DashboardPage, test_video_data: dict
    ) -> None:
        """A Delete button (aria-label='Delete <title>') is visible before any interaction."""
        video_title = test_video_data["video_title"]
        assert dashboard_page.is_delete_button_visible(video_title), (
            f"Expected a Delete button for '{video_title}' to be visible, "
            "but it was not found. "
            "The dashboard may not be rendering action buttons correctly."
        )

    def test_confirmation_prompt_appears_after_delete_click(
        self, dashboard_page: DashboardPage, test_video_data: dict
    ) -> None:
        """Clicking Delete replaces it with an inline Confirm + Cancel prompt.

        NOTE: This test mutates the page state. The page is left in confirmation
        mode. Tests 4 and 5 depend on this state.
        """
        video_title = test_video_data["video_title"]
        dashboard_page.click_delete_button(video_title)

        assert dashboard_page.is_confirm_delete_button_visible(timeout=_CONFIRM_TIMEOUT), (
            "Expected a 'Confirm' button to appear after clicking Delete, "
            "but it was not found within the timeout. "
            "The deletion confirmation prompt may be missing."
        )
        assert dashboard_page.is_cancel_delete_button_visible(timeout=3_000), (
            "Expected a 'Cancel' button to appear alongside 'Confirm', "
            "but it was not visible. "
            "The inline confirmation must show both Confirm and Cancel."
        )

    def test_delete_button_hidden_during_confirmation(
        self, dashboard_page: DashboardPage, test_video_data: dict
    ) -> None:
        """While in confirmation mode the original Delete button must not be visible.

        Pre-condition: test_confirmation_prompt_appears_after_delete_click has run
        and left the page in confirmation mode (Confirm + Cancel visible).
        """
        video_title = test_video_data["video_title"]
        assert not dashboard_page.is_delete_button_visible(video_title, timeout=1_000), (
            f"Expected the Delete button for '{video_title}' to be hidden while "
            "the confirmation prompt (Confirm/Cancel) is displayed, "
            "but it was still visible."
        )

    def test_cancel_restores_delete_button(
        self, dashboard_page: DashboardPage, test_video_data: dict
    ) -> None:
        """Clicking Cancel dismisses the confirmation and restores the Delete button.

        Pre-condition: page is in confirmation mode (Confirm + Cancel visible).
        Post-condition: page returns to initial state with Delete button visible.
        """
        video_title = test_video_data["video_title"]
        dashboard_page.click_cancel_delete()

        assert dashboard_page.is_delete_button_visible(video_title, timeout=_CONFIRM_TIMEOUT), (
            "Expected the Delete button to reappear after clicking Cancel, "
            "but it was not visible. "
            "Cancel may not have properly dismissed the confirmation prompt."
        )
        assert not dashboard_page.is_confirm_delete_button_visible(timeout=1_000), (
            "Expected the Confirm button to disappear after clicking Cancel, "
            "but it was still visible."
        )

    def test_video_removed_from_listing_after_confirm(
        self, dashboard_page: DashboardPage, test_video_data: dict
    ) -> None:
        """After Delete → Confirm the video row disappears from the dashboard table.

        Pre-condition: Delete button is visible (restored by test_cancel_restores_delete_button).
        """
        video_title = test_video_data["video_title"]

        # Initiate deletion
        dashboard_page.click_delete_button(video_title)

        # Wait for confirmation to appear before clicking Confirm
        assert dashboard_page.is_confirm_delete_button_visible(timeout=_CONFIRM_TIMEOUT), (
            "Expected Confirm button to appear after clicking Delete (second time), "
            "but it was not visible."
        )

        # Confirm the deletion
        dashboard_page.click_confirm_delete()

        # Assert the video row is removed
        dashboard_page.wait_for_video_to_disappear(video_title, timeout=_DISAPPEAR_TIMEOUT)

        assert not dashboard_page.is_video_visible_by_title(video_title, timeout=2_000), (
            f"Expected '{video_title}' to be removed from the dashboard after confirming "
            "deletion, but the row is still present. "
            "The DELETE API call may have failed or the UI did not update."
        )
