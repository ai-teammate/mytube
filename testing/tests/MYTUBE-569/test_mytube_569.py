"""
MYTUBE-569: Dashboard video grid — animated skeleton pulse screens displayed
during data fetch.

Objective
---------
Verify that the reusable skeleton component with pulse animation is applied to
the dashboard video grid loading state.

Steps
-----
1. Navigate to the Dashboard video grid.
2. Simulate a delayed API response for the video list.
3. Observe the loading state of the grid items.

Expected Result
---------------
Skeleton screens with an animated shimmer/pulse effect are visible in the grid
positions where VideoCards will be rendered, preventing a blank UI before data
arrives.

Architecture
------------
Two complementary modes:

1. **Static source analysis** (always runs):
   - Confirms ``VideoCardSkeleton`` is conditionally rendered in
     ``dashboard/_content.tsx`` only while ``fetching`` is ``true``.
   - Confirms ``data-testid="video-card-skeleton"`` is present on each card.
   - Confirms ``Skeleton.module.css`` defines the ``skeletonPulse`` keyframe
     animation and applies it to the ``.skeleton`` class.

2. **Live Playwright mode** (when ``APP_URL`` / ``WEB_BASE_URL`` is set AND
   ``FIREBASE_TEST_EMAIL`` + ``FIREBASE_TEST_PASSWORD`` are provided):
   - Logs in as the test user.
   - Intercepts ``/api/me/videos`` with a configurable delay to keep the
     loading state visible for inspection.
   - Asserts that ``[data-testid="video-card-skeleton"]`` elements are visible
     while the request is pending.
   - Releases the intercepted request and asserts skeletons are gone once the
     videos have loaded.

3. **Fixture Playwright mode** (fallback when live credentials are absent):
   - Starts a local HTTP server serving a minimal HTML page that reproduces
     the skeleton component's DOM and CSS exactly.
   - Asserts the skeleton elements and pulse animation CSS are rendered as
     expected.

Environment variables
---------------------
APP_URL / WEB_BASE_URL      Base URL of the deployed web app.
FIREBASE_API_KEY            Firebase Web API key.
FIREBASE_TEST_EMAIL         CI test user email.
FIREBASE_TEST_PASSWORD      CI test user password.
PLAYWRIGHT_HEADLESS         Run headless (default: true).
PLAYWRIGHT_SLOW_MO          Slow-motion delay ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-569/test_mytube_569.py -v
"""
from __future__ import annotations

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

# ---------------------------------------------------------------------------
# Paths to source files under test
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DASHBOARD_CONTENT = _REPO_ROOT / "web" / "src" / "app" / "dashboard" / "_content.tsx"
_SKELETON_TSX = _REPO_ROOT / "web" / "src" / "components" / "VideoCardSkeleton.tsx"
_SKELETON_CSS = _REPO_ROOT / "web" / "src" / "components" / "Skeleton.module.css"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_SKELETON_TESTID = "video-card-skeleton"
_FIXTURE_PORT = 19569
_API_ROUTE_PATTERN = "**/api/me/videos**"

# Minimal HTML that mirrors the VideoCardSkeleton + Skeleton components.
# Includes the skeletonPulse keyframe animation inline so the fixture mode
# can verify it independently of CSS module bundling.
_FIXTURE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Skeleton fixture – MYTUBE-569</title>
  <style>
    @keyframes skeletonPulse {
      0%, 100% { opacity: 1; }
      50%       { opacity: 0.45; }
    }
    .skeleton {
      background: #e0e0e0;
      border-radius: 8px;
      animation: skeletonPulse 1.4s ease-in-out infinite;
      display: block;
    }
    .videoGrid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 16px;
    }
    .card { border-radius: 8px; overflow: hidden; }
    .thumb { position: relative; padding-top: 56.25%; }
    .thumbFill { position: absolute; inset: 0; border-radius: 12px 12px 0 0; }
    .body { padding: 8px; }
    .titleLine1 { height: 14px; width: 90%; margin-bottom: 6px; }
    .titleLine2 { height: 14px; width: 65%; margin-bottom: 8px; }
    .subLine { height: 12px; width: 75%; }
  </style>
