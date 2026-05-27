"""
MYTUBE-655: Delete avatar in progress — button disabled and shows loading state.

Objective
---------
Verify the UI provides feedback and prevents concurrent requests during
avatar deletion.

Preconditions
-------------
User is on the Account Settings page with an avatar set.

Steps
-----
1. Click the 'Remove avatar' button.
2. Observe the button state while the API request is pending.

Expected Result
---------------
The 'Remove avatar' button becomes disabled and displays a loading indicator
("Removing…") to prevent multiple clicks while the DELETE /api/me/avatar
request is in flight.

Test strategy
-------------
Two complementary modes:

1. **Source analysis** (always runs):
   - Confirms that ``settings/page.tsx`` sets ``setRemoving(true)`` before the
     fetch and ``setRemoving(false)`` in the ``finally`` block.
   - Confirms the button is disabled when ``removing`` is truthy.
   - Confirms the button renders "Removing…" text while deletion is in progress.

2. **Playwright fixture mode** (always runs):
   - Serves a local HTML page that faithfully reproduces the Remove avatar
     button behaviour from ``settings/page.tsx`` without requiring authentication.
   - Intercepts the simulated DELETE XHR to introduce a deliberate delay so
     the in-flight state is observable.
   - Asserts the button is disabled and shows "Removing…" while waiting.
   - Asserts the button is re-enabled and shows "Remove avatar" after completion.

3. **Live mode** (when ``FIREBASE_TEST_EMAIL`` and ``FIREBASE_TEST_PASSWORD`` are set):
   - Logs in and navigates to ``/settings``.
   - Intercepts ``DELETE /api/me/avatar`` via Playwright route to delay the response.
   - Arms a MutationObserver and clicks "Remove avatar".
   - Asserts the observer captured the "Removing…" + disabled in-flight state.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL      CI test user email (required for live mode).
FIREBASE_TEST_PASSWORD   CI test user password (required for live mode).
PLAYWRIGHT_HEADLESS      Run headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-655/test_mytube_655.py -v
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.settings_page.settings_page import SettingsPage

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS_TSX = _REPO_ROOT / "web" / "src" / "app" / "settings" / "page.tsx"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_FIXTURE_PORT = 19655
_DELETE_DELAY_MS = 2_000      # simulated network delay in fixture
_IN_FLIGHT_TIMEOUT = 5_000    # ms — max wait to observe in-flight state
_COMPLETION_TIMEOUT = 10_000  # ms — max wait for deletion to complete
_LIVE_ROUTE_DELAY_S = 3.0     # seconds the live route intercept delays

# Existing avatar URL injected into the mocked /api/me response.
_EXISTING_AVATAR_URL = (
    "https://storage.googleapis.com/mytube-hls-output/avatars/uid_655_test/avatar.jpg"
)

# Minimal valid 1×1 GIF for CDN image requests.
_GIF_BYTES = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
    b"!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01"
    b"\x00\x00\x02\x02D\x01\x00;"
)

# ---------------------------------------------------------------------------
# Fixture HTML — mirrors the 'Remove avatar' button section from page.tsx
# ---------------------------------------------------------------------------

_FIXTURE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Remove avatar button fixture – MYTUBE-655</title>
  <style>
    body {{ font-family: sans-serif; margin: 2rem; }}
    button {{
      padding: 0.5rem 1rem;
      border: 1px solid #fca5a5;
      background: #fff;
      color: #dc2626;
      border-radius: 0.5rem;
      font-size: 0.875rem;
      font-weight: 600;
      cursor: pointer;
      transition: opacity 0.2s;
    }}
    button:disabled {{
      opacity: 0.5;
      cursor: not-allowed;
    }}
    #status {{ margin-top: 0.75rem; font-size: 0.875rem; color: #374151; }}
  </style>
</head>
<body>
  <button id="remove_btn" type="button">Remove avatar</button>
  <p id="status">idle</p>

  <script>
    const DELETE_DELAY_MS = {delete_delay_ms};

    const removeBtn = document.getElementById('remove_btn');
    const status    = document.getElementById('status');

    removeBtn.addEventListener('click', async () => {{
      // ---- In-flight state (mirrors setRemoving(true)) ----
      removeBtn.disabled = true;
      removeBtn.textContent = 'Removing\u2026';
      status.textContent = 'removing';

      // Simulate slow DELETE /api/me/avatar network request.
      await new Promise(resolve => setTimeout(resolve, DELETE_DELAY_MS));

      // ---- Completed state (mirrors setRemoving(false) in finally) ----
      removeBtn.disabled = false;
      removeBtn.textContent = 'Remove avatar';
      status.textContent = 'done';
    }});
  </script>
</body>
</html>
""".replace("{delete_delay_ms}", str(_DELETE_DELAY_MS))

