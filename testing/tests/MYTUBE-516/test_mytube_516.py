"""
MYTUBE-516: Comment form redesign — input field and submit button styling

Objective
---------
Verify the redesign of the comment input form, including the borderless state
and the CTA button style.

Steps
-----
1. Navigate to the comments section on the watch page.
2. Inspect the comment input field and click to focus.
3. Inspect the submit button.

Expected Result
---------------
The input is borderless with ``background: var(--bg-page)`` and shows a purple
accent focus ring (``var(--accent-logo)``).  The submit button uses the
``.btn.cta`` style (green pill shape).

Test approach
-------------
**Static source analysis** — reads the CommentSection TSX component and its
CSS module directly.  No live browser or running server is required.  Verifies:

Input field (``commentInput`` CSS class):
  - ``border: none``              → borderless
  - ``background: var(--bg-page)``→ background uses the page-background token
  - ``:focus`` ``box-shadow`` uses ``var(--accent-logo)`` → purple focus ring

Submit button (in CommentSection.tsx):
  - ``className="btn cta"``       → uses the global CTA button class

Global CSS (``.btn.cta`` in globals.css):
  - ``border-radius: 999px``      → pill shape
  - ``background: var(--gradient-cta)``  → green gradient

CSS token values (globals.css ``:root``):
  - ``--gradient-cta`` is a green linear gradient
  - ``--accent-logo`` is a purple hex value (``#6d40cb`` / ``#9370db``)

Architecture
------------
- Reads source files relative to the repo root via ``_REPO_ROOT``.
- All file paths are constants — no hardcoded environment values.
- pytest class-per-concern structure mirrors MYTUBE-461 pattern.
"""
from __future__ import annotations

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# ---------------------------------------------------------------------------
# Constants — source file paths
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

_COMMENT_SECTION_TSX = os.path.join(
    _REPO_ROOT, "web", "src", "components", "CommentSection.tsx"
)
_COMMENT_MODULE_CSS = os.path.join(
    _REPO_ROOT, "web", "src", "components", "CommentSection.module.css"
)
_GLOBALS_CSS = os.path.join(_REPO_ROOT, "web", "src", "app", "globals.css")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_source(path: str) -> str:
    assert os.path.isfile(path), f"Source file not found: {path}"
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _extract_css_class_block(css: str, class_name: str) -> str:
    """Return the CSS declaration block for ``class_name`` (e.g. ``.commentInput``)."""
    pattern = re.compile(
        rf"\.{re.escape(class_name)}\s*\{{([^}}]*)\}}", re.DOTALL
    )
    match = pattern.search(css)
    if not match:
        return ""
    return match.group(0)


def _extract_css_focus_block(css: str, class_name: str) -> str:
    """Return the declaration block for ``class_name:focus``."""
    pattern = re.compile(
        rf"\.{re.escape(class_name)}:focus\s*\{{([^}}]*)\}}", re.DOTALL
    )
    match = pattern.search(css)
    if not match:
        return ""
    return match.group(0)


def _extract_compound_class_block(css: str, parent: str, child: str) -> str:
    """Return the declaration block for ``.parent.child`` compound selector."""
    pattern = re.compile(
        rf"\.{re.escape(parent)}\.{re.escape(child)}\s*\{{([^}}]*)\}}", re.DOTALL
    )
    match = pattern.search(css)
    if not match:
        return ""
    return match.group(0)


def _extract_submit_button_block(tsx: str) -> str:
    """Return the JSX block for ``<button type="submit"`` in the comment form."""
    idx = tsx.find('type="submit"')
    if idx == -1:
        idx = tsx.find("type='submit'")
    if idx == -1:
        return ""
    start = tsx.rfind("<button", 0, idx)
    if start == -1:
        return tsx[max(0, idx - 200): idx + 500]
    end = tsx.find("</button>", idx)
    if end == -1:
        return tsx[start: start + 600]
    return tsx[start: end + len("</button>")]


# ---------------------------------------------------------------------------
# Tests — input field (borderless + bg-page background)
# ---------------------------------------------------------------------------


class TestCommentInputStyling:
    """Verify the comment textarea is borderless with bg-page background."""

    @pytest.fixture(scope="class")
    def css_module(self) -> str:
        return _read_source(_COMMENT_MODULE_CSS)

    @pytest.fixture(scope="class")
    def input_block(self, css_module: str) -> str:
        block = _extract_css_class_block(css_module, "commentInput")
        assert block, (
            "Could not locate '.commentInput' rule in CommentSection.module.css. "
            "The class name may have changed."
        )
        return block

    def test_input_is_borderless(self, input_block: str) -> None:
        """The comment textarea must have ``border: none`` (borderless design)."""
        assert "border: none" in input_block, (
            "'.commentInput' is missing 'border: none'. "
            f"CSS block found:\n{input_block}"
        )

    def test_input_background_uses_bg_page_token(self, input_block: str) -> None:
        """The textarea background must be ``var(--bg-page)``."""
        assert "background: var(--bg-page)" in input_block, (
            "'.commentInput' does not use 'background: var(--bg-page)'. "
            f"CSS block found:\n{input_block}"
        )


# ---------------------------------------------------------------------------
# Tests — focus ring (purple accent via --accent-logo)
# ---------------------------------------------------------------------------


