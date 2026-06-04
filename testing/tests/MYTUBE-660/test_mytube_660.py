"""
MYTUBE-660: SiteHeader positioning text — component displays 'corp video portal'.

Objective
---------
Verify that the SiteHeader component reflects the new corporate positioning
text so that the header renders "MYTUBE" and the "corp video portal" subtitle.

Steps
-----
1. Navigate to the homepage.
2. Inspect the text content within the SiteHeader component (logo subtitle /
   wordmark area).

Expected Result
---------------
The text "MYTUBE: corp video portal" is rendered within the header — i.e. the
MYTUBE wordmark and the "corp video portal" subtitle are both present.

Test approach
-------------
Dual-mode:

  Part A — Static analysis (always runs):
    Reads SiteHeader.tsx and asserts:
      - The string "MYTUBE" is present as the primary wordmark.
      - The string "Corp Video Portal" (the subtitle, rendered uppercase via
        CSS) is present in the source.
      - Both elements are nested inside the branded logo <Link>.

  Part B — Live Playwright UI test (runs when the app is reachable):
    1. Navigates to the homepage.
    2. Locates the <header> element.
    3. Asserts the MYTUBE wordmark span is visible inside the header.
    4. Asserts the subtitle span containing "corp video portal" text is
       visible inside the header (case-insensitive match because the CSS
       'uppercase' class transforms the text visually).

Environment variables
---------------------
APP_URL / WEB_BASE_URL      Base URL of the deployed web app.
                            Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS         Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO          Slow-motion delay in ms (default: 0).

Architecture
------------
- WebConfig centralises env var access (testing/core/config/web_config.py).
- HeaderPage page object handles navigation and header interactions.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, Browser

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.header_page.header_page import HeaderPage

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SITE_HEADER_SRC = _REPO_ROOT / "web" / "src" / "components" / "SiteHeader.tsx"

# ---------------------------------------------------------------------------
# Expected values
# ---------------------------------------------------------------------------

_EXPECTED_WORDMARK = "MYTUBE"
_EXPECTED_SUBTITLE = "Corp Video Portal"
# CSS 'uppercase' class visually transforms the subtitle; the DOM text node
# value is "Corp Video Portal" but it renders as "CORP VIDEO PORTAL".
_EXPECTED_SUBTITLE_LOWER = "corp video portal"

_PAGE_LOAD_TIMEOUT = 30_000  # ms


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    """Launch Chromium for the test module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def home_page(web_config: WebConfig, browser: Browser) -> HeaderPage:
    """Navigate to the homepage and return a HeaderPage instance."""
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    header = HeaderPage(page)
    try:
        header.navigate_to(web_config.base_url + "/")
    except Exception as exc:
        context.close()
        pytest.skip(
            f"Could not reach {web_config.base_url}/ — skipping live UI tests. "
            f"Error: {exc}"
        )

    yield header
    context.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _site_header_source() -> str:
    return _SITE_HEADER_SRC.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Part A — Static analysis tests (always run)
# ---------------------------------------------------------------------------