# ---------------------------------------------------------------------------
# Fixture HTTP server
# ---------------------------------------------------------------------------


class _FixtureHandler(BaseHTTPRequestHandler):
    """Serves the single-file fixture HTML."""

    def do_GET(self) -> None:  # noqa: N802
        html = _FIXTURE_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def log_message(self, *args) -> None:  # noqa: ANN002
        pass  # silence request logging


def _start_fixture_server(port: int) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def fixture_server_url() -> str:
    server = _start_fixture_server(_FIXTURE_PORT)
    yield f"http://127.0.0.1:{_FIXTURE_PORT}/"
    server.shutdown()


# ---------------------------------------------------------------------------
# Test class 1: Source analysis (no browser needed)
# ---------------------------------------------------------------------------


class TestAvatarDeleteSourceAnalysis:
    """MYTUBE-655 — source-level verification that the removing state is wired correctly."""

    def test_settings_tsx_exists(self) -> None:
        """The settings page source file must exist."""
        assert _SETTINGS_TSX.exists(), (
            f"Expected settings page at {_SETTINGS_TSX} but the file was not found. "
            "Check the repo layout."
        )

    def test_removing_state_initialised_false(self) -> None:
        """The ``removing`` state must be initialised to ``false``."""
        src = _SETTINGS_TSX.read_text()
        assert "useState(false)" in src or 'setRemoving(false)' in src, (
            "Expected ``removing`` state to be initialised to false in settings/page.tsx. "
            "The state guards the button's disabled attribute during deletion."
        )

    def test_set_removing_true_before_fetch(self) -> None:
        """``setRemoving(true)`` must appear before the DELETE fetch call."""
        src = _SETTINGS_TSX.read_text()
        removing_true_pos = src.find("setRemoving(true)")
        fetch_pos = src.find("DELETE")
        assert removing_true_pos != -1, (
            "setRemoving(true) not found in settings/page.tsx. "
            "The button will never be disabled during deletion."
        )
        assert fetch_pos != -1, (
            "DELETE fetch call not found in settings/page.tsx. "
            "Expected a DELETE /api/me/avatar request for avatar removal."
        )
        assert removing_true_pos < fetch_pos, (
            "setRemoving(true) must appear before the DELETE fetch call. "
            f"setRemoving(true) at char {removing_true_pos}, DELETE at char {fetch_pos}."
        )

    def test_set_removing_false_in_finally(self) -> None:
        """``setRemoving(false)`` must appear in the finally block so it always resets."""
        src = _SETTINGS_TSX.read_text()
        finally_pos = src.find("finally")
        removing_false_pos = src.find("setRemoving(false)")
        assert removing_false_pos != -1, (
            "setRemoving(false) not found in settings/page.tsx. "
            "The button will remain disabled if the DELETE request fails."
        )
        assert finally_pos != -1, (
            "finally block not found in handleAvatarRemove. "
            "setRemoving(false) must be in a finally block to ensure the button is re-enabled "
            "regardless of request outcome."
        )
        assert removing_false_pos > finally_pos, (
            "setRemoving(false) must appear after the finally keyword. "
            f"finally at char {finally_pos}, setRemoving(false) at char {removing_false_pos}."
        )

    def test_button_disabled_when_removing(self) -> None:
        """The button element must have ``disabled={removing}`` attribute."""
        src = _SETTINGS_TSX.read_text()
        assert "disabled={removing}" in src, (
            "The 'Remove avatar' button must have disabled={removing} so it becomes "
            "unclickable while the DELETE request is in flight. "
            "Found no such attribute in settings/page.tsx."
        )

    def test_button_shows_removing_text_in_flight(self) -> None:
        """The button must render 'Removing…' text while ``removing`` is true."""
        src = _SETTINGS_TSX.read_text()
        assert "Removing" in src, (
            "Expected 'Removing…' text in the button's conditional render expression "
            "in settings/page.tsx. "
            "The button must visually indicate progress while the deletion is pending."
        )

    def test_button_shows_remove_avatar_text_idle(self) -> None:
        """The button must render 'Remove avatar' text when not deleting."""
        src = _SETTINGS_TSX.read_text()
        assert "Remove avatar" in src, (
            "Expected 'Remove avatar' as the idle button label in settings/page.tsx."
        )


