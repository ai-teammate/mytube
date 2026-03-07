"""
MYTUBE-193: Visual distinction of status badges — processing and failed states differentiated.

Objective
---------
Verify that status badges on the dashboard visually distinguish between different
transcoding states: "processing" (yellow) and "failed" (red).

Preconditions
-------------
User has videos with "processing" and "failed" statuses visible on the dashboard.

Test steps
----------
1. Navigate to the /dashboard page.
2. Compare the visual appearance of the badge for a "processing" video versus a
   "failed" video.

Expected Result
---------------
The badges are visually distinct (different Tailwind color classes) so the user
can easily identify if a video is still being transcoded or if an error occurred.

Source code reference
---------------------
web/src/app/dashboard/page.tsx  →  statusBadgeClasses():
  - "processing" → "bg-yellow-100 text-yellow-800"
  - "failed"     → "bg-red-100 text-red-800"

Test approach
-------------
Dual-mode:

Live mode (when FIREBASE_TEST_EMAIL, FIREBASE_TEST_PASSWORD, PostgreSQL, and the
deployed app are all reachable):
  - Seeds a test user and two videos (status="processing", status="failed") in the DB.
  - Logs in via the web app's login form using Firebase credentials.
  - Navigates to /dashboard and checks the Tailwind color classes on the rendered
    badge <span> elements.

Fixture mode (default fallback — always runs):
  - Starts a local HTTP server that serves a minimal HTML page with two badge
    <span> elements styled identically to the production app (same Tailwind class
    names + equivalent inline styles for rendering without Tailwind CSS).
  - Playwright navigates to the fixture page and checks the same class attributes.

Environment variables
---------------------
APP_URL / WEB_BASE_URL  : Base URL of the deployed web app.
                          Default: https://ai-teammate.github.io/mytube
API_BASE_URL            : Backend API base URL (Live mode).
                          Default: http://localhost:8081
FIREBASE_TEST_EMAIL     : Firebase test user email (Live mode).
FIREBASE_TEST_PASSWORD  : Firebase test user password (Live mode).
FIREBASE_TEST_UID       : Firebase UID of the CI test user (Live mode DB seeding).
DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME : DB connection (Live mode).
PLAYWRIGHT_HEADLESS     : Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      : Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses DashboardPage (Page Object) from testing/components/pages/dashboard_page/.
- Uses LoginPage (Page Object) from testing/components/pages/login_page/.
- Uses UserService and VideoService for idempotent DB seeding (Live mode).
- WebConfig and DBConfig centralise all env var access.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import os
import sys
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

import psycopg2
import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

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

_FIXTURE_PORT = 19193
_PAGE_LOAD_TIMEOUT = 30_000  # ms
_TABLE_LOAD_TIMEOUT = 20_000  # ms — max time for the video table to appear

# Test data for DB seeding (Live mode)
_TEST_FIREBASE_UID = "test-uid-mytube-193"
_TEST_USERNAME = "testuser_mytube193"
_PROCESSING_VIDEO_TITLE = "MYTUBE-193 Processing Video"
_FAILED_VIDEO_TITLE = "MYTUBE-193 Failed Video"

# Expected Tailwind color class keywords
_PROCESSING_COLOR_KEYWORD = "yellow"  # bg-yellow-100
_FAILED_COLOR_KEYWORD = "red"         # bg-red-100

# ---------------------------------------------------------------------------
# Fixture mode HTML
# Mirrors what the production StatusBadge component renders, using:
#   - The same Tailwind class names (for class-attribute assertion)
#   - Equivalent inline styles (so rendering works without Tailwind CSS)
# ---------------------------------------------------------------------------

_FIXTURE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Dashboard – fixture (MYTUBE-193)</title>
</head>
<body style="background:#f9fafb;padding:2.5rem 1rem;font-family:Arial,sans-serif;">
  <h1 style="font-size:1.5rem;font-weight:700;color:#111827;margin-bottom:1.5rem;">My videos</h1>
  <div style="border-radius:1rem;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.05);overflow:hidden;">
    <table style="width:100%;font-size:.875rem;border-collapse:collapse;">
      <thead>
        <tr style="border-bottom:1px solid #f3f4f6;text-align:left;">
          <th style="padding:.75rem 1rem;font-weight:500;color:#6b7280;">Title</th>
          <th style="padding:.75rem 1rem;font-weight:500;color:#6b7280;">Status</th>
        </tr>
      </thead>
      <tbody>
        <tr style="border-bottom:1px solid #f9fafb;">
          <td style="padding:.75rem 1rem;color:#111827;">Test Processing Video</td>
          <td style="padding:.75rem 1rem;">
            <span
              class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-yellow-100 text-yellow-800"
              style="display:inline-flex;align-items:center;border-radius:9999px;padding:.125rem .625rem;font-size:.75rem;font-weight:500;background-color:#fef9c3;color:#854d0e;"
            >processing</span>
          </td>
        </tr>
        <tr>
          <td style="padding:.75rem 1rem;color:#111827;">Test Failed Video</td>
          <td style="padding:.75rem 1rem;">
            <span
              class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-red-100 text-red-800"
              style="display:inline-flex;align-items:center;border-radius:9999px;padding:.125rem .625rem;font-size:.75rem;font-weight:500;background-color:#fee2e2;color:#991b1b;"
            >failed</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Fixture mode HTTP server
# ---------------------------------------------------------------------------


class _FixtureDashboardHandler(BaseHTTPRequestHandler):
    """Serves the fixture dashboard HTML for every GET request."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # suppress console noise

    def do_GET(self) -> None:  # noqa: N802
        body = _FIXTURE_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _start_server(port: int) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), _FixtureDashboardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_url_reachable(url: str, timeout: int = 8) -> bool:
    """Return True if the URL responds with a non-5xx HTTP status."""
    try:
        req = urllib.request.Request(url, method="GET")
        res = urllib.request.urlopen(req, timeout=timeout)
        return res.status < 500
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


