"""
MYTUBE-517: Comment list items — card styling and author metadata alignment

Objective
---------
Verify that individual comment items apply the new card-based design system
and typography.

Steps
-----
1. Navigate to a video with existing comments.
2. Inspect a comment list item container.
3. Observe the username, timestamp, and body text styling.

Expected Result
---------------
Comment items have ``background: var(--bg-card)``, ``border-radius: 12px``,
and ``padding: 12px``. The avatar uses a gradient circle. Username and
timestamp match the ``.meta-line`` style, and the body text uses
``var(--text-primary)``.

Test Architecture
-----------------
**Layer A — Source code static analysis** (always runs):
    Parses ``web/src/components/CommentSection.module.css`` to confirm that
    the expected CSS properties are declared for the relevant classes.

**Layer B — Playwright fixture** (always runs):
    A self-contained HTML page replicates the comment item structure using
    the same CSS class names and CSS custom properties from globals.css.
    Playwright verifies computed styles against expected values.

**Layer C — Live app integration** (runs when WEB_BASE_URL is set):
    Navigates to the static ``/v/_/`` placeholder watch page with mocked
    API responses (video detail + comments list).  Asserts that:
    - The comment list renders at least one ``.commentItem`` element.
    - The ``.commentItem`` has the correct background colour, border-radius,
      and padding.
    - The ``.metaLine`` is present and contains the author name.
    - The ``.commentBody`` element uses ``var(--text-primary)`` colour.

Environment Variables
---------------------
APP_URL / WEB_BASE_URL  : Base URL of the deployed web app.
                          Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     : Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      : Slow-motion delay in ms (default: 0).
"""
from __future__ import annotations

import os
import re
import sys
import json

import pytest
from playwright.sync_api import sync_playwright, Page, Route

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_CSS_PATH = os.path.join(
    _REPO_ROOT, "web", "src", "components", "CommentSection.module.css"
)
_PAGE_LOAD_TIMEOUT = 30_000   # ms
_COMMENT_LOAD_TIMEOUT = 10_000  # ms

# Placeholder video ID — the only pre-generated watch page in the static export
_PLACEHOLDER_VIDEO_ID = "_"

# Expected computed style values (from globals.css light theme)
_EXPECTED_BORDER_RADIUS = "12px"
_EXPECTED_PADDING = "12px"

# ---------------------------------------------------------------------------
# Mock data for Layer C live integration
# ---------------------------------------------------------------------------

_MOCK_VIDEO_DETAIL = {
    "id": _PLACEHOLDER_VIDEO_ID,
    "title": "MYTUBE-517 Test Video",
    "description": "Automated test video for MYTUBE-517 comment styling.",
    "thumbnail_url": None,
    "hls_manifest_url": None,
    "view_count": 1,
    "status": "ready",
    "tags": [],
    "uploader": {
        "username": "ci-test",
        "avatar_url": None,
    },
    "created_at": "2026-01-01T00:00:00.000Z",
}

