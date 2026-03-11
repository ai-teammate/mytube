"""
MYTUBE-426: Icon component props — className and style applied to SVG element

Objective
---------
Verify that custom CSS classes and inline styles passed as props are correctly
applied to the underlying SVG element of SunIcon and MoonIcon.

Steps
-----
1. Render SunIcon with className="test-class".
2. Render MoonIcon with style={{ marginTop: '10px' }}.
3. Inspect the rendered HTML for both components.

Expected Result
---------------
The SunIcon contains "test-class" in its class list, and the MoonIcon has the
inline style marginTop: 10px applied.

Test Approach
-------------
Delegates to the Jest + React Testing Library suite in
web/src/__tests__/components/icons/icons.test.tsx, which runs in jsdom and
verifies className and style props are forwarded to the SVG element for both
SunIcon and MoonIcon.

Run from repo root:
    pytest testing/tests/MYTUBE-426/test_mytube_426.py -v
"""
from __future__ import annotations

import os
import subprocess
import pytest

WEB_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "web")
)

TEST_FILE = "__tests__/components/icons/icons.test.tsx"


def _run_jest(test_name_pattern: str | None = None) -> subprocess.CompletedProcess:
    """Run the Jest suite for icon components in web/ and return the result."""
    cmd = [
        "npm",
        "test",
        "--",
        f"--testPathPatterns={TEST_FILE}",
        "--verbose",
        "--no-coverage",
        "--forceExit",
    ]
    if test_name_pattern:
        cmd += ["--testNamePattern", test_name_pattern]

    return subprocess.run(
        cmd,
        cwd=WEB_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )


class TestIconProps:
    """MYTUBE-426: Verify that className and style props are applied to SVG element."""

    def test_sun_icon_classname_applied_to_svg(self):
        """
        Step 1 — Render SunIcon with className="test-class".
        The SVG element must contain 'test-class' in its class list.
        Delegates to the 'SunIcon > accepts a className prop' Jest test case.
        """
        result = _run_jest(test_name_pattern="SunIcon.*accepts a className prop")
        combined = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"SunIcon className Jest test FAILED (exit code {result.returncode}).\n\n"
            f"=== STDOUT ===\n{result.stdout}\n\n"
            f"=== STDERR ===\n{result.stderr}"
        )

        assert "accepts a className prop" in combined, (
            "Expected Jest test 'SunIcon > accepts a className prop' to appear in output.\n"
            f"Full output:\n{combined}"
        )

    def test_moon_icon_style_applied_to_svg(self):
        """
        Step 2 — Render MoonIcon with style={{ marginTop: '10px' }}.
        The SVG element must have the inline style applied.
        Delegates to the 'MoonIcon > accepts a style prop' Jest test case.
        """
        result = _run_jest(test_name_pattern="MoonIcon.*accepts a style prop")
        combined = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"MoonIcon style Jest test FAILED (exit code {result.returncode}).\n\n"
            f"=== STDOUT ===\n{result.stdout}\n\n"
            f"=== STDERR ===\n{result.stderr}"
        )

        assert "accepts a style prop" in combined, (
            "Expected Jest test 'MoonIcon > accepts a style prop' to appear in output.\n"
            f"Full output:\n{combined}"
        )

    def test_sun_icon_classname_and_moon_icon_style_full_suite(self):
        """
        Combined assertion — runs the full icon test suite to verify that all
        className and style tests for both SunIcon and MoonIcon pass together.
        This is the canonical MYTUBE-426 assertion.
        """
        result = _run_jest()
        combined = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"Icon component Jest suite FAILED (exit code {result.returncode}).\n\n"
            f"=== STDOUT ===\n{result.stdout}\n\n"
            f"=== STDERR ===\n{result.stderr}"
        )

        # Verify SunIcon className test case ran and passed
        assert "SunIcon" in combined, (
            f"SunIcon tests not found in output.\nFull output:\n{combined}"
        )

        # Verify MoonIcon style test case ran and passed
        assert "MoonIcon" in combined, (
            f"MoonIcon tests not found in output.\nFull output:\n{combined}"
        )

        # Verify both className and style cases are reported
        assert "accepts a className prop" in combined, (
            f"'accepts a className prop' test not found in output.\nFull output:\n{combined}"
        )
        assert "accepts a style prop" in combined, (
            f"'accepts a style prop' test not found in output.\nFull output:\n{combined}"
        )
