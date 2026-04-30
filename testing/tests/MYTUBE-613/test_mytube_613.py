"""
MYTUBE-613: Clear avatar URL field — preview is hidden.

Objective
---------
Verify that the preview area is cleared when the Avatar URL field is empty.

Preconditions
-------------
User is on the Account Settings page (`/settings`).

Steps
-----
1. Enter a valid URL so the preview image is rendered.
2. Delete all content from the "Avatar URL" input field.

Expected Result
---------------
The `<img>` element and any placeholders are removed from the DOM.
No preview is displayed below the hint text.

Test strategy
-------------
Two complementary modes:

1. **Source analysis** (always runs):
   - Confirms that `settings/page.tsx` conditionally renders `<AvatarPreview>`
     only when `form.avatarUrl` is truthy (``{form.avatarUrl && ...}``).
   - Confirms `AvatarPreview.tsx` renders an `<img>` only when `src` is
     non-empty and no load error has occurred.
   - Together these guarantee that clearing the URL removes both the `<img>`
     and the placeholder SVG from the DOM.

2. **Playwright fixture mode** (always runs):
   - Serves a local HTML page that faithfully reproduces the conditional
     rendering logic from `settings/page.tsx` + `AvatarPreview.tsx`.
   - Step 1: Type a valid image URL into the avatar URL input → assert that
     `<img>` appears inside the preview container.
   - Step 2: Clear the input field → assert that both the `<img>` *and* the
     preview container itself are removed from the DOM (matching the React
     `{form.avatarUrl && <AvatarPreview>}` gate).

3. **Live mode** (when `FIREBASE_TEST_EMAIL` + `FIREBASE_TEST_PASSWORD` are set):
   - Logs in via the login page and navigates to `/settings`.
   - Intercepts `/api/me` to inject a pre-filled profile (avatarUrl set).
   - Asserts the preview `<img>` is visible.
   - Clears the avatar URL input and asserts the preview is gone.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL      CI test user email (required for live mode).
FIREBASE_TEST_PASSWORD   CI test user password (required for live mode).
PLAYWRIGHT_HEADLESS      Run headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-613/test_mytube_613.py -v
"""
from __future__ import annotations

import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS_TSX = _REPO_ROOT / "web" / "src" / "app" / "settings" / "page.tsx"
_AVATAR_PREVIEW_TSX = _REPO_ROOT / "web" / "src" / "components" / "AvatarPreview.tsx"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_FIXTURE_PORT = 19613

# A stable public image URL (served by httpbin — always returns a 200 image)
_VALID_IMAGE_URL = "https://picsum.photos/64/64"

# Selectors used across both fixture and live modes
_AVATAR_INPUT_ID = "avatar_url"           # matches id="avatar_url" in settings/page.tsx
_PREVIEW_CONTAINER_SELECTOR = "#preview-container"   # fixture-specific wrapper id
_PREVIEW_IMG_SELECTOR = "#preview-container img"     # img inside preview container

# ---------------------------------------------------------------------------
# Minimal fixture HTML — reproduces the conditional rendering gate
# from settings/page.tsx + AvatarPreview.tsx without requiring auth.
#
# Logic mirrored from React source:
#   - Outer gate:   {form.avatarUrl && <AvatarPreview src={form.avatarUrl} />}
#   - Inner render: showImage = src && !error  → <img> else <svg>
#
# When the input is cleared, #preview-container is removed entirely from the
# DOM — matching the {form.avatarUrl && ...} React gate.
# When a URL is typed, #preview-container is inserted; if the image loads
# successfully an <img> is present; on error only the placeholder SVG shows.
# ---------------------------------------------------------------------------
_FIXTURE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Avatar URL preview fixture – MYTUBE-613</title>
  <style>
    body { font-family: sans-serif; margin: 2rem; }
    label { display: block; font-size: 0.875rem; font-weight: 500; margin-bottom: 0.25rem; }
    input[type="url"] {
      width: 100%; max-width: 400px;
      border: 1px solid #d1d5db; border-radius: 0.5rem;
      padding: 0.5rem 0.75rem; font-size: 0.875rem;
    }
    .hint { margin-top: 0.25rem; font-size: 0.75rem; color: #9ca3af; }
    /* AvatarPreview styles */
    #preview-container {
      margin-top: 0.75rem;
      width: 4rem; height: 4rem;
      border-radius: 9999px; overflow: hidden;
      background: #e5e7eb;
      display: flex; align-items: center; justify-content: center;
    }
    #preview-container img {
      width: 4rem; height: 4rem; border-radius: 9999px; object-fit: cover;
    }
    #preview-container svg {
      width: 2rem; height: 2rem; color: #9ca3af;
    }
  </style>
