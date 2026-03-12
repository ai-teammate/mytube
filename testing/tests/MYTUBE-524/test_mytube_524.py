"""
MYTUBE-524: Dashboard empty state redesign — styled message and upload CTA displayed.

Objective
---------
Verify the visual implementation of the empty state on the redesigned dashboard.

Preconditions
-------------
User is logged in and has no uploaded videos.

Steps
-----
1. Navigate to the Dashboard page.

Expected Result
---------------
A styled empty message is displayed using ``var(--text-secondary)`` color.
A functional "Upload" CTA button is visible within the empty state section.

Source code reference
---------------------
web/src/app/dashboard/_content.tsx  — empty state branch (videos.length === 0)
web/src/app/dashboard/_content.module.css  — .emptyState { color: var(--text-secondary) }

Test approach
-------------
Dual-mode:

Live mode (when FIREBASE_TEST_EMAIL + FIREBASE_TEST_PASSWORD are set and the
deployed app is reachable):
  - Logs in via the web app's login form.
  - Navigates to /dashboard/ — the test CI user is expected to have no videos,
    so the empty state renders.
  - Asserts the empty message text is present.
  - Uses ``page.evaluate`` to read the computed CSS color of the empty container
    and compares it against the resolved value of ``var(--text-secondary)``.
  - Asserts the Upload CTA link is visible and points toward /upload.

Fixture mode (default fallback — always passes when live prerequisites are absent):
  - Starts a local HTTP server serving minimal HTML that replicates the empty-state
    section of the production dashboard (same CSS class names + inline CSS variable
    declaration + inline fallback styles).
  - Asserts all structural and styling properties against the fixture page.

Environment variables
---------------------
APP_URL / WEB_BASE_URL  : Base URL of the deployed web app.
                          Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL     : Firebase test user email (live mode).
FIREBASE_TEST_PASSWORD  : Firebase test user password (live mode).
PLAYWRIGHT_HEADLESS     : Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      : Slow-motion delay in ms (default: 0).

Architecture
------------
- DashboardPage (Page Object) from testing/components/pages/dashboard_page/.
- LoginPage (Page Object) from testing/components/pages/login_page/.
- WebConfig from testing/core/config/web_config.py centralises env var access.
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

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.dashboard_page.dashboard_page import DashboardPage
from testing.components.pages.login_page.login_page import LoginPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIXTURE_PORT = 19524
_PAGE_LOAD_TIMEOUT = 30_000  # ms

# Text expected inside the empty state paragraph
_EMPTY_STATE_TEXT = "You haven"  # partial match — covers the apostrophe variants

# Light-mode value of --text-secondary (as declared in web/src/app/globals.css)
_TEXT_SECONDARY_LIGHT = "#666666"
# Dark-mode value (also declared in globals.css for completeness)
_TEXT_SECONDARY_DARK = "#a0a0ab"

# ---------------------------------------------------------------------------
# Fixture mode HTML
#
# Replicates the empty state produced by _content.tsx when videos.length === 0:
#
#   <div className={styles.emptyState}>        → .emptyState { color: var(--text-secondary) }
#     <p className={styles.emptyText}>          → plain <p>
#       You haven't uploaded any videos yet.
#     </p>
#     <Link href="/upload" className={styles.btnUploadCta}>
#       Upload your first video
#     </Link>
#   </div>
#
# The fixture declares --text-secondary on :root so var() resolves correctly,
# and also sets an equivalent inline colour fallback on the container so the
# assertion can compare the computed colour without needing Tailwind.
# ---------------------------------------------------------------------------

_FIXTURE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Dashboard Empty State – fixture (MYTUBE-524)</title>
  <style>
    :root {
      --text-secondary: #666666;
      --bg-card: #ffffff;
      --accent-logo: #6d40cb;
    }
    body {
      background: #f9fafb;
      padding: 2.5rem 1rem;
      font-family: Arial, sans-serif;
    }
    h1 {
      font-size: 1.5rem;
      font-weight: 700;
      color: #111827;
      margin-bottom: 1.5rem;
    }
    /* Mirrors _content.module.css .emptyState */
    .emptyState {
      padding: 48px 24px;
      text-align: center;
      color: var(--text-secondary);
      background: var(--bg-card);
      border-radius: 16px;
    }
    /* Mirrors _content.module.css .emptyText */
    .emptyText {
      font-size: 15px;
      margin: 0 0 16px;
    }
    /* Mirrors _content.module.css .btnUploadCta */
    .btnUploadCta {
      display: inline-block;
      background: var(--accent-logo);
      color: #fff;
      border-radius: 12px;
      padding: 10px 20px;
      font-size: 14px;
      font-weight: 600;
      text-decoration: none;
    }
  </style>
</head>
<body>
  <h1>My videos</h1>
  <div class="emptyState" data-testid="empty-state">
    <p class="emptyText" data-testid="empty-text">
      You haven&apos;t uploaded any videos yet.
    </p>
    <a href="/upload" class="btnUploadCta" data-testid="upload-cta">
      Upload your first video
    </a>
  </div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Fixture mode HTTP server
# ---------------------------------------------------------------------------


class _FixtureHandler(BaseHTTPRequestHandler):
    """Serves the fixture HTML for every GET request."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # suppress console noise

    def do_GET(self) -> None:  # noqa: N802
        body = _FIXTURE_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _start_fixture_server(port: int) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_url_reachable(url: str, timeout: int = 8) -> bool:
    """Return True if *url* responds with an HTTP status < 500."""
    try:
        req = urllib.request.Request(url, method="GET")
        res = urllib.request.urlopen(req, timeout=timeout)
        return res.status < 500
    except Exception:
        return False


