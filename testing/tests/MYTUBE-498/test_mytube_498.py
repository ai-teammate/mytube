"""
MYTUBE-498: SiteHeader branded logo — typography and SVG dimensions match redesign spec

Objective
---------
Verify that the SiteHeader logo section uses the correct SVG dimensions and font
styling for the wordmark and subtitle.

Steps
-----
1. Navigate to the homepage and locate the site logo in the header.
2. Inspect the LogoIcon SVG component — expects 44×44 px and color: var(--accent-logo).
3. Inspect the .logo-text block and its children:
   - Wordmark "MYTUBE": bold, 22 px, color: var(--accent-logo).
   - Subtitle "Personal Video Portal": 12 px, uppercase, color: var(--text-subtle).

Test Approach
-------------
Dual-mode:

1. **Static Mode** (primary, always runs) — Analyses ``web/src/components/SiteHeader.tsx``
   directly to verify the required Tailwind classes and inline-style tokens are present.
   This is fast, offline-safe, and covers the exact class names the spec requires.

2. **Live Mode** (secondary, Playwright) — When APP_URL / WEB_BASE_URL is set, launches
   a real browser, navigates to the homepage, and asserts computed CSS values for the
   LogoIcon, wordmark, and subtitle elements.

Run from repo root:
    pytest testing/tests/MYTUBE-498/test_mytube_498.py -v
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SITE_HEADER_TSX = _REPO_ROOT / "web" / "src" / "components" / "SiteHeader.tsx"

# ---------------------------------------------------------------------------
# Expected values (redesign specification)
# ---------------------------------------------------------------------------

# LogoIcon SVG: w-11 h-11 maps to 44 px each at the Tailwind default
_EXPECTED_LOGO_ICON_WIDTH_CLASS = "w-11"
_EXPECTED_LOGO_ICON_HEIGHT_CLASS = "h-11"
_EXPECTED_LOGO_ICON_COLOR = "var(--accent-logo)"

# Wordmark "MYTUBE"
_EXPECTED_WORDMARK_TEXT = "MYTUBE"
_EXPECTED_WORDMARK_FONT_SIZE_CLASS = "text-[22px]"
_EXPECTED_WORDMARK_FONT_WEIGHT_CLASS = "font-bold"
_EXPECTED_WORDMARK_COLOR = "var(--accent-logo)"

# Subtitle "Personal Video Portal"
_EXPECTED_SUBTITLE_TEXT = "Personal Video Portal"
_EXPECTED_SUBTITLE_FONT_SIZE_CLASS = "text-[12px]"
_EXPECTED_SUBTITLE_UPPERCASE_CLASS = "uppercase"
_EXPECTED_SUBTITLE_COLOR = "var(--text-subtle)"

_PAGE_LOAD_TIMEOUT = 30_000  # ms


# ---------------------------------------------------------------------------
# Mode helper
# ---------------------------------------------------------------------------


def _should_use_live_mode() -> bool:
    env_url = os.getenv("APP_URL", os.getenv("WEB_BASE_URL", ""))
    return bool(env_url and env_url.lower() not in ("false", "0", ""))


# ---------------------------------------------------------------------------
# Static analysis helpers
# ---------------------------------------------------------------------------


def _read_source() -> str:
    return _SITE_HEADER_TSX.read_text(encoding="utf-8")


def _assert_logo_icon_dimensions(source: str) -> None:
    """Assert that LogoIcon has Tailwind classes w-11 h-11 (= 44×44 px)."""
    # Match <LogoIcon ... className="...w-11...h-11..." or h-11 before w-11
    pattern = re.compile(
        r'<LogoIcon[^/]*className="[^"]*w-11[^"]*h-11[^"]*"',
        re.DOTALL,
    )
    pattern_rev = re.compile(
        r'<LogoIcon[^/]*className="[^"]*h-11[^"]*w-11[^"]*"',
        re.DOTALL,
    )
    assert pattern.search(source) or pattern_rev.search(source), (
        f"LogoIcon must have className containing 'w-11' and 'h-11' "
        f"(Tailwind sizing for 44×44 px). "
        f"File: {_SITE_HEADER_TSX}"
    )


def _assert_logo_icon_color(source: str) -> None:
    """Assert that LogoIcon has style={{ color: 'var(--accent-logo)' }}."""
    pattern = re.compile(
        r'<LogoIcon[^/]*style=\{\{[^}]*color:\s*"var\(--accent-logo\)"',
        re.DOTALL,
    )
    assert pattern.search(source), (
        f"LogoIcon must have inline style {{ color: 'var(--accent-logo)' }}. "
        f"File: {_SITE_HEADER_TSX}"
    )


def _assert_wordmark_font_size(source: str) -> None:
    """Assert that the MYTUBE wordmark span uses text-[22px]."""
    pattern = re.compile(
        r'className="[^"]*text-\[22px\][^"]*"[^<]*MYTUBE',
        re.DOTALL,
    )
    assert pattern.search(source), (
        f"Wordmark 'MYTUBE' span must have className containing 'text-[22px]'. "
        f"File: {_SITE_HEADER_TSX}"
    )


def _assert_wordmark_font_weight(source: str) -> None:
    """Assert that the MYTUBE wordmark span uses font-bold."""
    pattern = re.compile(
        r'className="[^"]*font-bold[^"]*"[^<]*MYTUBE',
        re.DOTALL,
    )
    assert pattern.search(source), (
        f"Wordmark 'MYTUBE' span must have className containing 'font-bold'. "
        f"File: {_SITE_HEADER_TSX}"
    )


def _assert_wordmark_color(source: str) -> None:
    """Assert that the MYTUBE wordmark span uses color: var(--accent-logo)."""
    # span with text-[22px] className, then style with accent-logo color, then MYTUBE text
    pattern = re.compile(
        r'className="[^"]*text-\[22px\][^"]*"[^>]*style=\{\{[^}]*color:\s*"var\(--accent-logo\)"[^}]*\}[^<]*MYTUBE',
        re.DOTALL,
    )
    assert pattern.search(source), (
        f"Wordmark 'MYTUBE' span must have inline style {{ color: 'var(--accent-logo)' }}. "
        f"File: {_SITE_HEADER_TSX}"
    )


def _assert_subtitle_font_size(source: str) -> None:
    """Assert that the subtitle span uses text-[12px]."""
    pattern = re.compile(
        r'className="[^"]*text-\[12px\][^"]*"[^<]*Personal Video Portal',
        re.DOTALL,
    )
    assert pattern.search(source), (
        f"Subtitle 'Personal Video Portal' span must have className containing 'text-[12px]'. "
        f"File: {_SITE_HEADER_TSX}"
    )


def _assert_subtitle_uppercase(source: str) -> None:
    """Assert that the subtitle span uses the uppercase Tailwind class."""
    pattern = re.compile(
        r'className="[^"]*uppercase[^"]*"[^<]*Personal Video Portal',
        re.DOTALL,
    )
    assert pattern.search(source), (
        f"Subtitle 'Personal Video Portal' span must have className containing 'uppercase'. "
        f"File: {_SITE_HEADER_TSX}"
    )


def _assert_subtitle_color(source: str) -> None:
    """Assert that the subtitle span uses color: var(--text-subtle)."""
    pattern = re.compile(
        r'className="[^"]*text-\[12px\][^"]*"[^>]*style=\{\{[^}]*color:\s*"var\(--text-subtle\)"[^}]*\}[^<]*Personal Video Portal',
        re.DOTALL,
    )
    assert pattern.search(source), (
        f"Subtitle 'Personal Video Portal' span must have inline style "
        f"{{ color: 'var(--text-subtle)' }}. File: {_SITE_HEADER_TSX}"
    )


# ---------------------------------------------------------------------------
# Live Playwright helpers
# ---------------------------------------------------------------------------


def _get_logo_styles(page) -> dict:
    """Return rendered size and color of the LogoIcon SVG in the header."""
    return page.evaluate(
        """() => {
            const header = document.querySelector('header');
            if (!header) return {};
            // The LogoIcon is the first <svg> inside the logo <a> link
            const svg = header.querySelector('a svg');
            if (!svg) return {};
            const rect = svg.getBoundingClientRect();
            const cs = window.getComputedStyle(svg);
            return {
                width:  Math.round(rect.width),
                height: Math.round(rect.height),
                color:  cs.color,
                inlineColor: svg.style.color,
            };
        }"""
    )


def _get_wordmark_styles(page) -> dict:
    """Return font-size, font-weight, and color of the 'MYTUBE' wordmark span."""
    return page.evaluate(
        """() => {
            const header = document.querySelector('header');
            if (!header) return {};
            // Find the span whose text content is 'MYTUBE'
            const spans = Array.from(header.querySelectorAll('span'));
            const span = spans.find(s => s.textContent.trim() === 'MYTUBE');
            if (!span) return {};
            const cs = window.getComputedStyle(span);
            return {
                fontSize:   cs.fontSize,
                fontWeight: cs.fontWeight,
                color:      cs.color,
                inlineColor: span.style.color,
            };
        }"""
    )


def _get_subtitle_styles(page) -> dict:
    """Return font-size, text-transform, and color of the subtitle span."""
    return page.evaluate(
        """() => {
            const header = document.querySelector('header');
            if (!header) return {};
            const spans = Array.from(header.querySelectorAll('span'));
            const span = spans.find(s => s.textContent.trim() === 'Personal Video Portal');
            if (!span) return {};
            const cs = window.getComputedStyle(span);
            return {
                fontSize:      cs.fontSize,
                textTransform: cs.textTransform,
                color:         cs.color,
                inlineColor:   span.style.color,
            };
        }"""
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser_page(config: WebConfig):
    """Playwright Page fixture: navigates to the homepage once for all live tests."""
    if not _should_use_live_mode():
        pytest.skip("Live mode skipped: APP_URL/WEB_BASE_URL not set")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(config.home_url(), timeout=_PAGE_LOAD_TIMEOUT, wait_until="networkidle")
        page.wait_for_selector("header", timeout=10_000)
        yield page
        browser.close()


# ---------------------------------------------------------------------------
# Tests — Static analysis (always run)
# ---------------------------------------------------------------------------


class TestLogoIconStaticSpec:
    """Static analysis: SiteHeader.tsx must declare correct classes for LogoIcon."""

    def test_logo_icon_has_44px_width_class(self) -> None:
        """Step 2: LogoIcon must use Tailwind class 'w-11' (44 px width)."""
        source = _read_source()
        _assert_logo_icon_dimensions(source)

    def test_logo_icon_has_accent_logo_color(self) -> None:
        """Step 2: LogoIcon must have style={{ color: 'var(--accent-logo)' }}."""
        source = _read_source()
        _assert_logo_icon_color(source)


class TestWordmarkStaticSpec:
    """Static analysis: SiteHeader.tsx must declare correct typography for 'MYTUBE'."""

    def test_wordmark_font_size_22px(self) -> None:
        """Step 3: 'MYTUBE' span must use 'text-[22px]'."""
        source = _read_source()
        _assert_wordmark_font_size(source)

    def test_wordmark_font_weight_bold(self) -> None:
        """Step 3: 'MYTUBE' span must include 'font-bold'."""
        source = _read_source()
        _assert_wordmark_font_weight(source)

    def test_wordmark_color_accent_logo(self) -> None:
        """Step 3: 'MYTUBE' span must have color: var(--accent-logo)."""
        source = _read_source()
        _assert_wordmark_color(source)


class TestSubtitleStaticSpec:
    """Static analysis: SiteHeader.tsx must declare correct typography for the subtitle."""

    def test_subtitle_font_size_12px(self) -> None:
        """Step 3: Subtitle span must use 'text-[12px]'."""
        source = _read_source()
        _assert_subtitle_font_size(source)

    def test_subtitle_is_uppercase(self) -> None:
        """Step 3: Subtitle span must include Tailwind 'uppercase' class."""
        source = _read_source()
        _assert_subtitle_uppercase(source)

    def test_subtitle_color_text_subtle(self) -> None:
        """Step 3: Subtitle span must have color: var(--text-subtle)."""
        source = _read_source()
        _assert_subtitle_color(source)


# ---------------------------------------------------------------------------
# Tests — Live Playwright (only when APP_URL is set)
# ---------------------------------------------------------------------------


class TestLogoIconLive:
    """Live tests: assert rendered dimensions and color of the LogoIcon SVG."""

    def test_logo_icon_width_44px(self, browser_page) -> None:
        """Step 2 (live): LogoIcon SVG must render at 44 px width."""
        styles = _get_logo_styles(browser_page)
        assert styles, (
            "Could not locate the LogoIcon <svg> inside <header> <a>. "
            f"Page URL: {browser_page.url}"
        )
        assert styles.get("width") == 44, (
            f"LogoIcon width: expected 44 px, got {styles.get('width')} px. "
            f"Page URL: {browser_page.url}"
        )

    def test_logo_icon_height_44px(self, browser_page) -> None:
        """Step 2 (live): LogoIcon SVG must render at 44 px height."""
        styles = _get_logo_styles(browser_page)
        assert styles.get("height") == 44, (
            f"LogoIcon height: expected 44 px, got {styles.get('height')} px. "
            f"Page URL: {browser_page.url}"
        )

    def test_logo_icon_inline_color_is_accent_logo(self, browser_page) -> None:
        """Step 2 (live): LogoIcon inline style color must be 'var(--accent-logo)'."""
        styles = _get_logo_styles(browser_page)
        assert styles.get("inlineColor") == "var(--accent-logo)", (
            f"LogoIcon inline color: expected 'var(--accent-logo)', "
            f"got '{styles.get('inlineColor')}'. Page URL: {browser_page.url}"
        )


class TestWordmarkLive:
    """Live tests: assert rendered font properties of the 'MYTUBE' wordmark."""

    def test_wordmark_font_size_22px(self, browser_page) -> None:
        """Step 3 (live): Wordmark must render at 22 px font-size."""
        styles = _get_wordmark_styles(browser_page)
        assert styles, (
            "Could not locate the 'MYTUBE' span inside <header>. "
            f"Page URL: {browser_page.url}"
        )
        assert styles.get("fontSize") == "22px", (
            f"Wordmark font-size: expected '22px', got '{styles.get('fontSize')}'. "
            f"Page URL: {browser_page.url}"
        )

    def test_wordmark_is_bold(self, browser_page) -> None:
        """Step 3 (live): Wordmark must have font-weight 700 (bold)."""
        styles = _get_wordmark_styles(browser_page)
        assert styles.get("fontWeight") in ("700", "bold"), (
            f"Wordmark font-weight: expected '700' or 'bold', "
            f"got '{styles.get('fontWeight')}'. Page URL: {browser_page.url}"
        )


class TestSubtitleLive:
    """Live tests: assert rendered font properties of the subtitle."""

    def test_subtitle_font_size_12px(self, browser_page) -> None:
        """Step 3 (live): Subtitle must render at 12 px font-size."""
        styles = _get_subtitle_styles(browser_page)
        assert styles, (
            "Could not locate the 'Personal Video Portal' span inside <header>. "
            f"Page URL: {browser_page.url}"
        )
        assert styles.get("fontSize") == "12px", (
            f"Subtitle font-size: expected '12px', got '{styles.get('fontSize')}'. "
            f"Page URL: {browser_page.url}"
        )

    def test_subtitle_is_uppercase(self, browser_page) -> None:
        """Step 3 (live): Subtitle must have text-transform: uppercase."""
        styles = _get_subtitle_styles(browser_page)
        assert styles.get("textTransform") == "uppercase", (
            f"Subtitle text-transform: expected 'uppercase', "
            f"got '{styles.get('textTransform')}'. Page URL: {browser_page.url}"
        )

    def test_subtitle_inline_color_is_text_subtle(self, browser_page) -> None:
        """Step 3 (live): Subtitle inline style color must be 'var(--text-subtle)'."""
        styles = _get_subtitle_styles(browser_page)
        assert styles.get("inlineColor") == "var(--text-subtle)", (
            f"Subtitle inline color: expected 'var(--text-subtle)', "
            f"got '{styles.get('inlineColor')}'. Page URL: {browser_page.url}"
        )