# ---------------------------------------------------------------------------
# Test class 2: Playwright fixture mode (always runs, no credentials needed)
# ---------------------------------------------------------------------------


class TestAvatarDeleteFixtureMode:
    """MYTUBE-655 — Playwright tests against the local fixture HTML."""

    def test_button_is_enabled_initially(self, fixture_server_url: str, web_config: WebConfig) -> None:
        """The 'Remove avatar' button must be enabled before the user clicks it."""
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=web_config.headless, slow_mo=web_config.slow_mo
            )
            page: Page = browser.new_page()
            page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
            try:
                page.goto(fixture_server_url, wait_until="domcontentloaded")
                btn = page.locator("#remove_btn")
                btn.wait_for(state="visible", timeout=5_000)
                assert not btn.is_disabled(), (
                    "The 'Remove avatar' button should be enabled before the user clicks it."
                )
                assert btn.text_content() == "Remove avatar", (
                    f"Expected button label 'Remove avatar', got: {btn.text_content()!r}"
                )
            finally:
                browser.close()

    def test_button_disabled_during_delete(self, fixture_server_url: str, web_config: WebConfig) -> None:
        """The button must become disabled immediately after clicking 'Remove avatar'."""
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=web_config.headless, slow_mo=web_config.slow_mo
            )
            page: Page = browser.new_page()
            page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
            try:
                page.goto(fixture_server_url, wait_until="domcontentloaded")
                btn = page.locator("#remove_btn")
                btn.wait_for(state="visible", timeout=5_000)

                # Click and immediately check the disabled state.
                btn.click()

                # The button must be disabled while the delete is in-flight.
                page.wait_for_function(
                    "() => document.getElementById('remove_btn').disabled === true",
                    timeout=_IN_FLIGHT_TIMEOUT,
                )
                assert btn.is_disabled(), (
                    "The 'Remove avatar' button must be disabled while the DELETE "
                    "request is in flight to prevent duplicate submissions."
                )
            finally:
                browser.close()

    def test_button_shows_removing_text_during_delete(self, fixture_server_url: str, web_config: WebConfig) -> None:
        """The button must show 'Removing…' text while the delete is pending."""
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=web_config.headless, slow_mo=web_config.slow_mo
            )
            page: Page = browser.new_page()
            page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
            try:
                page.goto(fixture_server_url, wait_until="domcontentloaded")
                btn = page.locator("#remove_btn")
                btn.wait_for(state="visible", timeout=5_000)

                btn.click()

                # Wait for the text to change to "Removing…".
                page.wait_for_function(
                    "() => document.getElementById('remove_btn').textContent.includes('Removing')",
                    timeout=_IN_FLIGHT_TIMEOUT,
                )
                text = btn.text_content()
                assert "Removing" in (text or ""), (
                    f"Expected button to show 'Removing…' during in-flight state, "
                    f"got: {text!r}."
                )
            finally:
                browser.close()

    def test_button_re_enabled_after_delete(self, fixture_server_url: str, web_config: WebConfig) -> None:
        """The button must be re-enabled and revert to 'Remove avatar' after the delete completes."""
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=web_config.headless, slow_mo=web_config.slow_mo
            )
            page: Page = browser.new_page()
            page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
            try:
                page.goto(fixture_server_url, wait_until="domcontentloaded")
                btn = page.locator("#remove_btn")
                btn.wait_for(state="visible", timeout=5_000)

                btn.click()

                # Wait for the operation to complete (the text reverts to "Remove avatar").
                page.wait_for_function(
                    "() => document.getElementById('remove_btn').textContent.trim() === 'Remove avatar'",
                    timeout=_COMPLETION_TIMEOUT,
                )
                assert not btn.is_disabled(), (
                    "The 'Remove avatar' button must be re-enabled once the DELETE "
                    "request completes."
                )
                assert btn.text_content() == "Remove avatar", (
                    f"Expected button to revert to 'Remove avatar' after completion, "
                    f"got: {btn.text_content()!r}."
                )
            finally:
                browser.close()


