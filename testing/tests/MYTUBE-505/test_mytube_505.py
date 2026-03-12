"""
MYTUBE-505: SiteFooter redesign — background and copyright typography applied

Objective
---------
Verify that the SiteFooter matches the redesigned visual specifications.

Steps
-----
1. Scroll to the bottom of the page to view the SiteFooter.
2. Inspect the footer background and the copyright text on the left.

Expected Result
---------------
* The footer background is var(--bg-card) with a top border of
  1px solid var(--border-light).
* The copyright text uses var(--text-subtle) and has a font-size of 13px.

Architecture & Testing Strategy
--------------------------------
**Layer A — CSS token validation** (always runs, no browser required):
    Reads web/src/app/globals.css and verifies that --bg-card, --border-light,
    and --text-subtle are defined in the :root block.

**Layer B — Source code structural analysis** (no browser required):
    Parses web/src/components/SiteFooter.tsx and verifies the component uses
    the correct CSS variables inline styles and font-size of 13px.

**Layer C — Live browser verification** (runs when APP_URL is available):
    Navigates to the deployed app, scrolls to footer, and reads computed
    CSS property values from the browser to confirm they match the design
    tokens.

Run from repo root:
    pytest testing/tests/MYTUBE-505/test_mytube_505.py -v
"""
from __future__ import annotations

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.pages.css_globals_page.css_globals_page import CSSGlobalsPage

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_GLOBALS_CSS = os.path.join(_REPO_ROOT, "web", "src", "app", "globals.css")
_SITE_FOOTER_TSX = os.path.join(_REPO_ROOT, "web", "src", "components", "SiteFooter.tsx")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_css = CSSGlobalsPage()