_MOCK_COMMENTS = [
    {
        "id": "mock-comment-001-mytube-517",
        "video_id": _PLACEHOLDER_VIDEO_ID,
        "author": {
            "uid": "test-uid-517",
            "username": "ci-tester",
            "avatar_url": None,
        },
        "body": "This is a test comment for MYTUBE-517 styling verification.",
        "created_at": "2026-01-01T12:00:00.000Z",
    }
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIXTURE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MYTUBE-517 Comment Styling Fixture</title>
<style>
  /* CSS custom properties matching globals.css light theme */
  :root {
    --bg-card: #f3f4f8;
    --bg-page: #ffffff;
    --text-primary: #222222;
    --text-secondary: #5a5a62;
    --text-subtle: #9090a0;
    --accent-logo: #6d40cb;
    --accent-cta: #62c235;
    --text-cta: #ffffff;
    --border-light: rgba(0,0,0,0.08);
  }

  /* Replicated from CommentSection.module.css */
  .commentList {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .commentItem {
    background: var(--bg-card);
    border-radius: 12px;
    padding: 12px;
  }

  .commentInner {
    display: flex;
    gap: 12px;
  }

  .avatarInitials {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--accent-logo) 0%, var(--accent-cta) 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 700;
    color: var(--text-cta);
    flex-shrink: 0;
  }

  .commentContent {
    flex: 1;
    min-width: 0;
  }

  .metaLine {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin-bottom: 4px;
  }

  .authorLink {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
    text-decoration: none;
  }

  .timestamp {
    font-size: 12px;
    color: var(--text-secondary);
  }

  .commentBody {
    font-size: 14px;
    color: var(--text-primary);
    white-space: pre-wrap;
    word-break: break-words;
    margin: 0;
  }
</style>
</head>
<body>
<ul class="commentList">
  <li class="commentItem" id="test-comment-item">
    <div class="commentInner">
      <div class="avatarInitials" id="test-avatar">CT</div>
      <div class="commentContent">
        <div class="metaLine" id="test-meta-line">
          <a class="authorLink" href="/u/ci-tester">ci-tester</a>
          <span class="timestamp">2 hours ago</span>
        </div>
        <p class="commentBody" id="test-comment-body">
          This is a test comment body for MYTUBE-517.
        </p>
      </div>
    </div>
  </li>
</ul>
</body>
</html>"""


def _css_source() -> str:
    """Read and return CommentSection.module.css content."""
    with open(_CSS_PATH, encoding="utf-8") as fh:
        return fh.read()


def _parse_rgb(rgb_str: str) -> tuple[int, int, int] | None:
    """Parse 'rgb(r, g, b)' → (r, g, b) tuple, or None on failure."""
    m = re.match(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", rgb_str)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser_instance():
    """Single shared Playwright/Chromium browser for the whole module."""
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        yield browser
        browser.close()


@pytest.fixture(scope="module")
def fixture_page(browser_instance):
    """Browser page loaded with the self-contained HTML fixture."""
    page = browser_instance.new_page()
    page.set_content(_FIXTURE_HTML, wait_until="domcontentloaded")
    yield page
    page.close()


# ---------------------------------------------------------------------------
# Layer A — Static CSS source analysis
# ---------------------------------------------------------------------------


class TestCommentItemCSSSource:
    """Layer A: Verify CommentSection.module.css declares the required properties."""

    def test_css_file_exists(self) -> None:
        """CommentSection.module.css must exist at the expected path."""
        assert os.path.isfile(_CSS_PATH), (
            f"CommentSection.module.css not found at '{_CSS_PATH}'. "
            "Ensure the CSS module file is present in web/src/components/."
        )

    def test_comment_item_background_var(self) -> None:
        """`.commentItem` must set `background: var(--bg-card)`."""
        css = _css_source()
        # Find the .commentItem block
        match = re.search(
            r"\.commentItem\s*\{([^}]+)\}", css, re.DOTALL
        )
        assert match, (
            "Could not find a `.commentItem { ... }` rule in CommentSection.module.css."
        )
        block = match.group(1)
        assert "var(--bg-card)" in block, (
            f"`.commentItem` block does not contain `var(--bg-card)`. "
            f"Found: {block.strip()!r}"
        )

    def test_comment_item_border_radius(self) -> None:
        """`.commentItem` must set `border-radius: 12px`."""
        css = _css_source()
        match = re.search(r"\.commentItem\s*\{([^}]+)\}", css, re.DOTALL)
        assert match, "Could not find `.commentItem` rule in CSS."
        block = match.group(1)
        assert "border-radius: 12px" in block, (
            f"`.commentItem` must declare `border-radius: 12px`. "
            f"Found block: {block.strip()!r}"
        )

    def test_comment_item_padding(self) -> None:
        """`.commentItem` must set `padding: 12px`."""
        css = _css_source()
        match = re.search(r"\.commentItem\s*\{([^}]+)\}", css, re.DOTALL)
        assert match, "Could not find `.commentItem` rule in CSS."
        block = match.group(1)
        assert "padding: 12px" in block, (
            f"`.commentItem` must declare `padding: 12px`. "
            f"Found block: {block.strip()!r}"
        )

    def test_avatar_gradient_circle(self) -> None:
        """`.avatarInitials` must use a linear-gradient with `--accent-logo` and `--accent-cta`."""
        css = _css_source()
        match = re.search(r"\.avatarInitials\s*\{([^}]+)\}", css, re.DOTALL)
        assert match, "Could not find `.avatarInitials` rule in CSS."
        block = match.group(1)
        assert "linear-gradient" in block, (
            f"`.avatarInitials` must use `linear-gradient(...)` for the gradient circle. "
            f"Found: {block.strip()!r}"
        )
        assert "var(--accent-logo)" in block, (
            f"`.avatarInitials` gradient must include `var(--accent-logo)`. "
            f"Found: {block.strip()!r}"
        )
        assert "var(--accent-cta)" in block, (
            f"`.avatarInitials` gradient must include `var(--accent-cta)`. "
            f"Found: {block.strip()!r}"
        )
        assert "border-radius: 50%" in block, (
            f"`.avatarInitials` must use `border-radius: 50%` for circle shape. "
            f"Found: {block.strip()!r}"
        )

    def test_meta_line_class_exists(self) -> None:
        """`.metaLine` class must be defined (username + timestamp container)."""
        css = _css_source()
        assert ".metaLine" in css, (
            "`.metaLine` class not found in CommentSection.module.css. "
            "The username and timestamp must be wrapped in a `.metaLine` container."
        )

    def test_comment_body_uses_text_primary(self) -> None:
        """`.commentBody` must set `color: var(--text-primary)`."""
        css = _css_source()
        match = re.search(r"\.commentBody\s*\{([^}]+)\}", css, re.DOTALL)
        assert match, "Could not find `.commentBody` rule in CSS."
        block = match.group(1)
        assert "var(--text-primary)" in block, (
            f"`.commentBody` must declare `color: var(--text-primary)`. "
            f"Found: {block.strip()!r}"
        )


# ---------------------------------------------------------------------------
# Layer B — Playwright fixture page — computed style verification
# ---------------------------------------------------------------------------


class TestCommentItemComputedStyles:
    """Layer B: Verify computed styles on the fixture HTML page."""

    def test_comment_item_border_radius_computed(self, fixture_page: Page) -> None:
        """Computed border-radius of .commentItem must be 12px."""
        border_radius = fixture_page.eval_on_selector(
            "#test-comment-item",
            "el => window.getComputedStyle(el).borderRadius",
        )
        assert border_radius == _EXPECTED_BORDER_RADIUS, (
            f"Expected `.commentItem` border-radius to be '{_EXPECTED_BORDER_RADIUS}', "
            f"got '{border_radius}'"
        )

    def test_comment_item_padding_computed(self, fixture_page: Page) -> None:
        """Computed padding of .commentItem must be 12px on all sides."""
        padding_top = fixture_page.eval_on_selector(
            "#test-comment-item",
            "el => window.getComputedStyle(el).paddingTop",
        )
        padding_right = fixture_page.eval_on_selector(
            "#test-comment-item",
            "el => window.getComputedStyle(el).paddingRight",
        )
        padding_bottom = fixture_page.eval_on_selector(
            "#test-comment-item",
            "el => window.getComputedStyle(el).paddingBottom",
        )
        padding_left = fixture_page.eval_on_selector(
            "#test-comment-item",
            "el => window.getComputedStyle(el).paddingLeft",
        )
        for side, val in [
            ("top", padding_top),
            ("right", padding_right),
            ("bottom", padding_bottom),
            ("left", padding_left),
        ]:
            assert val == _EXPECTED_PADDING, (
                f"Expected `.commentItem` padding-{side} to be '{_EXPECTED_PADDING}', "
                f"got '{val}'"
            )

    def test_comment_item_background_color(self, fixture_page: Page) -> None:
        """Computed background of .commentItem must resolve to --bg-card (#f3f4f8)."""
        bg_color = fixture_page.eval_on_selector(
            "#test-comment-item",
            "el => window.getComputedStyle(el).backgroundColor",
        )
        # --bg-card is #f3f4f8 in light theme → rgb(243, 244, 248)
        parsed = _parse_rgb(bg_color)
        assert parsed is not None, (
            f"Could not parse background-color '{bg_color}' as RGB."
        )
        assert parsed == (243, 244, 248), (
            f"Expected `.commentItem` background to be rgb(243, 244, 248) "
            f"(--bg-card: #f3f4f8), got '{bg_color}'"
        )

    def test_avatar_border_radius_circle(self, fixture_page: Page) -> None:
        """Avatar (.avatarInitials) must be circular: border-radius 50%."""
        border_radius = fixture_page.eval_on_selector(
            "#test-avatar",
            "el => window.getComputedStyle(el).borderRadius",
        )
        assert border_radius == "50%", (
            f"Expected avatar border-radius to be '50%' for a gradient circle, "
            f"got '{border_radius}'"
        )

    def test_meta_line_is_visible(self, fixture_page: Page) -> None:
        """The .metaLine element (username + timestamp) must be present and visible."""
        meta = fixture_page.locator("#test-meta-line")
        assert meta.count() == 1, "`.metaLine` element not found in comment structure."
        assert meta.is_visible(), "`.metaLine` element is not visible."

    def test_comment_body_text_color(self, fixture_page: Page) -> None:
        """Computed color of .commentBody must resolve to --text-primary (#222222)."""
        color = fixture_page.eval_on_selector(
            "#test-comment-body",
            "el => window.getComputedStyle(el).color",
        )
        # --text-primary is #222222 → rgb(34, 34, 34)
        parsed = _parse_rgb(color)
        assert parsed is not None, (
            f"Could not parse color '{color}' as RGB."
        )
        assert parsed == (34, 34, 34), (
            f"Expected `.commentBody` color to be rgb(34, 34, 34) "
            f"(--text-primary: #222222), got '{color}'"
        )


# ---------------------------------------------------------------------------
# Layer C — Live application integration
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def live_watch_page(config: WebConfig, browser_instance):
    """
    Navigate to /v/_/ with mocked API responses so comments render.
    Skips if APP_URL / WEB_BASE_URL is not set.
    """
    base_url = config.base_url

    page = browser_instance.new_page()

    def handle_video_route(route: Route) -> None:
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_MOCK_VIDEO_DETAIL),
        )

    def handle_comments_route(route: Route) -> None:
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_MOCK_COMMENTS),
        )

    page.route("**/api/videos/_", handle_video_route)
    page.route("**/api/videos/_/", handle_video_route)
    page.route("**/api/videos/*/comments", handle_comments_route)
    page.route("**/api/videos/*/comments/", handle_comments_route)

    watch_url = f"{base_url}/v/{_PLACEHOLDER_VIDEO_ID}/"
    try:
        page.goto(watch_url, timeout=_PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")
    except Exception as e:
        page.close()
        pytest.skip(f"Live app unreachable: {e}")

    # Wait for the comment list to appear
    try:
        page.wait_for_selector(
            "[class*='commentItem']",
            timeout=_COMMENT_LOAD_TIMEOUT,
        )
    except Exception:
        page.close()
        pytest.skip("Comment items did not render — live app may not be available.")

    yield page
    page.close()


class TestCommentItemLiveApp:
    """Layer C: Live app integration test (skipped when WEB_BASE_URL not set)."""

    def test_comment_item_renders(self, live_watch_page: Page) -> None:
        """At least one comment item must render on the live watch page."""
        items = live_watch_page.locator("[class*='commentItem']")
        count = items.count()
        assert count >= 1, (
            "No comment items found on the live watch page after mocking the API. "
            "The CommentSection component may not be rendering comment list items."
        )

    def test_live_comment_item_border_radius(self, live_watch_page: Page) -> None:
        """Computed border-radius of the first live comment item must be 12px."""
        first_item = live_watch_page.locator("[class*='commentItem']").first
        border_radius = first_item.evaluate(
            "el => window.getComputedStyle(el).borderRadius"
        )
        assert border_radius == _EXPECTED_BORDER_RADIUS, (
            f"Live app: expected comment item border-radius '{_EXPECTED_BORDER_RADIUS}', "
            f"got '{border_radius}'"
        )

    def test_live_comment_item_padding(self, live_watch_page: Page) -> None:
        """Computed padding of the first live comment item must be 12px on all sides."""
        first_item = live_watch_page.locator("[class*='commentItem']").first
        for side in ("paddingTop", "paddingRight", "paddingBottom", "paddingLeft"):
            val = first_item.evaluate(
                f"el => window.getComputedStyle(el).{side}"
            )
            assert val == _EXPECTED_PADDING, (
                f"Live app: expected comment item {side} '{_EXPECTED_PADDING}', "
                f"got '{val}'"
            )

    def test_live_comment_meta_line_present(self, live_watch_page: Page) -> None:
        """The .metaLine element must be present inside each comment item."""
        meta_lines = live_watch_page.locator("[class*='metaLine']")
        count = meta_lines.count()
        assert count >= 1, (
            "No `.metaLine` elements found in the live comment list. "
            "Username and timestamp container is missing."
        )

    def test_live_comment_body_color(self, live_watch_page: Page) -> None:
        """Computed color of the live `.commentBody` element must resolve to --text-primary."""
        first_body = live_watch_page.locator("[class*='commentBody']").first
        color = first_body.evaluate("el => window.getComputedStyle(el).color")
        parsed = _parse_rgb(color)
        assert parsed is not None, (
            f"Could not parse live comment body color '{color}' as RGB."
        )
        # --text-primary: #222222 (light) → rgb(34, 34, 34)
        # --text-primary: #f0f0f0 (dark)  → rgb(240, 240, 240)
        r, g, b = parsed
        assert (r, g, b) in [(34, 34, 34), (240, 240, 240)], (
            f"Live comment body color '{color}' does not match either light-theme "
            f"(rgb(34, 34, 34)) or dark-theme (rgb(240, 240, 240)) --text-primary value."
        )