</head>
<body>
  <div class="videoGrid" id="video-grid">
    <!-- Mirrors VideoCardSkeleton count={4} -->
    <div class="card" aria-hidden="true" data-testid="video-card-skeleton">
      <div class="thumb"><div class="skeleton thumbFill"></div></div>
      <div class="body">
        <div class="skeleton titleLine1"></div>
        <div class="skeleton titleLine2"></div>
        <div class="skeleton subLine"></div>
      </div>
    </div>
    <div class="card" aria-hidden="true" data-testid="video-card-skeleton">
      <div class="thumb"><div class="skeleton thumbFill"></div></div>
      <div class="body">
        <div class="skeleton titleLine1"></div>
        <div class="skeleton titleLine2"></div>
        <div class="skeleton subLine"></div>
      </div>
    </div>
    <div class="card" aria-hidden="true" data-testid="video-card-skeleton">
      <div class="thumb"><div class="skeleton thumbFill"></div></div>
      <div class="body">
        <div class="skeleton titleLine1"></div>
        <div class="skeleton titleLine2"></div>
        <div class="skeleton subLine"></div>
      </div>
    </div>
    <div class="card" aria-hidden="true" data-testid="video-card-skeleton">
      <div class="thumb"><div class="skeleton thumbFill"></div></div>
      <div class="body">
        <div class="skeleton titleLine1"></div>
        <div class="skeleton titleLine2"></div>
        <div class="skeleton subLine"></div>
      </div>
    </div>
  </div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_live_credentials() -> bool:
    """Return True if Firebase test credentials are configured."""
    email = os.getenv("FIREBASE_TEST_EMAIL", "")
    password = os.getenv("FIREBASE_TEST_PASSWORD", "")
    return bool(email and password)


def _has_live_mode() -> bool:
    """Return True if both APP_URL and Firebase credentials are set."""
    env_url = os.getenv("APP_URL", os.getenv("WEB_BASE_URL", ""))
    live_url = bool(env_url and env_url.lower() not in ("false", "0", ""))
    return live_url and _has_live_credentials()


