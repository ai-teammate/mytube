"""
MYTUBE-461: Auth submit button — green gradient pill design applied

Objective
---------
Verify that the primary submit button on the Sign In and Register pages matches
the green gradient pill design specification.

Expected Result
---------------
The button:
- Uses the ``btn cta`` CSS classes.
- Is full-width (``w-full`` Tailwind class).
- Features a green gradient background via the ``--gradient-cta`` CSS variable
  (``linear-gradient(90deg, #62c235 0%, #4fa82b 100%)``).
- Has a pill-shaped border-radius (``borderRadius: 999``).

Test approach
-------------
**Static source analysis** — reads the TSX source files for the login and
register pages directly.  No browser or live server required.  Each property
is verified with a focused regex against the actual JSX markup, so any
regression (wrong class, wrong radius, wrong gradient) produces a clear failure.
"""
from __future__ import annotations

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

_LOGIN_PAGE = os.path.join(_REPO_ROOT, "web", "src", "app", "login", "page.tsx")
_REGISTER_PAGE = os.path.join(_REPO_ROOT, "web", "src", "app", "register", "page.tsx")

# The --gradient-cta token value defined in globals.css.
_GRADIENT_CTA_TOKEN = "--gradient-cta"
_EXPECTED_GRADIENT_RE = re.compile(
    r"linear-gradient\(\s*90deg\s*,\s*#62c235\s+0%\s*,\s*#4fa82b\s+100%\s*\)"
)

_GLOBALS_CSS = os.path.join(_REPO_ROOT, "web", "src", "app", "globals.css")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_source(path: str) -> str:
    assert os.path.isfile(path), f"Source file not found: {path}"
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _extract_submit_button_block(source: str) -> str:
    """Return the JSX block for the primary submit button (type='submit')
    that carries the 'btn cta' class.

    Grabs from the <button opening tag through to the matching closing tag.
    Falls back to a reasonable substring if the full block cannot be parsed.
    """
    # Find the line with type="submit" that also has 'btn cta'
    idx = source.find('btn cta')
    if idx == -1:
        return ""
    # Walk backwards to the preceding <button tag
    start = source.rfind("<button", 0, idx)
    if start == -1:
        return source[max(0, idx - 200): idx + 500]
    # Walk forwards to </button>
    end = source.find("</button>", idx)
    if end == -1:
        return source[start: start + 800]
    return source[start: end + len("</button>")]


def _get_gradient_cta_value(css_path: str) -> str:
    """Extract the --gradient-cta value from the :root block of globals.css."""
    css = _read_source(css_path)
    match = re.search(r"--gradient-cta\s*:\s*([^;]+);", css)
    assert match, f"--gradient-cta not found in {css_path}"
    return match.group(1).strip()


# ---------------------------------------------------------------------------
# Tests — Login page
# ---------------------------------------------------------------------------


class TestLoginSubmitButton:
    """MYTUBE-461 — Login page submit button design."""

    @pytest.fixture(scope="class")
    def button_block(self) -> str:
        source = _read_source(_LOGIN_PAGE)
        block = _extract_submit_button_block(source)
        assert block, (
            "Could not locate 'btn cta' submit button in login/page.tsx. "
            "The button may be missing or the class names have changed."
        )
        return block

    def test_has_btn_cta_class(self, button_block: str) -> None:
        """Submit button must carry both 'btn' and 'cta' CSS classes."""
        assert "btn cta" in button_block, (
            "Login submit button is missing the 'btn cta' class. "
            f"Button block found:\n{button_block}"
        )

    def test_is_full_width(self, button_block: str) -> None:
        """Submit button must be full-width (w-full Tailwind class)."""
        assert "w-full" in button_block, (
            "Login submit button is missing the 'w-full' class. "
            f"Button block found:\n{button_block}"
        )

    def test_has_green_gradient_background(self, button_block: str) -> None:
        """Submit button background must reference the --gradient-cta token."""
        gradient_token_used = "var(--gradient-cta)" in button_block
        gradient_inline = bool(_EXPECTED_GRADIENT_RE.search(button_block))
        assert gradient_token_used or gradient_inline, (
            "Login submit button does not use a green gradient background. "
            "Expected 'var(--gradient-cta)' or an inline green gradient. "
            f"Button block found:\n{button_block}"
        )

    def test_has_pill_border_radius(self, button_block: str) -> None:
        """Submit button must have a pill-shaped border-radius (999)."""
        assert "999" in button_block, (
            "Login submit button is missing a pill border-radius (999). "
            f"Button block found:\n{button_block}"
        )


# ---------------------------------------------------------------------------
# Tests — Register page
# ---------------------------------------------------------------------------


class TestRegisterSubmitButton:
    """MYTUBE-461 — Register page submit button design."""

    @pytest.fixture(scope="class")
    def button_block(self) -> str:
        source = _read_source(_REGISTER_PAGE)
        block = _extract_submit_button_block(source)
        assert block, (
            "Could not locate 'btn cta' submit button in register/page.tsx. "
            "The button may be missing or the class names have changed."
        )
        return block

    def test_has_btn_cta_class(self, button_block: str) -> None:
        """Submit button must carry both 'btn' and 'cta' CSS classes."""
        assert "btn cta" in button_block, (
            "Register submit button is missing the 'btn cta' class. "
            f"Button block found:\n{button_block}"
        )

    def test_is_full_width(self, button_block: str) -> None:
        """Submit button must be full-width (w-full Tailwind class)."""
        assert "w-full" in button_block, (
            "Register submit button is missing the 'w-full' class. "
            f"Button block found:\n{button_block}"
        )

    def test_has_green_gradient_background(self, button_block: str) -> None:
        """Submit button background must reference the --gradient-cta token."""
        gradient_token_used = "var(--gradient-cta)" in button_block
        gradient_inline = bool(_EXPECTED_GRADIENT_RE.search(button_block))
        assert gradient_token_used or gradient_inline, (
            "Register submit button does not use a green gradient background. "
            "Expected 'var(--gradient-cta)' or an inline green gradient. "
            f"Button block found:\n{button_block}"
        )

    def test_has_pill_border_radius(self, button_block: str) -> None:
        """Submit button must have a pill-shaped border-radius (999)."""
        assert "999" in button_block, (
            "Register submit button is missing a pill border-radius (999). "
            f"Button block found:\n{button_block}"
        )


# ---------------------------------------------------------------------------
# Tests — CSS token correctness
# ---------------------------------------------------------------------------


class TestGradientCtaToken:
    """MYTUBE-461 — Verify --gradient-cta token is a green gradient."""

    def test_gradient_cta_is_green(self) -> None:
        """--gradient-cta must be a linear gradient using green (#62c235 / #4fa82b)."""
        value = _get_gradient_cta_value(_GLOBALS_CSS)
        assert _EXPECTED_GRADIENT_RE.search(value), (
            f"Expected --gradient-cta to match a 90deg green gradient "
            f"(#62c235 → #4fa82b), but got: '{value}'"
        )
