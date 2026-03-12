"""
MYTUBE-451: VideoCard title clamping — long titles are truncated at two lines

Objective
---------
Ensure that video titles that exceed the available width are limited to two
lines to maintain card layout consistency.

Preconditions
-------------
A video exists with a very long title (e.g., 200+ characters).

Steps
-----
1. Navigate to a page displaying the VideoCard for the long-titled video.
2. Observe the rendered title text.

Expected Result
---------------
The title text is restricted to a maximum of two lines. Overflowing text is
hidden or shown with an ellipsis (two-line clamp), preventing the card height
from expanding excessively.

Test Approach
-------------
Static CSS inspection: reads web/src/components/VideoCard.module.css and
verifies the .videoTitle rule contains the required two-line clamping
properties:
  - display: -webkit-box
  - -webkit-line-clamp: 2
  - -webkit-box-orient: vertical
  - overflow: hidden

Also verifies that VideoCard.tsx applies styles.videoTitle to the title
Link element, confirming the CSS rule is wired to the rendered output.

Run from repo root:
    pytest testing/tests/MYTUBE-451/test_mytube_451.py -v
"""
from __future__ import annotations

import pathlib
import re

# ── Paths ────────────────────────────────────────────────────────────────────

_REPO_ROOT: pathlib.Path = pathlib.Path(__file__).parents[3]
_CSS_PATH: pathlib.Path = _REPO_ROOT / "web" / "src" / "components" / "VideoCard.module.css"
_TSX_PATH: pathlib.Path = _REPO_ROOT / "web" / "src" / "components" / "VideoCard.tsx"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_rule_block(css_text: str, selector: str) -> str:
    """Return the declaration block for *selector* from *css_text*.

    Matches the first ``selector { ... }`` block. Returns an empty string if
    the selector is not found.
    """
    pattern = re.compile(
        rf"{re.escape(selector)}\s*\{{([^}}]*)\}}",
        re.DOTALL,
    )
    match = pattern.search(css_text)
    return match.group(1) if match else ""


def _get_property(block: str, prop: str) -> str | None:
    """Return the trimmed value of *prop* from a CSS declaration block, or None."""
    pattern = re.compile(
        rf"(?:^|;|\n)\s*{re.escape(prop)}\s*:\s*([^;]+);",
        re.DOTALL,
    )
    match = pattern.search(block)
    return match.group(1).strip() if match else None


# ── Test class ────────────────────────────────────────────────────────────────

class TestVideoCardTitleClamping:
    """MYTUBE-451: VideoCard title is clamped to two lines via CSS."""

    def setup_method(self) -> None:
        self._css_text = _CSS_PATH.read_text()
        self._tsx_text = _TSX_PATH.read_text()
        self._block = _extract_rule_block(self._css_text, ".videoTitle")

    # ── CSS property assertions ───────────────────────────────────────────────

    def test_videotitle_rule_exists_in_css_module(self) -> None:
        """.videoTitle selector must be present in VideoCard.module.css."""
        assert self._block, (
            f".videoTitle rule not found in {_CSS_PATH}. "
            "The CSS module must define a .videoTitle selector to enable title clamping."
        )

    def test_display_webkit_box(self) -> None:
        """display: -webkit-box must be set to enable the line-clamp mechanism."""
        value = _get_property(self._block, "display")
        assert value == "-webkit-box", (
            f"Expected '.videoTitle {{ display: -webkit-box; }}' but got "
            f"'display: {value!r}' in {_CSS_PATH}. "
            "The -webkit-box display mode is required for -webkit-line-clamp to work."
        )

    def test_webkit_line_clamp_is_2(self) -> None:
        """-webkit-line-clamp must be 2 to restrict titles to two lines."""
        value = _get_property(self._block, "-webkit-line-clamp")
        assert value == "2", (
            f"Expected '-webkit-line-clamp: 2' but got '-webkit-line-clamp: {value!r}' "
            f"in {_CSS_PATH}. Long titles would not be clamped to two lines."
        )

    def test_webkit_box_orient_vertical(self) -> None:
        """-webkit-box-orient: vertical is required for line clamping."""
        value = _get_property(self._block, "-webkit-box-orient")
        assert value == "vertical", (
            f"Expected '-webkit-box-orient: vertical' but got "
            f"'-webkit-box-orient: {value!r}' in {_CSS_PATH}. "
            "The vertical box orientation is required for -webkit-line-clamp to clamp text lines."
        )

    def test_overflow_hidden(self) -> None:
        """overflow: hidden must be set so clamped text is not visible."""
        value = _get_property(self._block, "overflow")
        assert value == "hidden", (
            f"Expected 'overflow: hidden' but got 'overflow: {value!r}' in {_CSS_PATH}. "
            "Without overflow:hidden, text beyond two lines would still be visible."
        )

    # ── Component wiring assertion ────────────────────────────────────────────

    def test_videotitle_class_applied_in_component(self) -> None:
        """VideoCard.tsx must apply styles.videoTitle to the title Link element.

        This ensures the CSS clamping rule is actually wired to the rendered
        title anchor in the component.
        """
        assert "styles.videoTitle" in self._tsx_text, (
            f"styles.videoTitle not found in {_TSX_PATH}. "
            "The VideoCard component must apply the videoTitle CSS module class "
            "to the title Link so that the clamping CSS rule takes effect."
        )