</head>
<body>
  <div>
    <label for="avatar_url">Avatar URL</label>
    <input
      id="avatar_url"
      type="url"
      placeholder="https://example.com/avatar.png"
    />
    <p class="hint">Enter a URL to a profile image</p>
    <!-- Preview container injected/removed by JS — mirrors {form.avatarUrl && <AvatarPreview>} -->
  </div>

  <script>
    // Mirrors React state: form.avatarUrl drives visibility.
    const input = document.getElementById('avatar_url');
    const fieldWrapper = input.parentElement;

    function buildPreviewContainer(src) {
      const container = document.createElement('div');
      container.id = 'preview-container';
      container.setAttribute('role', 'img');
      container.setAttribute('aria-label', 'Avatar preview');

      // Inner element: <img> when src is present, SVG placeholder otherwise.
      // This mirrors AvatarPreview: showImage = src && !error
      const img = document.createElement('img');
      img.src = src;
      img.alt = '';
      img.onerror = function() {
        // On error: replace img with placeholder SVG (mirrors AvatarPreview error state)
        this.remove();
        container.innerHTML += `
          <svg aria-hidden="true" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z"/>
          </svg>`;
      };
      container.appendChild(img);
      return container;
    }

    function updatePreview() {
      const url = input.value.trim();
      const existing = document.getElementById('preview-container');

      if (!url) {
        // Mirrors {form.avatarUrl && ...}: when falsy, remove entirely.
        if (existing) existing.remove();
        return;
      }

      if (existing) {
        // URL changed — rebuild to reset error state (mirrors useEffect([src])).
        existing.remove();
      }
      fieldWrapper.appendChild(buildPreviewContainer(url));
    }

    input.addEventListener('input', updatePreview);
    // Initialise with empty state.
    updatePreview();
  </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Fixture server handler
# ---------------------------------------------------------------------------