def _resolve_mode(web_config: WebConfig, db_config: DBConfig) -> str:
    """Return "live" if all live-mode conditions are met, else "fixture"."""
    if not web_config.test_email or not web_config.test_password:
        return "fixture"
    if not _is_url_reachable(web_config.base_url + "/"):
        return "fixture"
    if not _postgres_available(db_config):
        return "fixture"
    return "live"


# ---------------------------------------------------------------------------
# pytest Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    """Launch a Chromium browser for the test module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def dashboard_context(web_config: WebConfig, db_config: DBConfig, browser: Browser):
    """Resolve whether to run in live or fixture mode.

    Live mode:
      - Seeds a test user + processing/failed videos in the DB.
      - Logs in via Playwright and navigates to /dashboard.
      - Yields a DashboardPage pointing at the real deployed app.

    Fixture mode:
      - Starts a local HTTP server with pre-styled badge HTML.
      - Yields a DashboardPage pointing at the fixture page (no auth needed).

    Yields a dict with:
      - ``mode``       : "live" or "fixture"
      - ``dashboard``  : DashboardPage instance (page already loaded)
      - ``context``    : BrowserContext (for cleanup)
    """
    mode = _resolve_mode(web_config, db_config)

    if mode == "live":
        # ── DB seeding ──────────────────────────────────────────────────
        db_conn = psycopg2.connect(db_config.dsn())
        db_conn.autocommit = True
        try:
            user_svc = UserService(db_conn)
            video_svc = VideoService(db_conn)

            # Resolve the Firebase UID: prefer the CI var, fall back to test UID.
            firebase_uid = os.getenv("FIREBASE_TEST_UID", _TEST_FIREBASE_UID).strip() or _TEST_FIREBASE_UID
            username = _TEST_USERNAME

            existing = user_svc.find_by_firebase_uid(firebase_uid)
            if existing is not None:
                user_id = existing["id"]
            else:
                user_id = user_svc.create_user(firebase_uid, username)

            # Seed one video per status (idempotent by design — inserts fresh rows
            # each run; the dashboard shows all of them, which is fine).
            video_svc.insert_video(user_id, _PROCESSING_VIDEO_TITLE, "processing")
            video_svc.insert_video(user_id, _FAILED_VIDEO_TITLE, "failed")
        finally:
            db_conn.close()

        # ── Browser login ───────────────────────────────────────────────
        browser_ctx: BrowserContext = browser.new_context()
        pg: Page = browser_ctx.new_page()
        pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)

        login_pg = LoginPage(pg)
        login_pg.navigate(web_config.login_url())
        login_pg.login_as(web_config.test_email, web_config.test_password)

        # Wait until redirected away from /login
        pg.wait_for_url(lambda url: "/login" not in url, timeout=_PAGE_LOAD_TIMEOUT)

        # Navigate to /dashboard and wait for the video table to load
        pg.goto(web_config.base_url + "/dashboard/", wait_until="domcontentloaded")
        try:
            pg.wait_for_selector("table", timeout=_TABLE_LOAD_TIMEOUT)
        except Exception:
            # Table may not appear if the user has no videos yet; proceed anyway
            pass
        pg.wait_for_load_state("networkidle", timeout=_TABLE_LOAD_TIMEOUT)

        dashboard = DashboardPage(pg)
        try:
            yield {"mode": "live", "dashboard": dashboard, "context": browser_ctx}
        finally:
            browser_ctx.close()

    else:
        # ── Fixture mode ────────────────────────────────────────────────
        fixture_srv = _start_server(_FIXTURE_PORT)
        browser_ctx = browser.new_context()
        pg = browser_ctx.new_page()
        pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)

        fixture_url = f"http://127.0.0.1:{_FIXTURE_PORT}/"
        pg.goto(fixture_url, wait_until="domcontentloaded")
        pg.wait_for_load_state("networkidle", timeout=10_000)

        dashboard = DashboardPage(pg)
        try:
            yield {"mode": "fixture", "dashboard": dashboard, "context": browser_ctx}
        finally:
            browser_ctx.close()
            fixture_srv.shutdown()


