"""
MYTUBE-459: Social login buttons — style and icons match redesign

Objective
---------
Verify the visual styling and icon presence of Google and GitHub social login
buttons rendered by the LoginPage component.

Steps
-----
1. Locate the social login buttons (.auth-btn) on the login page.
2. Inspect the borders, radius, and internal icons.

Expected Result
---------------
Buttons are full-width with ``1.5px solid var(--border-light)``,
``border-radius: 12px``, and ``background: var(--bg-content)``.
The Google button includes a colored "G" SVG icon, and the GitHub button
includes a GitHub mark SVG icon.

Test Approach
-------------
Delegates to Jest + React Testing Library in
web/src/__tests__/app/login/social_buttons_style.test.tsx, which renders the
LoginPage in jsdom and inspects the inline styles and SVG child elements of
each .auth-btn button.

Run from repo root::

    pytest testing/tests/MYTUBE-459/test_mytube_459.py -v
"""
from __future__ import annotations

import os
import subprocess

import pytest

WEB_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "web")
)

TEST_FILE = "__tests__/app/login/social_buttons_style.test.tsx"


def _run_jest(test_name_pattern: str | None = None) -> subprocess.CompletedProcess:
    """Run the Jest suite for social button styles and return the result."""
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


class TestSocialLoginButtonStyles:
    """MYTUBE-459: Social login buttons — style and icons match redesign."""

    def test_google_button_border(self):
        """
        Step 2a — The Google .auth-btn has border: 1.5px solid var(--border-light).
        """
        result = _run_jest(test_name_pattern="Google button has border")
        combined = result.stdout + result.stderr
        assert result.returncode == 0, (
            f"Google border test FAILED (exit {result.returncode}).\n\n"
            f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}"
        )
        assert "Google button has border" in combined

    def test_google_button_border_radius(self):
        """
        Step 2b — The Google .auth-btn has borderRadius: 12px.
        """
        result = _run_jest(test_name_pattern="Google button has borderRadius")
        combined = result.stdout + result.stderr
        assert result.returncode == 0, (
            f"Google borderRadius test FAILED (exit {result.returncode}).\n\n"
            f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}"
        )
        assert "Google button has borderRadius" in combined

    def test_google_button_background(self):
        """
        Step 2c — The Google .auth-btn has background: var(--bg-content).
        """
        result = _run_jest(test_name_pattern="Google button has background")
        combined = result.stdout + result.stderr
        assert result.returncode == 0, (
            f"Google background test FAILED (exit {result.returncode}).\n\n"
            f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}"
        )
        assert "Google button has background" in combined

    def test_google_button_full_width(self):
        """
        Step 2d — The Google .auth-btn has the w-full (full-width) class.
        """
        result = _run_jest(test_name_pattern="Google button is full-width")
        combined = result.stdout + result.stderr
        assert result.returncode == 0, (
            f"Google full-width test FAILED (exit {result.returncode}).\n\n"
            f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}"
        )
        assert "Google button is full-width" in combined

    def test_google_button_svg_icon(self):
        """
        Step 2e — The Google button contains a colored SVG icon (4 brand-color paths).
        """
        result = _run_jest(test_name_pattern="Google button contains a colored SVG icon")
        combined = result.stdout + result.stderr
        assert result.returncode == 0, (
            f"Google SVG icon test FAILED (exit {result.returncode}).\n\n"
            f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}"
        )
        assert "Google button contains a colored SVG icon" in combined

    def test_github_button_border(self):
        """
        Step 2f — The GitHub .auth-btn has border: 1.5px solid var(--border-light).
        """
        result = _run_jest(test_name_pattern="GitHub button has border")
        combined = result.stdout + result.stderr
        assert result.returncode == 0, (
            f"GitHub border test FAILED (exit {result.returncode}).\n\n"
            f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}"
        )
        assert "GitHub button has border" in combined

    def test_github_button_border_radius(self):
        """
        Step 2g — The GitHub .auth-btn has borderRadius: 12px.
        """
        result = _run_jest(test_name_pattern="GitHub button has borderRadius")
        combined = result.stdout + result.stderr
        assert result.returncode == 0, (
            f"GitHub borderRadius test FAILED (exit {result.returncode}).\n\n"
            f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}"
        )
        assert "GitHub button has borderRadius" in combined

    def test_github_button_background(self):
        """
        Step 2h — The GitHub .auth-btn has background: var(--bg-content).
        """
        result = _run_jest(test_name_pattern="GitHub button has background")
        combined = result.stdout + result.stderr
        assert result.returncode == 0, (
            f"GitHub background test FAILED (exit {result.returncode}).\n\n"
            f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}"
        )
        assert "GitHub button has background" in combined

    def test_github_button_full_width(self):
        """
        Step 2i — The GitHub .auth-btn has the w-full (full-width) class.
        """
        result = _run_jest(test_name_pattern="GitHub button is full-width")
        combined = result.stdout + result.stderr
        assert result.returncode == 0, (
            f"GitHub full-width test FAILED (exit {result.returncode}).\n\n"
            f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}"
        )
        assert "GitHub button is full-width" in combined

    def test_github_button_svg_icon(self):
        """
        Step 2j — The GitHub button contains an SVG icon (GitHub mark).
        """
        result = _run_jest(test_name_pattern="GitHub button contains an SVG icon")
        combined = result.stdout + result.stderr
        assert result.returncode == 0, (
            f"GitHub SVG icon test FAILED (exit {result.returncode}).\n\n"
            f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}"
        )
        assert "GitHub button contains an SVG icon" in combined