class TestCommentInputFocusRing:
    """Verify the focus state shows a purple accent ring via var(--accent-logo)."""

    @pytest.fixture(scope="class")
    def css_module(self) -> str:
        return _read_source(_COMMENT_MODULE_CSS)

    @pytest.fixture(scope="class")
    def focus_block(self, css_module: str) -> str:
        block = _extract_css_focus_block(css_module, "commentInput")
        assert block, (
            "Could not locate '.commentInput:focus' rule in CommentSection.module.css. "
            "The focus state may be missing."
        )
        return block

    def test_focus_ring_uses_accent_logo_token(self, focus_block: str) -> None:
        """The focus box-shadow must use ``var(--accent-logo)`` (purple accent)."""
        assert "var(--accent-logo)" in focus_block, (
            "'.commentInput:focus' does not use 'var(--accent-logo)' for the focus ring. "
            f"CSS block found:\n{focus_block}"
        )

    def test_focus_ring_uses_box_shadow(self, focus_block: str) -> None:
        """The focus state must apply the ring via ``box-shadow``."""
        assert "box-shadow" in focus_block, (
            "'.commentInput:focus' must apply the ring via 'box-shadow'. "
            f"CSS block found:\n{focus_block}"
        )


# ---------------------------------------------------------------------------
# Tests — submit button (btn cta class)
# ---------------------------------------------------------------------------


class TestCommentSubmitButton:
    """Verify the comment submit button uses the '.btn.cta' class."""

    @pytest.fixture(scope="class")
    def tsx_source(self) -> str:
        return _read_source(_COMMENT_SECTION_TSX)

    @pytest.fixture(scope="class")
    def button_block(self, tsx_source: str) -> str:
        block = _extract_submit_button_block(tsx_source)
        assert block, (
            "Could not locate a <button type='submit'> in CommentSection.tsx. "
            "The submit button may be missing."
        )
        return block

    def test_submit_button_has_btn_cta_class(self, button_block: str) -> None:
        """The comment submit button must carry the 'btn cta' CSS classes."""
        assert "btn cta" in button_block, (
            "Comment submit button is missing the 'btn cta' class. "
            f"Button block found:\n{button_block}"
        )


# ---------------------------------------------------------------------------
# Tests — global .btn.cta definition (pill shape + green gradient)
# ---------------------------------------------------------------------------


class TestBtnCtaGlobalStyles:
    """Verify the global .btn.cta rule defines a green pill shape."""

    @pytest.fixture(scope="class")
    def globals_css(self) -> str:
        return _read_source(_GLOBALS_CSS)

    @pytest.fixture(scope="class")
    def btn_block(self, globals_css: str) -> str:
        block = _extract_css_class_block(globals_css, "btn")
        assert block, (
            "Could not locate '.btn' rule in globals.css. "
            "The global button class may have changed."
        )
        return block

    @pytest.fixture(scope="class")
    def btn_cta_block(self, globals_css: str) -> str:
        block = _extract_compound_class_block(globals_css, "btn", "cta")
        assert block, (
            "Could not locate '.btn.cta' rule in globals.css. "
            "The global CTA button class may have changed."
        )
        return block

    def test_btn_has_pill_border_radius(self, btn_block: str) -> None:
        """The .btn base class must have ``border-radius: 999px`` (pill shape)."""
        assert "border-radius: 999px" in btn_block, (
            "'.btn' is missing 'border-radius: 999px' (pill shape). "
            f"CSS block found:\n{btn_block}"
        )

    def test_btn_cta_has_gradient_cta_background(self, btn_cta_block: str) -> None:
        """The .btn.cta class must use ``var(--gradient-cta)`` background."""
        assert "var(--gradient-cta)" in btn_cta_block, (
            "'.btn.cta' does not use 'var(--gradient-cta)' background. "
            f"CSS block found:\n{btn_cta_block}"
        )


# ---------------------------------------------------------------------------
# Tests — CSS token values (accent-logo is purple, gradient-cta is green)
# ---------------------------------------------------------------------------


_PURPLE_HEX_RE = re.compile(r"#[6-9a-f][0-9a-f]{5}", re.IGNORECASE)
_GREEN_GRADIENT_RE = re.compile(
    r"linear-gradient\(\s*90deg\s*,\s*#62c235\s+0%\s*,\s*#4fa82b\s+100%\s*\)"
)


class TestCssTokenValues:
    """Verify that CSS custom properties carry the expected design values."""

    @pytest.fixture(scope="class")
    def globals_css(self) -> str:
        return _read_source(_GLOBALS_CSS)

    def test_accent_logo_is_purple(self, globals_css: str) -> None:
        """``--accent-logo`` must be a purple hex color (#6d40cb or similar)."""
        # Find --accent-logo declarations
        matches = re.findall(r"--accent-logo\s*:\s*([^;]+);", globals_css)
        assert matches, "--accent-logo not defined in globals.css"
        # Each value should be a purple-range hex (#6xxxxx or #7xxxxx or #8xxxxx or #9xxxxx)
        for value in matches:
            value = value.strip().lower()
            assert value.startswith("#"), (
                f"--accent-logo value '{value}' is not a hex color."
            )
            # Loosely verify it is in the purple hue range (r < 180, b >= 180, or
            # check it's explicitly in the known purple palette).
            known_purples = {"#6d40cb", "#9370db", "#7b55d8", "#8b6ce4"}
            # Accept any known purple or values starting with 6/7/8/9 in the blue-purple range
            is_purple = (
                value in known_purples
                or bool(re.match(r"#[6-9][0-9a-f]{5}", value))
            )
            assert is_purple, (
                f"--accent-logo value '{value}' does not appear to be a purple color. "
                "The focus ring should be purple (accent-logo)."
            )

    def test_gradient_cta_is_green(self, globals_css: str) -> None:
        """``--gradient-cta`` must be a green linear gradient."""
        match = re.search(r"--gradient-cta\s*:\s*([^;]+);", globals_css)
        assert match, "--gradient-cta not defined in globals.css"
        value = match.group(1).strip()
        assert _GREEN_GRADIENT_RE.search(value), (
            f"--gradient-cta value '{value}' is not the expected green gradient "
            "(linear-gradient(90deg, #62c235 0%, #4fa82b 100%))."
        )
