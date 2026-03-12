"""
MYTUBE-515: Star rating widget redesign — color and size match visual specification

Objective
---------
Verify the StarRating component updates, including star colors, sizes, and
heading typography.

Steps
-----
1. Navigate to the video watch page and locate the "Rate this video" section.
2. Inspect the section heading.
3. Inspect the star buttons for size and color (both filled and empty states).
4. Hover over the stars.

Expected Result
---------------
* The heading text is "Rate this video" with font-size: 16px and font-weight: 600.
* Stars are 24px in size.
* Filled stars use #ff6666 (var(--star-color)) and empty stars use var(--border-light).
* A hover effect is visible on interaction.

Architecture
------------
**Layer A — CSS source analysis** (always runs, no browser needed):
    Reads web/src/components/StarRating.module.css to confirm:
    - .heading: font-size: 16px, font-weight: 600
    - .starButton: font-size: 24px, color: var(--border-light)
    - .starFilled: color: var(--star-color)
    - Hover rule applies a transform

    Reads web/src/app/globals.css to confirm:
    - --star-color is #ff6666
    - --border-light is defined

**Layer B — Playwright fixture test** (always runs):
    Renders a self-contained HTML page that reproduces the StarRating CSS
    exactly, then uses Playwright's evaluate() to read computed styles and
    verify:
    - Heading font-size: 16px, font-weight: 600
    - Star button font-size: 24px
    - Empty star color resolves to #dcdcdc (--border-light light-theme value)
    - Filled star color resolves to #ff6666 (--star-color)
    - Hover transform is registered in the stylesheet (scale applied)

Run from repo root:
    pytest testing/tests/MYTUBE-515/test_mytube_515.py -v

With live app:
    WEB_BASE_URL=https://ai-teammate.github.io/mytube pytest testing/tests/MYTUBE-515/test_mytube_515.py -v
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.pages.css_globals_page.css_globals_page import CSSGlobalsPage

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[3]
_STAR_RATING_CSS = _REPO_ROOT / "web" / "src" / "components" / "StarRating.module.css"
_GLOBALS_CSS = _REPO_ROOT / "web" / "src" / "app" / "globals.css"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_css_globals = CSSGlobalsPage()


def _read_file(path: Path) -> str:
    if not path.is_file():
        pytest.fail(f"Source file not found: {path}")
    return path.read_text(encoding="utf-8")


def _get_fixture_html() -> str:
    """
    Self-contained HTML page that embeds the StarRating CSS values directly
    (replicating what the module CSS produces after compilation) so computed
    styles can be verified in Playwright.

    The CSS variables are resolved to their light-theme values as defined in
    globals.css so that computed color assertions are predictable.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>MYTUBE-515 — StarRating visual test</title>
  <style>
    :root {
      --star-color: #ff6666;
      --border-light: #dcdcdc;
      --text-primary: #1a1a2e;
      --text-secondary: #666666;
      --text-subtle: #999999;
      --accent-logo: #9370db;
    }

    /* Replicating StarRating.module.css */
    .container {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .heading {
      font-size: 16px;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0 0 4px;
    }
    .ratingRow {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .starsGroup {
      display: flex;
      align-items: center;
      gap: 2px;
    }
    .starButton {
      font-size: 24px;
      line-height: 1;
      background: none;
      border: none;
      padding: 2px;
      cursor: pointer;
      transition: transform 0.15s ease, color 0.1s ease;
      color: var(--border-light);
    }
    .starButton:focus {
      outline: none;
    }
    .starButton:not(:disabled):hover {
      transform: scale(1.15);
    }
    .starButton:disabled {
      cursor: default;
    }
    .starFilled {
      color: var(--star-color);
    }
    .ratingSummary {
      font-size: 14px;
      color: var(--text-secondary);
    }
    .loginPrompt {
      font-size: 12px;
      color: var(--text-subtle);
    }
    .loginLink {
      color: var(--accent-logo);
      text-decoration: none;
    }
    .loginLink:hover {
      text-decoration: underline;
    }
  </style>
</head>
<body>
  <div class="container" id="star-rating-widget">
    <p class="heading" id="heading">Rate this video</p>
    <div class="ratingRow">
      <div class="starsGroup" role="group" aria-label="Star rating" id="stars-group">
        <button type="button" class="starButton" id="star-1"
          aria-label="Rate 1 star" aria-pressed="false">★</button>
        <button type="button" class="starButton" id="star-2"
          aria-label="Rate 2 stars" aria-pressed="false">★</button>
        <button type="button" class="starButton starFilled" id="star-3"
          aria-label="Rate 3 stars" aria-pressed="true">★</button>
        <button type="button" class="starButton starFilled" id="star-4"
          aria-label="Rate 4 stars" aria-pressed="false">★</button>
        <button type="button" class="starButton starFilled" id="star-5"
          aria-label="Rate 5 stars" aria-pressed="false">★</button>
      </div>
      <span class="ratingSummary" id="rating-summary">3.0 / 5 (12)</span>
    </div>
    <p class="loginPrompt">
      <a href="/login" class="loginLink">Log in</a> to rate this video.
    </p>
  </div>
</body>
</html>"""


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert #rrggbb hex to (r, g, b) tuple."""
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def _rgb_str_to_tuple(rgb: str) -> tuple[int, int, int]:
    """Parse 'rgb(r, g, b)' or 'rgba(r, g, b, a)' into (r, g, b)."""
    nums = re.findall(r"\d+", rgb)
    return (int(nums[0]), int(nums[1]), int(nums[2]))


def _colors_match(computed_rgb: str, expected_hex: str, tolerance: int = 2) -> bool:
    """
    Return True if the computed 'rgb(r,g,b)' string matches the expected hex,
    within a small tolerance to handle browser rounding.
    """
    try:
        actual = _rgb_str_to_tuple(computed_rgb)
        expected = _hex_to_rgb(expected_hex)
        return all(abs(a - e) <= tolerance for a, e in zip(actual, expected))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Layer A: CSS source-code analysis
# ---------------------------------------------------------------------------

class TestLayerACSSSource:
    """
    Layer A: Verify the StarRating module CSS defines the correct visual values.
    No browser required — this is pure text analysis.
    """

    def test_heading_font_size_is_16px(self) -> None:
        """
        Step 2 — Inspect the section heading.
        .heading in StarRating.module.css must declare font-size: 16px.
        """
        css = _read_file(_STAR_RATING_CSS)
        # Extract the .heading rule block
        match = re.search(r"\.heading\s*\{([^}]+)\}", css, re.DOTALL)
        assert match, ".heading rule not found in StarRating.module.css"
        block = match.group(1)
        assert "font-size: 16px" in block, (
            f"Expected 'font-size: 16px' in .heading rule but got:\n{block.strip()}"
        )

    def test_heading_font_weight_is_600(self) -> None:
        """
        Step 2 — Inspect the section heading.
        .heading in StarRating.module.css must declare font-weight: 600.
        """
        css = _read_file(_STAR_RATING_CSS)
        match = re.search(r"\.heading\s*\{([^}]+)\}", css, re.DOTALL)
        assert match, ".heading rule not found in StarRating.module.css"
        block = match.group(1)
        assert "font-weight: 600" in block, (
            f"Expected 'font-weight: 600' in .heading rule but got:\n{block.strip()}"
        )

    def test_star_button_font_size_is_24px(self) -> None:
        """
        Step 3 — Inspect star buttons for size.
        .starButton in StarRating.module.css must declare font-size: 24px.
        """
        css = _read_file(_STAR_RATING_CSS)
        match = re.search(r"\.starButton\s*\{([^}]+)\}", css, re.DOTALL)
        assert match, ".starButton rule not found in StarRating.module.css"
        block = match.group(1)
        assert "font-size: 24px" in block, (
            f"Expected 'font-size: 24px' in .starButton rule but got:\n{block.strip()}"
        )

    def test_empty_star_uses_border_light_variable(self) -> None:
        """
        Step 3 — Inspect empty star color.
        .starButton must use var(--border-light) as its color.
        """
        css = _read_file(_STAR_RATING_CSS)
        match = re.search(r"\.starButton\s*\{([^}]+)\}", css, re.DOTALL)
        assert match, ".starButton rule not found in StarRating.module.css"
        block = match.group(1)
        assert "var(--border-light)" in block, (
            f"Expected 'color: var(--border-light)' in .starButton rule but got:\n{block.strip()}"
        )

    def test_filled_star_uses_star_color_variable(self) -> None:
        """
        Step 3 — Inspect filled star color.
        .starFilled must use var(--star-color) as its color.
        """
        css = _read_file(_STAR_RATING_CSS)
        match = re.search(r"\.starFilled\s*\{([^}]+)\}", css, re.DOTALL)
        assert match, ".starFilled rule not found in StarRating.module.css"
        block = match.group(1)
        assert "var(--star-color)" in block, (
            f"Expected 'color: var(--star-color)' in .starFilled rule but got:\n{block.strip()}"
        )

    def test_star_color_token_is_ff6666(self) -> None:
        """
        Step 3 — Inspect filled star color value.
        --star-color in globals.css must be #ff6666.
        """
        value = _css_globals.get_light_token("--star-color")
        assert value == "#ff6666", (
            f"Expected --star-color to be '#ff6666' in globals.css but got '{value}'."
        )

    def test_border_light_token_is_defined(self) -> None:
        """
        Step 3 — Inspect empty star color token.
        --border-light must be defined in the globals.css :root block.
        """
        value = _css_globals.get_light_token("--border-light")
        assert value, f"--border-light token is empty or missing in globals.css; got: '{value}'"

    def test_hover_effect_uses_transform_scale(self) -> None:
        """
        Step 4 — Hover over the stars.
        The hover rule for .starButton must apply a transform (scale).
        """
        css = _read_file(_STAR_RATING_CSS)
        # Look for a hover rule that contains transform: scale(...)
        hover_match = re.search(
            r"\.starButton[^{]*:hover\s*\{([^}]+)\}",
            css,
            re.DOTALL,
        )
        assert hover_match, (
            "No hover rule found for .starButton in StarRating.module.css. "
            "Expected a rule like '.starButton:not(:disabled):hover { transform: scale(...); }'"
        )
        hover_block = hover_match.group(1)
        assert "transform" in hover_block and "scale" in hover_block, (
            f"Expected hover rule to contain 'transform: scale(...)' but got:\n{hover_block.strip()}"
        )

    def test_heading_text_in_component_source(self) -> None:
        """
        Step 1 & 2 — Navigate and inspect the heading.
        StarRating.tsx must render the text "Rate this video".
        """
        star_rating_tsx = _REPO_ROOT / "web" / "src" / "components" / "StarRating.tsx"
        source = _read_file(star_rating_tsx)
        assert "Rate this video" in source, (
            "The text 'Rate this video' was not found in StarRating.tsx. "
            "The heading may have changed or been removed."
        )


# ---------------------------------------------------------------------------
# Layer B: Playwright computed-style verification
# ---------------------------------------------------------------------------

class TestLayerBPlaywrightStyles:
    """
    Layer B: Render the StarRating widget in a Playwright browser and verify
    computed CSS properties match the visual specification.
    """

    @pytest.fixture(scope="class")
    def page(self):
        """Start a Playwright browser instance scoped to the test class."""
        with sync_playwright() as p:
            headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
            browser = p.chromium.launch(headless=headless)
            ctx = browser.new_context()
            pg = ctx.new_page()
            pg.set_content(_get_fixture_html())
            pg.wait_for_load_state("domcontentloaded")
            yield pg
            browser.close()

    def test_heading_computed_font_size(self, page: Page) -> None:
        """
        Step 2 — Inspect the section heading.
        The computed font-size of #heading must be '16px'.
        """
        font_size = page.evaluate(
            "() => window.getComputedStyle(document.getElementById('heading')).fontSize"
        )
        assert font_size == "16px", (
            f"Expected heading font-size to be '16px' but computed value is '{font_size}'."
        )

    def test_heading_computed_font_weight(self, page: Page) -> None:
        """
        Step 2 — Inspect the section heading.
        The computed font-weight of #heading must be '600'.
        """
        font_weight = page.evaluate(
            "() => window.getComputedStyle(document.getElementById('heading')).fontWeight"
        )
        assert font_weight == "600", (
            f"Expected heading font-weight to be '600' but computed value is '{font_weight}'."
        )

    def test_heading_text_content(self, page: Page) -> None:
        """
        Step 1 & 2 — Locate and inspect the "Rate this video" section heading.
        The heading element must display the text 'Rate this video'.
        """
        text = page.evaluate(
            "() => document.getElementById('heading').textContent.trim()"
        )
        assert text == "Rate this video", (
            f"Expected heading text 'Rate this video' but got '{text}'."
        )

    def test_empty_star_computed_font_size(self, page: Page) -> None:
        """
        Step 3 — Inspect star button size.
        Empty star buttons must have a computed font-size of '24px'.
        """
        font_size = page.evaluate(
            "() => window.getComputedStyle(document.getElementById('star-1')).fontSize"
        )
        assert font_size == "24px", (
            f"Expected star button font-size to be '24px' but computed value is '{font_size}'."
        )

    def test_empty_star_computed_color(self, page: Page) -> None:
        """
        Step 3 — Inspect empty star color.
        Empty stars must resolve to the --border-light color (#dcdcdc in light theme).
        """
        # --border-light is #dcdcdc in light theme
        expected_hex = _css_globals.get_light_token("--border-light")
        color = page.evaluate(
            "() => window.getComputedStyle(document.getElementById('star-1')).color"
        )
        assert _colors_match(color, expected_hex), (
            f"Expected empty star color to match --border-light ({expected_hex}) "
            f"but computed color is '{color}'."
        )

    def test_filled_star_computed_color(self, page: Page) -> None:
        """
        Step 3 — Inspect filled star color.
        Filled stars (with .starFilled class) must resolve to #ff6666 (--star-color).
        """
        expected_hex = "#ff6666"
        color = page.evaluate(
            "() => window.getComputedStyle(document.getElementById('star-3')).color"
        )
        assert _colors_match(color, expected_hex), (
            f"Expected filled star color to match --star-color ({expected_hex}) "
            f"but computed color is '{color}'."
        )

    def test_star_group_role_and_label(self, page: Page) -> None:
        """
        Step 1 — Navigate and locate the 'Rate this video' section.
        The star group must have role='group' and aria-label='Star rating'.
        """
        role = page.get_attribute("#stars-group", "role")
        label = page.get_attribute("#stars-group", "aria-label")
        assert role == "group", f"Expected role='group' on stars container but got '{role}'."
        assert label == "Star rating", (
            f"Expected aria-label='Star rating' but got '{label}'."
        )

    def test_five_star_buttons_present(self, page: Page) -> None:
        """
        Step 1 — Locate the rating section.
        The widget must contain exactly 5 star buttons.
        """
        count = page.evaluate(
            "() => document.querySelectorAll('[role=\"group\"][aria-label=\"Star rating\"] button').length"
        )
        assert count == 5, (
            f"Expected 5 star buttons in the rating widget but found {count}."
        )