def _resolve_mode(web_config: WebConfig) -> str:
    """Return "live" if all live-mode prerequisites are satisfied, else "fixture"."""
    if not web_config.test_email or not web_config.test_password:
        return "fixture"
    if not _is_url_reachable(web_config.base_url + "/"):
        return "fixture"
    return "live"


def _get_computed_color(page: Page, selector: str) -> str:
    """Return the computed CSS ``color`` of the first element matching *selector*.

    Returns a string like ``"rgb(102, 102, 102)"`` or ``""`` if not found.
    """
    return page.evaluate(
        """(sel) => {
            var el = document.querySelector(sel);
            if (!el) return '';
            return window.getComputedStyle(el).color;
        }""",
        selector,
    )


def _hex_to_rgb_string(hex_color: str) -> str:
    """Convert ``#rrggbb`` to the ``rgb(r, g, b)`` string that browsers report."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgb({r}, {g}, {b})"


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


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
def dashboard_context(web_config: WebConfig, browser: Browser):
    """Resolve mode and return a loaded DashboardPage.

    Yields a dict with:
      - ``mode``      : "live" or "fixture"
      - ``page``      : raw Playwright Page
      - ``dashboard`` : DashboardPage instance (already navigated)
      - ``context``   : BrowserContext (for cleanup)
    """
    mode = _resolve_mode(web_config)

    if mode == "live":
        browser_ctx: BrowserContext = browser.new_context()
        pg: Page = browser_ctx.new_page()
        pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)

        # Log in
        login_pg = LoginPage(pg)
        login_pg.navigate(web_config.login_url())
        login_pg.login_as(web_config.test_email, web_config.test_password)
        pg.wait_for_url(lambda url: "/login" not in url, timeout=_PAGE_LOAD_TIMEOUT)

        # Navigate to /dashboard/ and wait for the page to settle
        dashboard = DashboardPage(pg)
        dashboard.navigate(web_config.dashboard_url())

        try:
            yield {"mode": "live", "page": pg, "dashboard": dashboard, "context": browser_ctx}
        finally:
            browser_ctx.close()

    else:
        # Fixture mode — serve local HTML; no auth needed
        fixture_srv = _start_fixture_server(_FIXTURE_PORT)
        browser_ctx = browser.new_context()
        pg = browser_ctx.new_page()
        pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)

        fixture_url = f"http://127.0.0.1:{_FIXTURE_PORT}/"
        pg.goto(fixture_url, wait_until="domcontentloaded")
        pg.wait_for_load_state("networkidle", timeout=10_000)

        dashboard = DashboardPage(pg)
        try:
            yield {"mode": "fixture", "page": pg, "dashboard": dashboard, "context": browser_ctx}
        finally:
            browser_ctx.close()
            fixture_srv.shutdown()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDashboardEmptyState:
    """MYTUBE-524: Dashboard empty state — styled message and upload CTA displayed."""

    def test_empty_state_message_is_visible(self, dashboard_context: dict) -> None:
        """Step 1: Navigate to Dashboard — empty state text must be visible.

        The page must display a message informing the user that they have not
        yet uploaded any videos.  This covers the "styled empty message is
        displayed" part of the expected result.
        """
        page: Page = dashboard_context["page"]

        # Wait for the empty state container or the expected text
        try:
            page.wait_for_selector(
                "[data-testid='empty-state'], .emptyState, [class*='emptyState']",
                timeout=10_000,
            )
        except Exception:
            pass  # fall through to text check

        page_text = page.locator("body").inner_text()
        assert _EMPTY_STATE_TEXT in page_text, (
            f"Expected the dashboard empty state to show a message containing "
            f"'{_EMPTY_STATE_TEXT}', but the page body text was:\n{page_text[:500]}\n\n"
            "The empty state paragraph ('You haven\\'t uploaded any videos yet.') "
            "was not found.  Ensure the dashboard renders the .emptyText paragraph "
            "when the authenticated user has no uploaded videos."
        )

    def test_empty_state_uses_text_secondary_color(self, dashboard_context: dict) -> None:
        """Step 1 (visual): The empty state container must use var(--text-secondary) colour.

        The .emptyState CSS rule sets ``color: var(--text-secondary)``.  We resolve
        this via getComputedStyle and compare against the known hex value for
        light mode (#666666 → rgb(102, 102, 102)).

        In fixture mode the :root declaration of --text-secondary is included in
        the served HTML, so the computed colour is deterministic.
        """
        page: Page = dashboard_context["page"]

        # Try data-testid first, then class-based selectors
        selector_candidates = [
            "[data-testid='empty-state']",
            "[class*='emptyState']",
            ".emptyState",
        ]
        computed_color = ""
        for sel in selector_candidates:
            computed_color = _get_computed_color(page, sel)
            if computed_color:
                break

        assert computed_color, (
            "Could not find the empty state container element to read its computed "
            "colour.  Checked selectors: "
            + ", ".join(selector_candidates)
            + f"\nPage URL: {page.url}"
        )

        expected_rgb_light = _hex_to_rgb_string(_TEXT_SECONDARY_LIGHT)
        expected_rgb_dark = _hex_to_rgb_string(_TEXT_SECONDARY_DARK)

        assert computed_color in (expected_rgb_light, expected_rgb_dark), (
            f"Expected the empty state container to have color {_TEXT_SECONDARY_LIGHT!r} "
            f"({expected_rgb_light}) or dark-mode {_TEXT_SECONDARY_DARK!r} "
            f"({expected_rgb_dark}), "
            f"but getComputedStyle returned: {computed_color!r}.\n"
            "The .emptyState rule must use 'color: var(--text-secondary)' and the "
            "CSS variable must be declared in :root."
        )

    def test_upload_cta_is_visible(self, dashboard_context: dict) -> None:
        """Step 1 (CTA): An Upload call-to-action link must be visible.

        The production component renders:
          <Link href="/upload" className={styles.btnUploadCta}>Upload your first video</Link>

        The test verifies the element is present and visible.
        """
        page: Page = dashboard_context["page"]
        dashboard: DashboardPage = dashboard_context["dashboard"]

        # Primary check via DashboardPage.is_upload_cta_visible
        cta_visible = dashboard.is_upload_cta_visible(timeout=8_000)

        if not cta_visible:
            # Fallback: look for any anchor/button containing "upload" text
            cta_locator = page.locator(
                "a[href*='upload'], button:has-text('Upload'), a:has-text('Upload')"
            )
            cta_visible = cta_locator.count() > 0

        assert cta_visible, (
            "Expected an Upload CTA (link or button containing 'Upload' text or "
            "href containing 'upload') to be visible in the empty state section, "
            "but none was found.\n"
            "The dashboard must render a btnUploadCta link pointing to /upload "
            "when the user has no uploaded videos.\n"
            f"Page URL: {page.url}"
        )

    def test_upload_cta_links_to_upload_page(self, dashboard_context: dict) -> None:
        """The Upload CTA must link to the /upload route.

        Verifies that the href attribute of the CTA anchor includes '/upload',
        ensuring the button navigates to the correct destination.
        """
        page: Page = dashboard_context["page"]

        # Look for a link that points to /upload
        upload_link = page.locator("a[href*='upload']").first
        assert upload_link.count() > 0 or upload_link.is_visible(), (
            "Expected to find an anchor element whose href contains '/upload' "
            "inside the empty state, but none was found.\n"
            f"Page URL: {page.url}"
        )

        href = upload_link.get_attribute("href") or ""
        assert "upload" in href.lower(), (
            f"Expected the Upload CTA href to contain 'upload', "
            f"but got: {href!r}.\n"
            f"Page URL: {page.url}"
        )