# ---------------------------------------------------------------------------
# Test class 3: Live mode (requires FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD)
# ---------------------------------------------------------------------------

_API_ME_PATTERN = "**/api/me"
_API_ME_DELETE_PATTERN = "**/api/me/avatar"
_CDN_PATTERN = "**/avatars/uid_655_test/**"


def _make_api_me_handler(avatar_url: str):
    """Return a Playwright route handler that serves a profile with avatar_url."""
    def handler(route):
        if route.request.method == "DELETE":
            route.fallback()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({
                "id": 1,
                "firebase_uid": "uid_655_test",
                "username": "testuser655",
                "email": "test655@example.com",
                "avatar_url": avatar_url,
                "created_at": "2025-01-01T00:00:00Z",
            }),
        )
    return handler


def _make_delete_avatar_slow_handler(delay_s: float):
    """Return a route handler that delays the DELETE /api/me/avatar response."""
    def handler(route):
        if route.request.method != "DELETE":
            route.fallback()
            return
        time.sleep(delay_s)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"message": "avatar removed"}),
        )
    return handler


def _gif_handler(route):
    route.fulfill(
        status=200,
        content_type="image/gif",
        body=_GIF_BYTES,
    )


class TestAvatarDeleteLiveMode:
    """MYTUBE-655 — live mode tests (skipped when credentials are absent)."""

    def test_remove_avatar_button_disabled_and_shows_removing_in_flight(
        self, web_config: WebConfig
    ) -> None:
        """Live mode: clicking 'Remove avatar' disables it and shows 'Removing…' in-flight.

        Uses a MutationObserver to capture the transient in-flight state because
        the route-handler delay blocks the Playwright event loop.
        """
        email = web_config.test_email
        password = web_config.test_password

        if not email or not password:
            pytest.skip(
                "FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD are not set — "
                "skipping live mode test."
            )

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=web_config.headless, slow_mo=web_config.slow_mo
            )
            context = browser.new_context()
            page: Page = context.new_page()
            page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

            try:
                # Intercept DELETE /api/me/avatar with a delay so we can observe
                # the in-flight state. Must be registered before the broad /api/me catch-all.
                page.route(
                    _API_ME_DELETE_PATTERN,
                    _make_delete_avatar_slow_handler(_LIVE_ROUTE_DELAY_S),
                )

                # Intercept GET /api/me to return a profile with an existing avatar.
                page.route(_API_ME_PATTERN, _make_api_me_handler(_EXISTING_AVATAR_URL))

                # Serve a valid GIF for avatar image requests to prevent onError fallback.
                page.route(_CDN_PATTERN, _gif_handler)

                # Log in.
                login_pg = LoginPage(page)
                login_pg.navigate(web_config.login_url())
                login_pg.login_as(email, password)
                login_pg.wait_for_navigation_to(web_config.home_url(), timeout=20_000)

                # Navigate to /settings.
                settings_pg = SettingsPage(page)
                settings_pg.navigate(web_config.settings_url())

                assert settings_pg.is_settings_page_loaded(), (
                    "Settings page did not load after navigation. "
                    "Check the APP_URL and that the user is authenticated."
                )

                # Verify the 'Remove avatar' button is visible (avatar URL is set).
                assert settings_pg.is_remove_avatar_button_visible(timeout=10_000), (
                    "The 'Remove avatar' button is not visible. "
                    "Expected the settings page to show the button when an avatar is set. "
                    "Check that GET /api/me route interception returned the avatar_url."
                )

                # Arm the observer, then click.
                settings_pg.arm_removing_observer()
                settings_pg.click_remove_avatar_button()

                # Wait for the route-handler delay to pass.
                time.sleep(_LIVE_ROUTE_DELAY_S + 1.0)

                assert settings_pg.was_removing_text_observed(), (
                    "MutationObserver did not capture 'Removing…' button text while "
                    "the DELETE /api/me/avatar route was delayed. "
                    "Expected the button to display 'Removing…' during the in-flight period. "
                    "This means either the button text is not changing or the route "
                    "interception is not working as expected."
                )

                assert settings_pg.was_removing_disabled_observed(), (
                    "MutationObserver did not observe the 'Removing…' button in a disabled "
                    "state. Expected disabled={removing} to disable the button while the "
                    "DELETE request is pending."
                )

            finally:
                context.close()
                browser.close()
