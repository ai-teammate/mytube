"""
MYTUBE-465: AppShell layout structure — outer page-wrap and inner shell contain correct styles

Objective
---------
Verify the structural implementation of the new AppShell layout including the
page-wrap and shell containers.

Steps
-----
1. Open the application on a standard route (e.g., Dashboard).
2. Inspect the element with class ``page-wrap``.
3. Inspect the element with class ``shell`` inside the page-wrap.

Expected Result
---------------
The ``page-wrap`` container has ``position: relative``, ``min-height: 100vh``,
and ``background: var(--bg-page)``.
The ``shell`` container has ``max-width: 1320px``, ``border-radius: 24px``,
``background: var(--bg-content)``, and ``box-shadow: var(--shadow-main)``.

Test approach
-------------
**Static source analysis** — reads the CSS source (``globals.css``) and the
AppShell component (``AppShell.tsx``) directly.  No browser or live server
required.  Every required property is verified with a focused regex so any
regression produces a clear and informative failure message.

Run from repo root:
    pytest testing/tests/MYTUBE-465/test_mytube_465.py -v
"""
from __future__ import annotations

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

_GLOBALS_CSS = os.path.join(_REPO_ROOT, "web", "src", "app", "globals.css")
_APP_SHELL_TSX = os.path.join(_REPO_ROOT, "web", "src", "components", "AppShell.tsx")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_source(path: str) -> str:
    assert os.path.isfile(path), f"Source file not found: {path}"
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _extract_css_rule_block(css: str, selector: str) -> str:
    """Return the declaration block for *selector* (first occurrence only).

    Example::

        block = _extract_css_rule_block(css, ".page-wrap")
        # returns e.g. "  position: relative;\n  min-height: 100vh;\n  ..."
    """
    escaped = re.escape(selector)
    # Match `selector { ... }` where ... does not contain a nested `{`.
    pattern = re.compile(
        rf"{escaped}\s*\{{([^}}]*)\}}",
        re.DOTALL,
    )
    match = pattern.search(css)
    assert match, (
        f"CSS rule for '{selector}' not found in {_GLOBALS_CSS}. "
        "The selector may be missing or the CSS file structure has changed."
    )
    return match.group(1)


def _assert_css_property(block: str, prop: str, expected_value: str, selector: str) -> None:
    """Assert that *prop* is set to *expected_value* inside *block*.

    The check is value-exact after stripping whitespace.
    """
    pattern = re.compile(
        rf"{re.escape(prop)}\s*:\s*([^;]+);",
        re.DOTALL,
    )
    match = pattern.search(block)
    assert match, (
        f"Property '{prop}' not found in the CSS rule for '{selector}'. "
        f"Block content:\n{block.strip()}"
    )
    actual = match.group(1).strip()
    assert actual == expected_value, (
        f"CSS property mismatch for '{selector}'.\n"
        f"  Property : {prop}\n"
        f"  Expected : {expected_value}\n"
        f"  Actual   : {actual}"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def globals_css() -> str:
    return _read_source(_GLOBALS_CSS)


@pytest.fixture(scope="module")
def app_shell_tsx() -> str:
    return _read_source(_APP_SHELL_TSX)


@pytest.fixture(scope="module")
def page_wrap_block(globals_css: str) -> str:
    return _extract_css_rule_block(globals_css, ".page-wrap")


@pytest.fixture(scope="module")
def shell_block(globals_css: str) -> str:
    return _extract_css_rule_block(globals_css, ".shell")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAppShellComponentSource:
    """Verify that AppShell.tsx uses the correct class names."""

    def test_page_wrap_class_present(self, app_shell_tsx: str) -> None:
        """AppShell must apply the ``page-wrap`` class to the outer div."""
        assert 'className="page-wrap"' in app_shell_tsx, (
            "AppShell.tsx does not contain className=\"page-wrap\". "
            "The outer wrapper must carry this class."
        )

    def test_shell_class_present(self, app_shell_tsx: str) -> None:
        """AppShell must apply the ``shell`` class to the inner container div."""
        assert 'className="shell"' in app_shell_tsx, (
            "AppShell.tsx does not contain className=\"shell\". "
            "The inner container must carry this class."
        )


class TestPageWrapStyles:
    """Verify CSS properties of the .page-wrap container."""

    def test_position_relative(self, page_wrap_block: str) -> None:
        """page-wrap must have position: relative."""
        _assert_css_property(page_wrap_block, "position", "relative", ".page-wrap")

    def test_min_height_100vh(self, page_wrap_block: str) -> None:
        """page-wrap must have min-height: 100vh."""
        _assert_css_property(page_wrap_block, "min-height", "100vh", ".page-wrap")

    def test_background_bg_page(self, page_wrap_block: str) -> None:
        """page-wrap background must reference the --bg-page CSS variable."""
        _assert_css_property(page_wrap_block, "background", "var(--bg-page)", ".page-wrap")


class TestShellStyles:
    """Verify CSS properties of the .shell container."""

    def test_max_width_1320px(self, shell_block: str) -> None:
        """shell must have max-width: 1320px."""
        _assert_css_property(shell_block, "max-width", "1320px", ".shell")

    def test_border_radius_24px(self, shell_block: str) -> None:
        """shell must have border-radius: 24px."""
        _assert_css_property(shell_block, "border-radius", "24px", ".shell")

    def test_background_bg_content(self, shell_block: str) -> None:
        """shell background must reference the --bg-content CSS variable."""
        _assert_css_property(shell_block, "background", "var(--bg-content)", ".shell")

    def test_box_shadow_shadow_main(self, shell_block: str) -> None:
        """shell box-shadow must reference the --shadow-main CSS variable."""
        _assert_css_property(shell_block, "box-shadow", "var(--shadow-main)", ".shell")