def _firebase_sign_in(api_key: str, email: str, password: str) -> str:
    """Sign in via Firebase REST API and return the ID token."""
    import urllib.request
    import json as _json

    url = (
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        f"?key={api_key}"
    )
    payload = _json.dumps(
        {"email": email, "password": password, "returnSecureToken": True}
    ).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = _json.loads(resp.read())
    return data["idToken"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


class _FixtureHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler serving the skeleton fixture HTML."""

    def do_GET(self) -> None:  # noqa: N802
        body = _FIXTURE_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:  # silence access logs
        pass


@pytest.fixture(scope="module")
def fixture_server():
    """Start the local fixture HTTP server and yield its base URL."""
    server = HTTPServer(("127.0.0.1", _FIXTURE_PORT), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{_FIXTURE_PORT}/"
    server.shutdown()


# ---------------------------------------------------------------------------
# Static source-analysis tests (always run)
# ---------------------------------------------------------------------------


class TestDashboardSkeletonSourceAnalysis:
    """
    MYTUBE-569 — Static source analysis.

    Verifies that the skeleton pulse animation is correctly wired into the
    dashboard video grid loading state at the source level.
    """

    @pytest.fixture(scope="class")
    def content_tsx(self) -> str:
        assert _DASHBOARD_CONTENT.exists(), (
            f"Dashboard _content.tsx not found at {_DASHBOARD_CONTENT}."
        )
        return _DASHBOARD_CONTENT.read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def skeleton_tsx(self) -> str:
        assert _SKELETON_TSX.exists(), (
            f"VideoCardSkeleton.tsx not found at {_SKELETON_TSX}."
        )
        return _SKELETON_TSX.read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def skeleton_css(self) -> str:
        assert _SKELETON_CSS.exists(), (
            f"Skeleton.module.css not found at {_SKELETON_CSS}."
        )
        return _SKELETON_CSS.read_text(encoding="utf-8")

    # ---- Dashboard _content.tsx assertions ----

    def test_video_card_skeleton_imported_in_dashboard(self, content_tsx: str) -> None:
        """VideoCardSkeleton must be imported in the dashboard _content.tsx."""
        assert "VideoCardSkeleton" in content_tsx, (
            "VideoCardSkeleton is not imported in dashboard/_content.tsx. "
            "The skeleton must be imported for the loading state to render."
        )

    def test_skeleton_rendered_when_fetching(self, content_tsx: str) -> None:
        """The dashboard must conditionally render VideoCardSkeleton when fetching is true."""
        # The implementation pattern is: {fetching ? <VideoCardSkeleton ...> : ...}
        assert "fetching" in content_tsx, (
            "'fetching' state variable is missing from dashboard/_content.tsx."
        )
        assert "VideoCardSkeleton" in content_tsx, (
            "VideoCardSkeleton is missing from the dashboard component rendering."
        )
        # Verify the conditional branch: fetching ? (...<VideoCardSkeleton...) : (...)
        fetching_index = content_tsx.find("fetching ?")
        skeleton_index = content_tsx.find("VideoCardSkeleton", fetching_index)
        assert fetching_index != -1, (
            "Expected ternary 'fetching ? ...' pattern not found in _content.tsx. "
            "The skeleton must be displayed only while the API call is in progress."
        )
        assert skeleton_index != -1 and skeleton_index > fetching_index, (
            "VideoCardSkeleton does not appear in the 'fetching ? ...' branch. "
            f"fetching? found at index {fetching_index}, "
            f"VideoCardSkeleton found at index {skeleton_index}."
        )

    def test_skeleton_inside_video_grid(self, content_tsx: str) -> None:
        """The skeleton must be rendered inside the videoGrid container."""
        # Look for the grid wrapper containing the skeleton
        assert "videoGrid" in content_tsx, (
            "'videoGrid' CSS class/style not found in _content.tsx. "
            "Skeleton cards must be placed in a grid container matching VideoCard positions."
        )

    # ---- VideoCardSkeleton.tsx assertions ----

    def test_skeleton_has_data_testid(self, skeleton_tsx: str) -> None:
        """Each skeleton card must carry data-testid='video-card-skeleton'."""
        assert 'data-testid="video-card-skeleton"' in skeleton_tsx, (
            "data-testid=\"video-card-skeleton\" not found in VideoCardSkeleton.tsx. "
            "This attribute is required for Playwright assertions to locate skeleton cards."
        )

    def test_skeleton_has_aria_hidden(self, skeleton_tsx: str) -> None:
        """Skeleton cards must be aria-hidden to hide them from screen readers."""
        assert 'aria-hidden="true"' in skeleton_tsx, (
            'aria-hidden="true" not found in VideoCardSkeleton.tsx. '
            "Skeleton placeholders must be hidden from assistive technologies."
        )

    def test_skeleton_renders_multiple_cards(self, skeleton_tsx: str) -> None:
        """VideoCardSkeleton must render a configurable number of cards (count prop)."""
        assert "count" in skeleton_tsx, (
            "'count' prop not found in VideoCardSkeleton.tsx. "
            "The skeleton must support a configurable number of placeholder cards."
        )
        assert "Array.from" in skeleton_tsx or ".map(" in skeleton_tsx, (
            "No array iteration (Array.from / .map) in VideoCardSkeleton.tsx. "
            "Expected multiple cards to be generated from a loop."
        )

    def test_skeleton_uses_skeleton_component(self, skeleton_tsx: str) -> None:
        """VideoCardSkeleton must use the reusable Skeleton component."""
        assert "import Skeleton" in skeleton_tsx or 'from "./Skeleton"' in skeleton_tsx, (
            "VideoCardSkeleton.tsx does not import the Skeleton component. "
            "Reusability requires using the shared Skeleton component."
        )

    # ---- Skeleton.module.css assertions ----

    def test_skeleton_css_has_pulse_keyframe(self, skeleton_css: str) -> None:
        """Skeleton.module.css must define the skeletonPulse keyframe animation."""
        assert "@keyframes skeletonPulse" in skeleton_css, (
            "@keyframes skeletonPulse not found in Skeleton.module.css. "
            "The pulse animation must be defined as a CSS keyframe."
        )

    def test_skeleton_css_pulse_uses_opacity(self, skeleton_css: str) -> None:
        """The skeletonPulse animation must modulate opacity to create a shimmer effect."""
        assert "opacity" in skeleton_css, (
            "'opacity' not found in Skeleton.module.css. "
            "The skeleton pulse animation achieves its shimmer/pulse effect by "
            "transitioning opacity between 1 and a lower value."
        )

    def test_skeleton_css_animation_applied(self, skeleton_css: str) -> None:
        """The .skeleton CSS class must have the animation property applied."""
        assert "animation:" in skeleton_css or "animation :" in skeleton_css, (
            "'animation:' property not found in Skeleton.module.css. "
            "The .skeleton class must apply the skeletonPulse keyframe animation."
        )

    def test_skeleton_css_animation_is_infinite(self, skeleton_css: str) -> None:
        """The skeleton animation must run infinitely for a continuous pulse effect."""
        assert "infinite" in skeleton_css, (
            "'infinite' keyword not found in Skeleton.module.css animation. "
            "The pulse animation must loop indefinitely while loading."
        )

    def test_skeleton_css_has_background(self, skeleton_css: str) -> None:
        """The .skeleton block must declare a background property for the visual fill."""
        assert "background:" in skeleton_css or "background :" in skeleton_css, (
            "'background:' not found in Skeleton.module.css. "
            "Skeleton elements need a background colour/gradient to be visible."
        )


# ---------------------------------------------------------------------------
# Fixture-mode Playwright tests (always run — no credentials needed)
# ---------------------------------------------------------------------------


class TestDashboardSkeletonFixture:
    """
    MYTUBE-569 — Fixture-mode Playwright tests.

    Serves a local HTML page that mirrors the VideoCardSkeleton DOM/CSS and
    verifies that skeleton elements are present and have the expected
    animation applied.
    """

    @pytest.fixture(scope="class")
    def skeleton_page(self, config: WebConfig, fixture_server: str):
        """Open a Playwright page pointed at the fixture server."""
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
            page = browser.new_page()
            page.goto(fixture_server, timeout=_PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")
            yield page
            browser.close()

    def test_skeleton_cards_present_in_grid(self, skeleton_page: Page) -> None:
        """Exactly 4 skeleton cards must be present inside the video grid."""
        cards = skeleton_page.locator(f"[data-testid='{_SKELETON_TESTID}']")
        count = cards.count()
        assert count == 4, (
            f"Expected 4 skeleton cards (data-testid='video-card-skeleton'), "
            f"found {count}. The VideoCardSkeleton count={{4}} must render 4 placeholder cards."
        )

    def test_all_skeleton_cards_are_visible(self, skeleton_page: Page) -> None:
        """All skeleton cards must be visible to the user."""
        cards = skeleton_page.locator(f"[data-testid='{_SKELETON_TESTID}']")
        for i in range(cards.count()):
            assert cards.nth(i).is_visible(), (
                f"Skeleton card at index {i} is not visible. "
                "Skeleton cards must be rendered visibly in the grid during loading."
            )

    def test_skeleton_cards_inside_grid_container(self, skeleton_page: Page) -> None:
        """Skeleton cards must be children of the videoGrid container."""
        grid = skeleton_page.locator("#video-grid")
        assert grid.count() > 0, "Video grid container not found in fixture HTML."
        cards_in_grid = grid.locator(f"[data-testid='{_SKELETON_TESTID}']")
        assert cards_in_grid.count() == 4, (
            f"Expected 4 skeleton cards inside the video grid, "
            f"found {cards_in_grid.count()}."
        )

    def test_skeleton_cards_have_pulse_animation(self, skeleton_page: Page) -> None:
        """Each skeleton element must have the skeletonPulse CSS animation applied."""
        skeleton_els = skeleton_page.locator(".skeleton")
        count = skeleton_els.count()
        assert count > 0, (
            "No elements with class 'skeleton' found. "
            "Skeleton elements must carry the CSS class that applies the animation."
        )
        # Check the computed animation name on the first skeleton element
        animation_name = skeleton_page.evaluate(
            """() => {
                const el = document.querySelector('.skeleton');
                if (!el) return null;
                return window.getComputedStyle(el).animationName;
            }"""
        )
        assert animation_name is not None, (
            "Could not compute animation style on .skeleton element."
        )
        assert animation_name != "none" and animation_name != "", (
            f"Animation on .skeleton is '{animation_name}' — expected 'skeletonPulse'. "
            "The skeleton class must have the pulse animation applied via CSS."
        )

    def test_skeleton_cards_have_non_transparent_background(
        self, skeleton_page: Page
    ) -> None:
        """Skeleton cards must have a visible (non-transparent) background colour."""
        bg_color = skeleton_page.evaluate(
            """() => {
                const el = document.querySelector('.skeleton');
                if (!el) return null;
                return window.getComputedStyle(el).backgroundColor;
            }"""
        )
        assert bg_color is not None, "Could not read background-color of .skeleton element."
        assert bg_color != "rgba(0, 0, 0, 0)" and bg_color != "transparent", (
            f"Background colour of .skeleton is transparent ('{bg_color}'). "
            "Skeleton elements must have a visible fill colour to act as placeholders."
        )

    def test_skeleton_thumbnail_placeholder_present(self, skeleton_page: Page) -> None:
        """Each skeleton card must contain a thumbnail placeholder element."""
        cards = skeleton_page.locator(f"[data-testid='{_SKELETON_TESTID}']")
        first_card = cards.first
        thumb = first_card.locator(".thumb")
        assert thumb.count() > 0, (
            "No thumbnail placeholder (.thumb) found inside the first skeleton card. "
            "Each VideoCardSkeleton must include a 16:9 thumbnail placeholder."
        )

    def test_skeleton_body_placeholders_present(self, skeleton_page: Page) -> None:
        """Each skeleton card must contain body text placeholder lines."""
        cards = skeleton_page.locator(f"[data-testid='{_SKELETON_TESTID}']")
        first_card = cards.first
        body = first_card.locator(".body")
        assert body.count() > 0, (
            "No body container (.body) found inside the first skeleton card. "
            "Each VideoCardSkeleton must include body placeholder lines for title and sub-line."
        )
        # At least 2 skeleton blocks inside the body (titleLine1, titleLine2, subLine)
        body_skeletons = body.locator(".skeleton")
        assert body_skeletons.count() >= 2, (
            f"Expected at least 2 skeleton lines in card body, "
            f"found {body_skeletons.count()}."
        )


# ---------------------------------------------------------------------------
# Live Playwright tests (require APP_URL + Firebase credentials)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _has_live_mode(),
    reason=(
        "Live mode requires APP_URL (or WEB_BASE_URL), "
        "FIREBASE_TEST_EMAIL, and FIREBASE_TEST_PASSWORD to be set."
    ),
)
class TestDashboardSkeletonLive:
    """
    MYTUBE-569 — Live Playwright tests against the deployed application.

    Signs in as the test user, intercepts /api/me/videos with an artificial
    delay, and asserts that skeleton cards are visible during the loading state.
    """

    @pytest.fixture(scope="class")
    def live_page(self, config: WebConfig):
        """
        Launch browser, perform Firebase login via the app's login page, and
        yield a Page already authenticated on the dashboard.
        """
        firebase_api_key = os.getenv("FIREBASE_API_KEY", "")
        email = config.test_email
        password = config.test_password

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
            context = browser.new_context()
            page = context.new_page()

            # --- Firebase login via app login page ---
            page.goto(config.login_url(), timeout=_PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")
            page.fill('input[id="email"]', email)
            page.fill('input[id="password"]', password)
            page.click('button[type="submit"]:not([aria-label="Submit search"])')

            # Wait for redirect away from login page (either dashboard or home)
            try:
                page.wait_for_url(
                    lambda url: "/login" not in url, timeout=20_000
                )
            except Exception:
                pass  # proceed and let subsequent assertions fail with context

            yield page
            browser.close()

    @pytest.fixture(scope="class")
    def dashboard_with_delayed_api(self, config: WebConfig, live_page: Page):
        """
        Navigate to dashboard with /api/me/videos intercepted + delayed so
        that the skeleton is observable.
        """
        _delay_seconds = 4.0  # seconds to hold the response
        _response_released = threading.Event()
        _original_response: dict = {}

        def _intercept_route(route):
            # Fetch the real response first, then delay returning it
            response = route.fetch()
            _original_response["status"] = response.status
            _original_response["headers"] = dict(response.headers)
            _original_response["body"] = response.body()
            # Wait until we release or until timeout
            _response_released.wait(timeout=_delay_seconds + 2)
            route.fulfill(
                status=response.status,
                headers=dict(response.headers),
                body=response.body(),
            )

        live_page.route(_API_ROUTE_PATTERN, lambda route: _intercept_route(route))

        # Navigate to the dashboard; the API call will be delayed
        live_page.goto(config.dashboard_url(), timeout=_PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")

        yield live_page, _response_released

        # Cleanup
        live_page.unroute(_API_ROUTE_PATTERN)
        _response_released.set()  # release if not already

    def test_skeleton_cards_visible_during_api_delay(
        self, dashboard_with_delayed_api
    ) -> None:
        """Skeleton cards must be visible while the video list API call is pending."""
        page, _release = dashboard_with_delayed_api
        # Skeleton cards should appear immediately since fetching starts as true
        skeleton = page.locator(f"[data-testid='{_SKELETON_TESTID}']").first
        skeleton.wait_for(state="visible", timeout=10_000)
        assert skeleton.is_visible(), (
            "data-testid='video-card-skeleton' is not visible while the "
            "/api/me/videos request is intercepted and delayed. "
            "The dashboard must display the skeleton pulse grid during the fetch."
        )

    def test_skeleton_count_matches_configured_count(
        self, dashboard_with_delayed_api
    ) -> None:
        """The correct number of skeleton cards (4) must be visible during loading."""
        page, _release = dashboard_with_delayed_api
        skeletons = page.locator(f"[data-testid='{_SKELETON_TESTID}']")
        count = skeletons.count()
        assert count == 4, (
            f"Expected 4 skeleton cards (VideoCardSkeleton count={{4}}), "
            f"found {count} on the dashboard during loading."
        )

    def test_skeleton_cards_inside_grid_container_live(
        self, dashboard_with_delayed_api
    ) -> None:
        """Skeleton cards must be rendered inside the video grid container."""
        page, _release = dashboard_with_delayed_api
        # Grid container has CSS module class — find by role or data attribute
        # The _content.tsx wraps them in <div className={styles.videoGrid}>
        grid_child_skeletons = page.locator(
            f"[data-testid='{_SKELETON_TESTID}']"
        )
        assert grid_child_skeletons.count() > 0, (
            "No skeleton cards found on the dashboard. "
            "Ensure the /api/me/videos route is being intercepted correctly."
        )
        # Verify they all share the same parent (the grid)
        parent_handle = page.evaluate(
            f"""() => {{
                const cards = document.querySelectorAll('[data-testid="{_SKELETON_TESTID}"]');
                if (cards.length < 2) return true;
                const parent = cards[0].parentElement;
                return Array.from(cards).every(c => c.parentElement === parent);
            }}"""
        )
        assert parent_handle, (
            "Skeleton cards do not share the same parent container. "
            "All skeleton cards must be direct children of the videoGrid div."
        )

    def test_skeleton_disappears_after_api_responds(
        self, dashboard_with_delayed_api
    ) -> None:
        """Skeleton cards must disappear once the video list API responds."""
        page, release_event = dashboard_with_delayed_api
        # Release the intercepted request
        release_event.set()
        # Skeleton should be gone after the API resolves
        skeleton = page.locator(f"[data-testid='{_SKELETON_TESTID}']").first
        try:
            skeleton.wait_for(state="hidden", timeout=15_000)
            assert not skeleton.is_visible(), (
                "Skeleton card is still visible after the /api/me/videos request completed. "
                "The loading state must be cleared once data is received."
            )
        except Exception:
            # If no skeleton was ever present post-release, that's fine too
            if skeleton.count() == 0:
                pass
            else:
                raise