class TestSiteHeaderPositioningTextStaticAnalysis:
    """Verify that SiteHeader.tsx contains the required branding text."""

    def test_source_file_exists(self) -> None:
        """The SiteHeader source file must be present in the repository."""
        assert _SITE_HEADER_SRC.is_file(), (
            f"SiteHeader source not found at {_SITE_HEADER_SRC}. "
            "Ensure the web app has been checked out correctly."
        )

    def test_mytube_wordmark_present(self) -> None:
        """The primary MYTUBE wordmark must appear in the SiteHeader source."""
        src = _site_header_source()
        assert _EXPECTED_WORDMARK in src, (
            f"Expected {_EXPECTED_WORDMARK!r} wordmark in SiteHeader source."
        )

    def test_corp_video_portal_subtitle_present(self) -> None:
        """The 'Corp Video Portal' subtitle text must appear in SiteHeader source."""
        src = _site_header_source()
        assert _EXPECTED_SUBTITLE in src, (
            f"Expected subtitle {_EXPECTED_SUBTITLE!r} in SiteHeader source. "
            "The component must render the 'corp video portal' positioning text."
        )

    def test_subtitle_inside_logo_link(self) -> None:
        """The subtitle span must be nested inside the branded logo Link block."""
        src = _site_header_source()
        logo_link_idx = src.find('aria-label="MYTUBE')
        subtitle_idx = src.find(_EXPECTED_SUBTITLE)
        assert logo_link_idx != -1, (
            "Expected the logo <Link> with an MYTUBE aria-label in SiteHeader source."
        )
        assert subtitle_idx != -1, (
            f"Expected {_EXPECTED_SUBTITLE!r} in SiteHeader source."
        )
        assert logo_link_idx < subtitle_idx, (
            "Expected the subtitle to appear after (inside) the logo Link element."
        )

    def test_uppercase_css_class_applied_to_subtitle(self) -> None:
        """The subtitle span must use the 'uppercase' Tailwind class so the text
        visually renders as 'CORP VIDEO PORTAL' matching corporate style."""
        src = _site_header_source()
        subtitle_idx = src.find(_EXPECTED_SUBTITLE)
        assert subtitle_idx != -1, (
            f"Expected {_EXPECTED_SUBTITLE!r} in SiteHeader source."
        )
        # Check surrounding context (within 200 chars before subtitle) for the class
        context_before = src[max(0, subtitle_idx - 200): subtitle_idx]
        assert "uppercase" in context_before, (
            "Expected Tailwind 'uppercase' class on the subtitle span — the "
            "CSS transform is what makes 'Corp Video Portal' render as all-caps."
        )


# ---------------------------------------------------------------------------
# Part B — Live Playwright UI tests
# ---------------------------------------------------------------------------


class TestSiteHeaderPositioningTextLiveUI:
    """Verify the SiteHeader renders the corporate positioning text on the live app."""

    def test_mytube_wordmark_visible_in_header(self, home_page: HeaderPage) -> None:
        """The MYTUBE wordmark must be visible inside the <header> element."""
        assert home_page.is_wordmark_visible(), (
            f"Expected {_EXPECTED_WORDMARK!r} wordmark to be visible inside the "
            "<header> element on the homepage."
        )

    def test_corp_video_portal_subtitle_visible_in_header(self, home_page: HeaderPage) -> None:
        """The 'corp video portal' subtitle must be visible inside the <header>."""
        # Playwright text matching is case-sensitive by default; the DOM text
        # node reads "Corp Video Portal" while CSS uppercases the visual output.
        assert home_page.is_subtitle_visible(_EXPECTED_SUBTITLE), (
            f"Expected subtitle {_EXPECTED_SUBTITLE!r} to be visible inside the "
            "<header> element. The CSS 'uppercase' class should render it as "
            f"'{_EXPECTED_SUBTITLE_LOWER.upper()}' visually."
        )

    def test_logo_link_accessible_label_includes_mytube(self, home_page: HeaderPage) -> None:
        """The logo link must have an accessible label that includes 'MYTUBE'."""
        label = home_page.get_logo_aria_label()
        assert "MYTUBE" in label, (
            f"Expected 'MYTUBE' in logo link aria-label, got: {label!r}"
        )

    def test_header_branding_text_combined(self, home_page: HeaderPage) -> None:
        """Human-style check: the combined header text contains both 'MYTUBE' and
        'corp video portal' (case-insensitive) — matching the ticket's expected
        result of 'MYTUBE: corp video portal'."""
        header_text = home_page.get_header_text()
        header_text_lower = header_text.lower()
        assert "mytube" in header_text_lower, (
            f"Expected 'mytube' in header text content. Got: {header_text!r}"
        )
        assert _EXPECTED_SUBTITLE_LOWER in header_text_lower, (
            f"Expected {_EXPECTED_SUBTITLE_LOWER!r} in header text content. "
            f"Got: {header_text!r}"
        )
