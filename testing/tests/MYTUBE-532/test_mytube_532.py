"""
MYTUBE-532: Hero stat cards rendering — three cards displayed with correct text and design tokens.

Objective
---------
Verify that the three stat hero-cards are correctly rendered with specified text and
visual properties.

Steps
-----
1. Navigate to the homepage.
2. Locate the elements with class .hero-card (CSS module: heroCard).
3. Verify the presence of three cards with labels: "100% Private", "HLS Quality", and
   "Free Forever".
4. Inspect CSS for background: var(--bg-card), border-radius: 12px, and
   box-shadow: var(--shadow-card).

Expected Result
---------------
All three cards are present with correct text labels and styling matching the design tokens.

Architecture
------------
- Dual-mode: live Playwright tests against the deployed app + static CSS module analysis.
- Uses WebConfig from testing/core/config/web_config.py.
- No raw Playwright APIs in test body — helpers encapsulate selector logic.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms

# CSS module selector: heroCard class (mangled by CSS Modules in Next.js)
_HERO_CARD_SELECTOR = "[class*='heroCard']"
_CARD_LABEL_SELECTOR = "[class*='cardLabel']"

# Expected card labels (in order)
_EXPECTED_LABELS = ["100% Private", "HLS Quality", "Free Forever"]
_EXPECTED_CARD_COUNT = 3

# Expected CSS values
_EXPECTED_BORDER_RADIUS = "12px"
_CSS_BG_TOKEN = "--bg-card"
_CSS_SHADOW_TOKEN = "--shadow-card"

# Repo root for static analysis
_REPO_ROOT = Path(__file__).resolve().parents[3]
_HERO_CSS = _REPO_ROOT / "web" / "src" / "components" / "HeroSection.module.css"
_HERO_TSX = _REPO_ROOT / "web" / "src" / "components" / "HeroSection.tsx"


# ---------------------------------------------------------------------------
# Mode helper
# ---------------------------------------------------------------------------


def _should_use_live_mode() -> bool:
    env_url = os.getenv("APP_URL", os.getenv("WEB_BASE_URL", ""))
    return bool(env_url and env_url.lower() not in ("false", "0", ""))


# ---------------------------------------------------------------------------
# Playwright helpers
# ---------------------------------------------------------------------------


def _computed_style(page: Page, selector: str, prop: str) -> str:
    """Return the computed CSS property value for the first matching element."""
    return page.eval_on_selector(
        selector,
        f"el => window.getComputedStyle(el).{prop}",
    )


def _css_var_value(page: Page, var_name: str) -> str:
    """Return the resolved value of a CSS custom property from :root."""
    return page.evaluate(
        f"() => window.getComputedStyle(document.documentElement)"
        f".getPropertyValue('{var_name}').trim()"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser_page(config: WebConfig):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(f"{config.base_url}/", timeout=_PAGE_LOAD_TIMEOUT, wait_until="networkidle")
        yield page
        browser.close()


# ---------------------------------------------------------------------------
# Live-mode tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _should_use_live_mode(),
    reason="Live mode requires APP_URL / WEB_BASE_URL",
)
class TestHeroStatCardsLive:
    """MYTUBE-532 — Live Playwright tests against the deployed application."""

    def test_three_hero_cards_present(self, browser_page: Page) -> None:
        """Exactly three .heroCard elements must be rendered on the homepage."""
        count = browser_page.locator(_HERO_CARD_SELECTOR).count()
        assert count == _EXPECTED_CARD_COUNT, (
            f"Expected exactly {_EXPECTED_CARD_COUNT} hero-card elements "
            f"(selector: '{_HERO_CARD_SELECTOR}'), found {count}. "
            f"URL: {browser_page.url}"
        )

    def test_card_label_100_private(self, browser_page: Page) -> None:
        """First card label must be '100% Private'."""
        self._assert_label_exists(browser_page, "100% Private")

    def test_card_label_hls_quality(self, browser_page: Page) -> None:
        """Second card label must be 'HLS Quality'."""
        self._assert_label_exists(browser_page, "HLS Quality")

    def test_card_label_free_forever(self, browser_page: Page) -> None:
        """Third card label must be 'Free Forever'."""
        self._assert_label_exists(browser_page, "Free Forever")

    def test_card_border_radius_12px(self, browser_page: Page) -> None:
        """Each hero-card must have border-radius: 12px."""
        cards = browser_page.locator(_HERO_CARD_SELECTOR)
        count = cards.count()
        assert count > 0, f"No hero-card elements found (selector: '{_HERO_CARD_SELECTOR}')."
        for i in range(count):
            card = cards.nth(i)
            border_radius = card.evaluate(
                "el => window.getComputedStyle(el).borderRadius"
            )
            assert border_radius == _EXPECTED_BORDER_RADIUS, (
                f"Hero card #{i} border-radius: expected '{_EXPECTED_BORDER_RADIUS}', "
                f"got '{border_radius}'."
            )

    def test_card_background_matches_bg_card_token(self, browser_page: Page) -> None:
        """Each hero-card background must resolve to the same color as var(--bg-card).

        Browsers normalise the resolved CSS variable value to rgb() format when
        read back via getComputedStyle, so we use a temp element to let the
        browser canonicalise the token value before comparing.
        """
        cards = browser_page.locator(_HERO_CARD_SELECTOR)
        count = cards.count()
        assert count > 0, f"No hero-card elements found (selector: '{_HERO_CARD_SELECTOR}')."
        for i in range(count):
            match = cards.nth(i).evaluate(
                f"""(el) => {{
                    const cs = window.getComputedStyle(el);
                    const varValue = window.getComputedStyle(document.documentElement)
                        .getPropertyValue('{_CSS_BG_TOKEN}').trim();
                    // Resolve the token through a temporary element so both sides are
                    // in the same browser-normalised format (e.g. rgb()).
                    const tmp = document.createElement('div');
                    tmp.style.backgroundColor = varValue;
                    document.body.appendChild(tmp);
                    const resolved = window.getComputedStyle(tmp).backgroundColor;
                    document.body.removeChild(tmp);
                    return {{
                        matches: cs.backgroundColor === resolved,
                        actual: cs.backgroundColor,
                        expected: resolved,
                        rawToken: varValue
                    }};
                }}"""
            )
            assert match["matches"], (
                f"Hero card #{i} backgroundColor: expected '{match['expected']}' "
                f"(var({_CSS_BG_TOKEN}) = '{match['rawToken']}'), "
                f"got '{match['actual']}'."
            )

    def test_card_box_shadow_matches_shadow_card_token(self, browser_page: Page) -> None:
        """Each hero-card box-shadow must resolve to the same value as var(--shadow-card).

        Browsers normalise box-shadow values when reading via getComputedStyle
        (e.g. '#00000014' becomes 'rgba(0, 0, 0, 0.08)' and offsets get 'px'
        suffixes), so we resolve the token through a temp element first.
        """
        cards = browser_page.locator(_HERO_CARD_SELECTOR)
        count = cards.count()
        assert count > 0, f"No hero-card elements found (selector: '{_HERO_CARD_SELECTOR}')."
        for i in range(count):
            match = cards.nth(i).evaluate(
                f"""(el) => {{
                    const cs = window.getComputedStyle(el);
                    const varValue = window.getComputedStyle(document.documentElement)
                        .getPropertyValue('{_CSS_SHADOW_TOKEN}').trim();
                    if (!varValue) {{
                        return {{
                            matches: cs.boxShadow === 'none' || cs.boxShadow === '',
                            actual: cs.boxShadow, expected: 'none', rawToken: varValue
                        }};
                    }}
                    const tmp = document.createElement('div');
                    tmp.style.boxShadow = varValue;
                    document.body.appendChild(tmp);
                    const resolved = window.getComputedStyle(tmp).boxShadow;
                    document.body.removeChild(tmp);
                    return {{
                        matches: cs.boxShadow === resolved,
                        actual: cs.boxShadow,
                        expected: resolved,
                        rawToken: varValue
                    }};
                }}"""
            )
            assert match["matches"], (
                f"Hero card #{i} boxShadow: expected '{match['expected']}' "
                f"(var({_CSS_SHADOW_TOKEN}) = '{match['rawToken']}'), "
                f"got '{match['actual']}'."
            )

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _assert_label_exists(self, page: Page, label: str) -> None:
        """Assert that a card label with the given text is present."""
        # Try CSS-module-aware selector first
        locator = page.locator(f"{_HERO_CARD_SELECTOR} {_CARD_LABEL_SELECTOR}")
        count = locator.count()
        if count == 0:
            # Fallback: search all spans inside hero cards
            locator = page.locator(f"{_HERO_CARD_SELECTOR} span")

        labels = [locator.nth(i).inner_text().strip() for i in range(locator.count())]
        assert label in labels, (
            f"Expected hero-card label '{label}' not found. "
            f"Found labels: {labels}. URL: {page.url}"
        )


# ---------------------------------------------------------------------------
# Static-analysis tests (always run)
# ---------------------------------------------------------------------------


class TestHeroStatCardsStatic:
    """MYTUBE-532 — Static source analysis of HeroSection.module.css and HeroSection.tsx."""

    @pytest.fixture(scope="class")
    def css_source(self) -> str:
        assert _HERO_CSS.exists(), (
            f"HeroSection.module.css not found at {_HERO_CSS}."
        )
        return _HERO_CSS.read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def tsx_source(self) -> str:
        assert _HERO_TSX.exists(), (
            f"HeroSection.tsx not found at {_HERO_TSX}."
        )
        return _HERO_TSX.read_text(encoding="utf-8")

    def test_heroCard_class_has_bg_card_token(self, css_source: str) -> None:
        """.heroCard CSS rule must use background: var(--bg-card)."""
        assert "var(--bg-card)" in css_source, (
            "Expected 'var(--bg-card)' not found in HeroSection.module.css. "
            "The .heroCard rule must use the --bg-card design token for its background."
        )

    def test_heroCard_class_has_border_radius_12px(self, css_source: str) -> None:
        """.heroCard CSS rule must have border-radius: 12px."""
        assert "border-radius: 12px" in css_source, (
            "Expected 'border-radius: 12px' not found in HeroSection.module.css. "
            "The .heroCard rule must specify border-radius: 12px."
        )

    def test_heroCard_class_has_shadow_card_token(self, css_source: str) -> None:
        """.heroCard CSS rule must use box-shadow: var(--shadow-card)."""
        assert "var(--shadow-card)" in css_source, (
            "Expected 'var(--shadow-card)' not found in HeroSection.module.css. "
            "The .heroCard rule must use the --shadow-card design token for box-shadow."
        )

    def test_tsx_three_stat_cards_defined(self, tsx_source: str) -> None:
        """HeroSection.tsx must define exactly three STAT_CARDS entries."""
        # Extract the STAT_CARDS array block to avoid matching the TypeScript interface
        stat_cards_match = re.search(
            r'STAT_CARDS[^=]*=\s*\[(.+?)\]\s*;',
            tsx_source,
            re.DOTALL,
        )
        assert stat_cards_match, (
            "Could not find STAT_CARDS array in HeroSection.tsx."
        )
        entries = re.findall(r'\{\s*icon:', stat_cards_match.group(1))
        assert len(entries) == 3, (
            f"Expected 3 stat card entries in STAT_CARDS[], found {len(entries)}. "
            f"HeroSection.tsx must define three cards: '100% Private', 'HLS Quality', 'Free Forever'."
        )

    def test_tsx_label_100_private(self, tsx_source: str) -> None:
        """HeroSection.tsx must include label '100% Private'."""
        assert "100% Private" in tsx_source, (
            "Expected label '100% Private' not found in HeroSection.tsx STAT_CARDS."
        )

    def test_tsx_label_hls_quality(self, tsx_source: str) -> None:
        """HeroSection.tsx must include label 'HLS Quality'."""
        assert "HLS Quality" in tsx_source, (
            "Expected label 'HLS Quality' not found in HeroSection.tsx STAT_CARDS."
        )

    def test_tsx_label_free_forever(self, tsx_source: str) -> None:
        """HeroSection.tsx must include label 'Free Forever'."""
        assert "Free Forever" in tsx_source, (
            "Expected label 'Free Forever' not found in HeroSection.tsx STAT_CARDS."
        )