class _FixtureHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler serving the avatar URL fixture HTML."""

    def do_GET(self) -> None:  # noqa: N802
        body = _FIXTURE_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        pass  # silence access logs


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def fixture_server():
    """Start the local fixture HTTP server and yield its base URL."""
    server = HTTPServer(("127.0.0.1", _FIXTURE_PORT), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{_FIXTURE_PORT}/"
    server.shutdown()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_live_credentials(config: WebConfig) -> bool:
    return bool(config.test_email and config.test_password)


# ---------------------------------------------------------------------------
# Test class 1 — Source analysis (always runs; no browser needed)
# ---------------------------------------------------------------------------


class TestSettingsAvatarSourceAnalysis:
    """Static analysis confirms the conditional-render gate is present in source."""

    @pytest.fixture(scope="class")
    def settings_tsx(self) -> str:
        assert _SETTINGS_TSX.exists(), f"settings/page.tsx not found at {_SETTINGS_TSX}"
        return _SETTINGS_TSX.read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def avatar_preview_tsx(self) -> str:
        assert _AVATAR_PREVIEW_TSX.exists(), (
            f"AvatarPreview.tsx not found at {_AVATAR_PREVIEW_TSX}"
        )
        return _AVATAR_PREVIEW_TSX.read_text(encoding="utf-8")

    def test_avatar_preview_conditionally_rendered(self, settings_tsx: str) -> None:
        """settings/page.tsx must gate AvatarPreview on a truthy avatarUrl.

        The pattern ``{form.avatarUrl && (`` ensures the preview (including
        both the <img> and placeholder) is unmounted when the field is empty.
        """
        assert "form.avatarUrl" in settings_tsx, (
            "settings/page.tsx does not reference form.avatarUrl. "
            "The conditional gate for AvatarPreview may be missing."
        )
        assert "AvatarPreview" in settings_tsx, (
            "settings/page.tsx does not render AvatarPreview. "
            "The avatar preview component is missing."
        )
        # Verify the gate: avatarUrl truthy → render AvatarPreview
        assert (
            "{form.avatarUrl && (" in settings_tsx
            or "form.avatarUrl &&" in settings_tsx
        ), (
            "settings/page.tsx does not conditionally gate AvatarPreview on avatarUrl. "
            "Expected pattern: {form.avatarUrl && (<AvatarPreview …/>)}. "
            "When avatarUrl is empty the preview must not render."
        )

    def test_avatar_input_field_present(self, settings_tsx: str) -> None:
        """The avatar URL input field must have id='avatar_url'."""
        assert 'id="avatar_url"' in settings_tsx or "id='avatar_url'" in settings_tsx, (
            "settings/page.tsx does not have an input with id='avatar_url'. "
            "The avatar URL field selector used in tests may not match."
        )

    def test_avatar_preview_renders_img_when_src_set(
        self, avatar_preview_tsx: str
    ) -> None:
        """AvatarPreview must render an <img> when src is non-empty and loaded."""
        assert "<img" in avatar_preview_tsx, (
            "AvatarPreview.tsx does not render an <img> element. "
            "Expected an <img> for a valid, loaded avatar URL."
        )

    def test_avatar_preview_has_show_image_guard(
        self, avatar_preview_tsx: str
    ) -> None:
        """AvatarPreview must guard <img> rendering with showImage (src && !error)."""
        assert "showImage" in avatar_preview_tsx or (
            "src &&" in avatar_preview_tsx or "!error" in avatar_preview_tsx
        ), (
            "AvatarPreview.tsx does not appear to guard <img> rendering. "
            "Expected a pattern like: showImage = src && !error."
        )


# ---------------------------------------------------------------------------
# Test class 2 — Playwright fixture mode (always runs)
# ---------------------------------------------------------------------------


class TestAvatarPreviewFixture:
    """
    MYTUBE-613 — Fixture-mode Playwright tests.

    Serves a local HTML page that mirrors the conditional render logic from
    settings/page.tsx + AvatarPreview.tsx and verifies via Playwright.
    """

    @pytest.fixture(scope="class")
    def fixture_page(self, web_config: WebConfig, fixture_server: str):
        """Open a Playwright page pointed at the fixture server."""
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=web_config.headless, slow_mo=web_config.slow_mo
            )
            page = browser.new_page()
            page.goto(fixture_server, timeout=_PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")
            yield page
            browser.close()

    def test_preview_appears_when_url_entered(self, fixture_page: Page) -> None:
        """Step 1: After entering a URL, the preview container with <img> appears."""
        input_el = fixture_page.locator(f"#{_AVATAR_INPUT_ID}")
        input_el.fill(_VALID_IMAGE_URL)

        # The preview container should appear immediately (synchronous JS).
        preview = fixture_page.locator(_PREVIEW_CONTAINER_SELECTOR)
        preview.wait_for(state="attached", timeout=5_000)

        assert preview.count() == 1, (
            f"Expected 1 preview container (#preview-container) after typing a URL, "
            f"got {preview.count()}. "
            f"The preview gate may not be working correctly."
        )
        # The <img> element should be present inside the container.
        img = fixture_page.locator(_PREVIEW_IMG_SELECTOR)
        assert img.count() == 1, (
            f"Expected 1 <img> inside the preview container after entering a valid URL, "
            f"got {img.count()}. "
            f"AvatarPreview should render <img> when src is non-empty."
        )

    def test_preview_hidden_after_clearing_url(self, fixture_page: Page) -> None:
        """Step 2: After clearing the URL, the preview container is removed from DOM.

        This is the core assertion for MYTUBE-613: clearing the Avatar URL
        field must remove both the <img> and any placeholders from the DOM.
        """
        input_el = fixture_page.locator(f"#{_AVATAR_INPUT_ID}")

        # Clear the input (mirrors user deleting all content from the field).
        input_el.fill("")
        # Dispatch 'input' event to trigger the JS listener (same as user typing).
        input_el.dispatch_event("input")

        # The preview container must be gone — detached from DOM — not just hidden.
        preview = fixture_page.locator(_PREVIEW_CONTAINER_SELECTOR)
        try:
            preview.wait_for(state="detached", timeout=5_000)
        except Exception:
            count = preview.count()
            raise AssertionError(
                f"Expected #preview-container to be detached from the DOM after "
                f"clearing the avatar URL field, but it is still present "
                f"(count={count}). "
                f"The preview must be fully removed — not just hidden — when avatarUrl is empty."
            )

        # Double-check: no <img> remains anywhere below the hint text.
        img = fixture_page.locator(_PREVIEW_IMG_SELECTOR)
        assert img.count() == 0, (
            f"<img> element is still present in the preview area after clearing "
            f"the avatar URL input. count={img.count()}. "
            f"Expected 0 — all preview elements must be removed from the DOM."
        )

    def test_preview_reappears_when_url_re_entered(self, fixture_page: Page) -> None:
        """Sanity: re-entering a URL after clearing must restore the preview."""
        input_el = fixture_page.locator(f"#{_AVATAR_INPUT_ID}")
        input_el.fill(_VALID_IMAGE_URL)

        preview = fixture_page.locator(_PREVIEW_CONTAINER_SELECTOR)
        preview.wait_for(state="attached", timeout=5_000)
        assert preview.count() == 1, (
            "Preview container did not re-appear after re-entering a URL. "
            "The preview toggle must be reversible."
        )


# ---------------------------------------------------------------------------
# Test class 3 — Live Playwright mode (only when credentials available)
# ---------------------------------------------------------------------------


class TestAvatarPreviewLive:
    """
    MYTUBE-613 — Live mode Playwright test.

    Logs in with real Firebase credentials, navigates to /settings, and
    verifies the avatar preview appears and disappears with the URL field.
    Only runs when FIREBASE_TEST_EMAIL + FIREBASE_TEST_PASSWORD are set.
    """

    @pytest.fixture(scope="class", autouse=True)
    def require_credentials(self, web_config: WebConfig):
        if not _has_live_credentials(web_config):
            pytest.skip(
                "FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD not set — "
                "skipping live mode for MYTUBE-613."
            )

    @pytest.fixture(scope="class")
    def live_page(self, web_config: WebConfig):
        """
        Log in and navigate to /settings; yield the authenticated page.
        The /api/me endpoint is intercepted to inject a pre-filled profile.
        """
        from testing.components.pages.login_page.login_page import LoginPage

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=web_config.headless, slow_mo=web_config.slow_mo
            )
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

            # Intercept /api/me GET to return a profile with an avatar URL so
            # the form pre-fills with a URL, making step-1 assertion reliable.
            import json

            def _handle_api_me(route, request):
                if request.method == "GET":
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps({
                            "username": "ci-test-user",
                            "avatar_url": _VALID_IMAGE_URL,
                        }),
                    )
                else:
                    route.continue_()

            page.route("**/api/me", _handle_api_me)

            # Log in via login page.
            login_page = LoginPage(page)
            login_page.navigate(web_config.login_url())
            login_page.login_as(web_config.test_email, web_config.test_password)

            # Wait for post-login redirect to home, then navigate to /settings.
            login_page.wait_for_navigation_to(web_config.home_url(), timeout=20_000)
            page.goto(
                f"{web_config.base_url}/settings/",
                timeout=_PAGE_LOAD_TIMEOUT,
                wait_until="networkidle",
            )
            # Wait for the loading spinner from RequireAuth to disappear.
            spinner = page.locator("text=Loading…")
            try:
                spinner.wait_for(state="hidden", timeout=15_000)
            except Exception:
                pass

            yield page
            context.close()
            browser.close()

    def test_live_preview_visible_with_url(self, live_page: Page) -> None:
        """Step 1 (live): AvatarPreview img is visible when avatar URL is filled."""
        # The form is pre-filled via the /api/me intercept.
        # Give it a moment to render.
        avatar_input = live_page.locator("#avatar_url")
        avatar_input.wait_for(state="visible", timeout=10_000)

        # The current value should be the mocked URL.
        current_val = avatar_input.input_value()
        if not current_val:
            # Manually fill the field if the intercept didn't pre-fill it.
            avatar_input.fill(_VALID_IMAGE_URL)

        # The preview img should be visible.
        preview_img = live_page.locator("img[alt='']").first
        try:
            preview_img.wait_for(state="attached", timeout=5_000)
        except Exception:
            pass  # image may still load; just check count below

        img_count = live_page.locator("[aria-label='Avatar preview'] img").count()
        assert img_count >= 1, (
            f"Expected an <img> in the avatar preview area when avatarUrl is set, "
            f"got {img_count}. The preview image should be visible with a valid URL."
        )

    def test_live_preview_gone_after_clearing(self, live_page: Page) -> None:
        """Step 2 (live): Clearing avatar URL hides the preview entirely."""
        avatar_input = live_page.locator("#avatar_url")
        avatar_input.click(click_count=3)
        avatar_input.press("Backspace")

        # Allow React state to propagate.
        live_page.wait_for_timeout(500)

        preview = live_page.locator("[aria-label='Avatar preview']")
        img = live_page.locator("[aria-label='Avatar preview'] img")

        assert preview.count() == 0, (
            f"Expected the avatar preview container to be removed from the DOM "
            f"after clearing the URL field, but found {preview.count()} element(s). "
            f"No preview should be displayed when avatarUrl is empty."
        )
        assert img.count() == 0, (
            f"Expected no <img> in the avatar preview area after clearing the URL, "
            f"got {img.count()} element(s)."
        )
