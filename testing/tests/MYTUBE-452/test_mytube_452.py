"""
MYTUBE-452: Hero section feature pills and headline — visual styling matches design tokens

Objective
---------
Verify the homepage hero section correctly renders the headline and feature
pills using the established design tokens.

Steps
-----
1. Navigate to the homepage.
2. Inspect the feature pills row above the headline.
3. Inspect the headline "MYTUBE: personal video portal".
4. Check the sub-text paragraph styling.

Expected Result
---------------
* Pills "Upload & Share", "HLS Streaming", and "Playlists & Discovery" use
  var(--accent-pill-bg) and var(--text-pill).
* Headline uses a responsive font size via clamp and has letter-spacing: -0.02em.
* Sub-text is colored with var(--text-secondary) and does not exceed 62ch in width.

Test approach
-------------
**Layer A — CSS token validation** (always runs, no browser required):
    Reads web/src/app/globals.css and verifies that the required design tokens
    (--accent-pill-bg, --text-pill, --text-secondary) are correctly defined in
    the :root block.

**Layer B — Source code structural analysis** (no browser required):
    Parses the homepage source files under web/src/app/ and
    web/src/components/ to confirm the hero section is present with:
    - Feature pills referencing var(--accent-pill-bg) and var(--text-pill)
    - A headline element with the expected text, clamp()-based font size,
      and letter-spacing: -0.02em
    - A sub-text element styled with var(--text-secondary) and a max-width
      using ch units (≤ 62ch)

Run from repo root:
    pytest testing/tests/MYTUBE-452/test_mytube_452.py -v
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
_HOME_PAGE_CLIENT = os.path.join(_REPO_ROOT, "web", "src", "app", "HomePageClient.tsx")
_WEB_SRC = os.path.join(_REPO_ROOT, "web", "src")

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


def _find_hero_sources() -> list[tuple[str, str]]:
    """
    Walk web/src looking for TSX/CSS files that contain any hero-section
    marker text.  Returns a list of (path, content) tuples for all matching
    files so tests can assert against the combined hero implementation.
    """
    hero_markers = [
        "personal video portal",
        "Upload & Share",
        "HLS Streaming",
        "Playlists & Discovery",
        "hero",
        "Hero",
    ]
    results: list[tuple[str, str]] = []
    for root, _dirs, files in os.walk(_WEB_SRC):
        # Skip node_modules and generated output directories
        if "node_modules" in root or ".next" in root or "__tests__" in root:
            continue
        for fname in files:
            if not (fname.endswith(".tsx") or fname.endswith(".ts") or fname.endswith(".css") or fname.endswith(".module.css")):
                continue
            fpath = os.path.join(root, fname)
            try:
                content = open(fpath, encoding="utf-8").read()
            except OSError:
                continue
            if any(marker in content for marker in hero_markers):
                results.append((fpath, content))
    return results


# ---------------------------------------------------------------------------
# Layer A: CSS design token validation
# ---------------------------------------------------------------------------

class TestLayerACSSTokens:
    """
    MYTUBE-452 — Layer A: Design tokens required for the hero section
    are correctly defined in globals.css.
    """

    def test_accent_pill_bg_token_defined(self) -> None:
        """
        Step 2 — Inspect feature pills styling.
        --accent-pill-bg must be defined in the :root block of globals.css.
        Expected value: #e5daf6 (light theme).
        """
        value = _css.get_light_token("--accent-pill-bg")
        assert value == "#e5daf6", (
            f"Expected --accent-pill-bg to be '#e5daf6' but got '{value}'. "
            "The pill background design token is missing or incorrect in globals.css."
        )

    def test_text_pill_token_defined(self) -> None:
        """
        Step 2 — Inspect feature pills styling.
        --text-pill must be defined in the :root block of globals.css.
        Expected value: #6d40cb (light theme).
        """
        value = _css.get_light_token("--text-pill")
        assert value == "#6d40cb", (
            f"Expected --text-pill to be '#6d40cb' but got '{value}'. "
            "The pill text design token is missing or incorrect in globals.css."
        )

    def test_text_secondary_token_defined(self) -> None:
        """
        Step 4 — Check sub-text paragraph styling.
        --text-secondary must be defined in the :root block of globals.css.
        Expected value: #666666 (light theme).
        """
        value = _css.get_light_token("--text-secondary")
        assert value == "#666666", (
            f"Expected --text-secondary to be '#666666' but got '{value}'. "
            "The secondary text design token is missing or incorrect in globals.css."
        )


# ---------------------------------------------------------------------------
# Layer B: Source code structural analysis
# ---------------------------------------------------------------------------

class TestLayerBHeroSection:
    """
    MYTUBE-452 — Layer B: The homepage hero section implements feature pills,
    headline, and sub-text with the correct design-token references and
    CSS properties.
    """

    def test_hero_section_exists_in_source(self) -> None:
        """
        Steps 1–4 — The homepage must contain a hero section element with
        identifiable content (headline text or feature pill labels).

        Checks HomePageClient.tsx and any other file under web/src/ for the
        expected hero content.
        """
        hero_sources = _find_hero_sources()
        relevant = [
            (path, content) for (path, content) in hero_sources
            if "personal video portal" in content
            or "Upload & Share" in content
            or "HLS Streaming" in content
            or "Playlists & Discovery" in content
        ]
        assert relevant, (
            "Hero section content not found in any source file under web/src/. "
            "Expected at least one TSX/CSS file to contain the hero headline "
            "'personal video portal' or one of the feature pill labels "
            "('Upload & Share', 'HLS Streaming', 'Playlists & Discovery'). "
            "The hero section appears to be missing from the homepage implementation."
        )

    def test_feature_pills_use_accent_pill_bg_token(self) -> None:
        """
        Step 2 — Feature pills row styling.
        Pills must reference var(--accent-pill-bg) for their background color.
        Looks for the token reference in TSX inline styles, CSS modules, or
        a <style> tag inside the hero section source files.
        """
        hero_sources = _find_hero_sources()
        all_content = "\n".join(content for _, content in hero_sources)
        # Accept both CSS var() reference styles
        pattern = re.compile(r"var\(\s*--accent-pill-bg\s*\)")
        assert pattern.search(all_content), (
            "No source file under web/src/ references var(--accent-pill-bg). "
            "Feature pills in the hero section must use this token for their "
            "background color. Found files: "
            + str([path for path, _ in hero_sources])
        )

    def test_feature_pills_use_text_pill_token(self) -> None:
        """
        Step 2 — Feature pills row styling.
        Pills must reference var(--text-pill) for their text color.
        """
        hero_sources = _find_hero_sources()
        all_content = "\n".join(content for _, content in hero_sources)
        pattern = re.compile(r"var\(\s*--text-pill\s*\)")
        assert pattern.search(all_content), (
            "No source file under web/src/ references var(--text-pill). "
            "Feature pills in the hero section must use this token for their "
            "text color. Found files: "
            + str([path for path, _ in hero_sources])
        )

    def test_headline_uses_clamp_font_size(self) -> None:
        """
        Step 3 — Headline "MYTUBE: personal video portal" styling.
        The headline must use a responsive font size expressed with clamp().
        Looks for a clamp() call in inline style, CSS module, or Tailwind
        arbitrary value associated with the hero headline.
        """
        hero_sources = _find_hero_sources()
        all_content = "\n".join(content for _, content in hero_sources)
        # Accept both plain clamp() and CSS font-size with clamp
        clamp_pattern = re.compile(r"clamp\s*\(")
        assert clamp_pattern.search(all_content), (
            "No source file under web/src/ containing hero content uses clamp() "
            "for a responsive font size on the hero headline. "
            "The headline 'MYTUBE: personal video portal' must use "
            "font-size: clamp(...) for responsive typography. "
            "Found files: " + str([path for path, _ in hero_sources])
        )

    def test_headline_has_letter_spacing(self) -> None:
        """
        Step 3 — Headline "MYTUBE: personal video portal" styling.
        The headline must have letter-spacing: -0.02em applied.
        """
        hero_sources = _find_hero_sources()
        all_content = "\n".join(content for _, content in hero_sources)
        # CSS property: letter-spacing: -0.02em  OR  JSX: letterSpacing: "-0.02em"
        ls_pattern = re.compile(
            r"letter-spacing\s*:\s*-0\.02em|letterSpacing\s*:\s*['\"]?-0\.02em['\"]?"
        )
        assert ls_pattern.search(all_content), (
            "No source file under web/src/ containing hero content applies "
            "letter-spacing: -0.02em to the headline. "
            "The headline 'MYTUBE: personal video portal' must have this "
            "letter-spacing to match the design specification. "
            "Found files: " + str([path for path, _ in hero_sources])
        )

    def test_subtext_uses_text_secondary_token(self) -> None:
        """
        Step 4 — Sub-text paragraph styling.
        The sub-text must reference var(--text-secondary) for its color.
        """
        hero_sources = _find_hero_sources()
        all_content = "\n".join(content for _, content in hero_sources)
        pattern = re.compile(r"var\(\s*--text-secondary\s*\)")
        assert pattern.search(all_content), (
            "No source file under web/src/ containing hero content references "
            "var(--text-secondary) for the sub-text color. "
            "The sub-text paragraph must use this design token. "
            "Found files: " + str([path for path, _ in hero_sources])
        )

    def test_subtext_max_width_62ch(self) -> None:
        """
        Step 4 — Sub-text paragraph styling.
        The sub-text must not exceed 62ch in width.
        Looks for max-width: 62ch or a ch-unit width ≤ 62 applied to the
        sub-text element in any hero source file.
        """
        hero_sources = _find_hero_sources()
        all_content = "\n".join(content for _, content in hero_sources)
        # Accept max-width: 62ch (CSS) or maxWidth: "62ch" (JSX inline style)
        ch_pattern = re.compile(
            r"max-width\s*:\s*(\d+)ch|maxWidth\s*:\s*['\"](\d+)ch['\"]"
        )
        matches = ch_pattern.findall(all_content)
        # Flatten and filter empty strings from alternation groups
        ch_values = [int(v) for pair in matches for v in pair if v]
        assert ch_values, (
            "No source file under web/src/ containing hero content specifies "
            "a max-width with ch units for the sub-text paragraph. "
            "The sub-text must have max-width: 62ch (or equivalent). "
            "Found files: " + str([path for path, _ in hero_sources])
        )
        assert any(v <= 62 for v in ch_values), (
            f"The sub-text max-width ch values found are {ch_values}, "
            "but none is ≤ 62ch as required by the design specification."
        )