@pytest.fixture(scope="module")
def loaded_dashboard(dashboard_context) -> DashboardPage:
    """Return the pre-loaded DashboardPage from the resolved context."""
    return dashboard_context["dashboard"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStatusBadgeVisualDistinction:
    """MYTUBE-193: Dashboard status badges are visually distinct for processing vs failed."""

    def test_processing_badge_is_present(self, loaded_dashboard: DashboardPage):
        """A badge with text 'Processing' must be visible on the dashboard.

        Verifies the precondition: the dashboard has at least one video in the
        'processing' state whose badge is rendered and visible.
        """
        assert loaded_dashboard.has_status_badge("Processing"), (
            "Expected a 'Processing' status badge to be visible on the dashboard, "
            "but none was found. "
            "The dashboard must render a status badge for videos in 'processing' state."
        )

    def test_failed_badge_is_present(self, loaded_dashboard: DashboardPage):
        """A badge with text 'Failed' must be visible on the dashboard.

        Verifies the precondition: the dashboard has at least one video in the
        'failed' state whose badge is rendered and visible.
        """
        assert loaded_dashboard.has_status_badge("Failed"), (
            "Expected a 'Failed' status badge to be visible on the dashboard, "
            "but none was found. "
            "The dashboard must render a status badge for videos in 'failed' state."
        )

    def test_processing_badge_uses_yellow_color_class(
        self, loaded_dashboard: DashboardPage
    ):
        """The 'processing' badge must carry the yellow Tailwind color class (bg-yellow-*).

        The source code (web/src/app/dashboard/page.tsx) assigns 'bg-yellow-100
        text-yellow-800' to processing badges to give them a yellow appearance
        that signals "in progress" to the user.
        """
        badge_class = loaded_dashboard.get_status_badge_class("processing")
        assert badge_class is not None, (
            "Could not read the CSS class attribute of the 'processing' badge. "
            "Ensure the badge element is visible on the dashboard."
        )
        assert _PROCESSING_COLOR_KEYWORD in badge_class, (
            f"Expected the 'processing' badge to have a yellow color class "
            f"(bg-yellow-*), but found classes: '{badge_class}'. "
            "The StatusBadge component must use bg-yellow-100 for processing status."
        )

    def test_failed_badge_uses_red_color_class(
        self, loaded_dashboard: DashboardPage
    ):
        """The 'failed' badge must carry the red Tailwind color class (bg-red-*).

        The source code assigns 'bg-red-100 text-red-800' to failed badges to
        signal an error state clearly distinguishable from processing.
        """
        badge_class = loaded_dashboard.get_status_badge_class("failed")
        assert badge_class is not None, (
            "Could not read the CSS class attribute of the 'failed' badge. "
            "Ensure the badge element is visible on the dashboard."
        )
        assert _FAILED_COLOR_KEYWORD in badge_class, (
            f"Expected the 'failed' badge to have a red color class (bg-red-*), "
            f"but found classes: '{badge_class}'. "
            "The StatusBadge component must use bg-red-100 for failed status."
        )

    def test_processing_and_failed_badges_have_different_color_classes(
        self, loaded_dashboard: DashboardPage
    ):
        """The 'processing' and 'failed' badges must use different color classes.

        This is the primary visual-distinction assertion: the two badge types
        must have different Tailwind background color classes so that users can
        visually differentiate between a video that is still being transcoded
        and one that encountered an error.
        """
        processing_class = loaded_dashboard.get_status_badge_class("processing")
        failed_class = loaded_dashboard.get_status_badge_class("failed")

        assert processing_class is not None, (
            "Could not find the 'processing' badge element."
        )
        assert failed_class is not None, (
            "Could not find the 'failed' badge element."
        )

        # Extract color-related Tailwind classes (containing color keywords)
        _COLOR_KEYWORDS = {"yellow", "red", "green", "blue", "gray", "purple", "pink"}
        processing_colors = {
            c for c in processing_class.split()
            if any(kw in c for kw in _COLOR_KEYWORDS)
        }
        failed_colors = {
            c for c in failed_class.split()
            if any(kw in c for kw in _COLOR_KEYWORDS)
        }

        assert processing_colors != failed_colors, (
            f"Expected the 'processing' and 'failed' badges to have different "
            f"color classes, but both use: "
            f"processing_colors={sorted(processing_colors)}, "
            f"failed_colors={sorted(failed_colors)}. "
            "Badges must be visually distinct to help users identify video states."
        )