def _read_source(path: str) -> str:
    """Read a source file, failing with a clear message if not found."""
    if not os.path.isfile(path):
        pytest.fail(f"Source file not found: {path}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _hex_to_rgb(hex_color: str) -> str:
    """Convert a 6-digit hex color to CSS rgb() notation."""
    hex_color = hex_color.strip().lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgb({r}, {g}, {b})"


def _should_use_live_mode() -> bool:
    """Return True when a deployed application URL is available."""
    env_url = os.getenv("APP_URL", os.getenv("WEB_BASE_URL", ""))
    return bool(env_url and env_url.lower() not in ("false", "0", ""))


# ---------------------------------------------------------------------------
# Layer A — CSS Token Validation
# ---------------------------------------------------------------------------


class TestCSSTokensDefined:
    """Verify design tokens required by the footer are defined in globals.css."""

    def test_bg_card_token_defined(self) -> None:
        """--bg-card must be defined in the :root block of globals.css."""
        value = _css.get_light_token("--bg-card")
        assert value, "--bg-card is empty in globals.css :root block"

    def test_border_light_token_defined(self) -> None:
        """--border-light must be defined in the :root block of globals.css."""
        value = _css.get_light_token("--border-light")
        assert value, "--border-light is empty in globals.css :root block"

    def test_text_subtle_token_defined(self) -> None:
        """--text-subtle must be defined in the :root block of globals.css."""
        value = _css.get_light_token("--text-subtle")
        assert value, "--text-subtle is empty in globals.css :root block"


# ---------------------------------------------------------------------------
# Layer B — Source Code Structural Analysis
# ---------------------------------------------------------------------------


class TestSiteFooterSource:
    """Verify SiteFooter.tsx applies the redesigned visual specifications."""

    def test_footer_background_uses_bg_card(self) -> None:
        """Footer element must use var(--bg-card) as its background."""
        source = _read_source(_SITE_FOOTER_TSX)
        assert 'var(--bg-card)' in source, (
            "SiteFooter.tsx does not use var(--bg-card) for the footer background. "
            f"Source: {_SITE_FOOTER_TSX}"
        )

    def test_footer_border_top_uses_border_light(self) -> None:
        """Footer must have a top border using var(--border-light)."""
        source = _read_source(_SITE_FOOTER_TSX)
        # The expected pattern: "1px solid var(--border-light)"
        assert 'var(--border-light)' in source, (
            "SiteFooter.tsx does not use var(--border-light) for the top border. "
            f"Source: {_SITE_FOOTER_TSX}"
        )
        # Verify it's a 1px solid border pattern
        assert re.search(r"1px\s+solid\s+var\(--border-light\)", source), (
            "SiteFooter.tsx border-top is not '1px solid var(--border-light)'. "
            f"Found source: {_SITE_FOOTER_TSX}"
        )

    def test_copyright_text_uses_text_subtle(self) -> None:
        """Copyright paragraph must use var(--text-subtle) for its color."""
        source = _read_source(_SITE_FOOTER_TSX)
        assert 'var(--text-subtle)' in source, (
            "SiteFooter.tsx does not use var(--text-subtle) for copyright text color. "
            f"Source: {_SITE_FOOTER_TSX}"
        )

    def test_copyright_font_size_is_13px(self) -> None:
        """Copyright paragraph must have a font-size of 13px."""
        source = _read_source(_SITE_FOOTER_TSX)
        # Accept both inline style (font-size: 13px / fontSize: '13px') and Tailwind text-[13px]
        has_13px = (
            "13px" in source or
            re.search(r"text-\[13px\]", source) is not None or
            re.search(r"fontSize.*13", source) is not None
        )
        assert has_13px, (
            "SiteFooter.tsx copyright paragraph does not have a font-size of 13px. "
            "Expected either style={{ fontSize: '13px' }}, text-[13px], or similar. "
            f"Source: {_SITE_FOOTER_TSX}"
        )

    def test_footer_inline_styles_structure(self) -> None:
        """Footer element must set background and borderTop inline styles."""
        source = _read_source(_SITE_FOOTER_TSX)
        # Check that a <footer> element has a style prop
        assert re.search(r"<footer[^>]*style=", source, re.DOTALL), (
            "SiteFooter.tsx <footer> element does not have inline style prop. "
            f"Source: {_SITE_FOOTER_TSX}"
        )
        # Both background and borderTop (or border-top) must be present
        has_background = "background" in source
        has_border_top = "borderTop" in source or "border-top" in source
        assert has_background, (
            "SiteFooter.tsx does not set background on the footer element."
        )
        assert has_border_top, (
            "SiteFooter.tsx does not set borderTop (border-top) on the footer element."
        )


# ---------------------------------------------------------------------------
# Layer C — Live Browser Verification
# ---------------------------------------------------------------------------


class TestSiteFooterLive:
    """Navigate to the deployed app and verify computed styles of the footer."""

    @pytest.mark.skipif(
        not _should_use_live_mode(),
        reason="APP_URL / WEB_BASE_URL not set — skipping live browser test",
    )
    def test_footer_computed_background_matches_bg_card(self, page) -> None:
        """Footer background-color must match the resolved --bg-card token."""
        from testing.core.config.web_config import WebConfig

        config = WebConfig()
        page.goto(config.home_url(), wait_until="domcontentloaded")

        # Scroll to footer
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_selector("footer", state="visible", timeout=10_000)

        # Read computed background color of the footer
        bg_color = page.evaluate(
            "() => getComputedStyle(document.querySelector('footer')).backgroundColor"
        )
        # Read the CSS variable resolved value
        bg_card_hex = _css.get_light_token("--bg-card")  # e.g. "#f3f4f8"
        expected_rgb = _hex_to_rgb(bg_card_hex)

        assert bg_color == expected_rgb, (
            f"Footer background-color: expected {expected_rgb!r} (from --bg-card={bg_card_hex!r}), "
            f"got {bg_color!r}"
        )

    @pytest.mark.skipif(
        not _should_use_live_mode(),
        reason="APP_URL / WEB_BASE_URL not set — skipping live browser test",
    )
    def test_footer_computed_border_top_matches_border_light(self, page) -> None:
        """Footer border-top-color must match the resolved --border-light token."""
        from testing.core.config.web_config import WebConfig

        config = WebConfig()
        # Re-use already-loaded page or navigate
        if "footer" not in page.url:
            page.goto(config.home_url(), wait_until="domcontentloaded")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_selector("footer", state="visible", timeout=10_000)

        border_color = page.evaluate(
            "() => getComputedStyle(document.querySelector('footer')).borderTopColor"
        )
        border_light_hex = _css.get_light_token("--border-light")  # e.g. "#dcdcdc"
        expected_rgb = _hex_to_rgb(border_light_hex)

        assert border_color == expected_rgb, (
            f"Footer border-top-color: expected {expected_rgb!r} (from --border-light={border_light_hex!r}), "
            f"got {border_color!r}"
        )

    @pytest.mark.skipif(
        not _should_use_live_mode(),
        reason="APP_URL / WEB_BASE_URL not set — skipping live browser test",
    )
    def test_copyright_computed_color_matches_text_subtle(self, page) -> None:
        """Copyright text color must match the resolved --text-subtle token."""
        from testing.core.config.web_config import WebConfig

        config = WebConfig()
        if "footer" not in page.url:
            page.goto(config.home_url(), wait_until="domcontentloaded")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_selector("footer p", state="visible", timeout=10_000)

        # The copyright <p> is the first <p> inside <footer>
        color = page.evaluate(
            "() => getComputedStyle(document.querySelector('footer p')).color"
        )
        text_subtle_hex = _css.get_light_token("--text-subtle")  # e.g. "#6e6e78"
        expected_rgb = _hex_to_rgb(text_subtle_hex)

        assert color == expected_rgb, (
            f"Copyright text color: expected {expected_rgb!r} (from --text-subtle={text_subtle_hex!r}), "
            f"got {color!r}"
        )

    @pytest.mark.skipif(
        not _should_use_live_mode(),
        reason="APP_URL / WEB_BASE_URL not set — skipping live browser test",
    )
    def test_copyright_computed_font_size_is_13px(self, page) -> None:
        """Copyright text font-size must be 13px (computed)."""
        from testing.core.config.web_config import WebConfig

        config = WebConfig()
        if "footer" not in page.url:
            page.goto(config.home_url(), wait_until="domcontentloaded")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_selector("footer p", state="visible", timeout=10_000)

        font_size = page.evaluate(
            "() => getComputedStyle(document.querySelector('footer p')).fontSize"
        )

        assert font_size == "13px", (
            f"Copyright font-size: expected '13px', got {font_size!r}"
        )
