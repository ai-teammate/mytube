"""
MYTUBE-429: Icon rendering without props — component renders with default behaviour.

Objective:
    Verify that the DecorCamera icon component does not crash and renders a valid
    SVG element successfully when no optional props are provided.

Test steps:
    1. Render <DecorCamera /> without passing any props.
    2. Observe the component output and console for errors.

Expected result:
    The component renders a valid <svg> element without any runtime errors.

Test structure:
    Delegates to the Jest + React Testing Library suite in
    web/src/__tests__/components/icons/icons.test.tsx, running only the
    "DecorCamera" describe block which covers all no-props rendering scenarios:
      - renders an <svg> element
      - has viewBox 0 0 120 120
      - has fill=currentColor
      - defaults to aria-hidden=true

Run from the repo root:
    pytest testing/tests/MYTUBE-429/test_mytube_429.py -v
"""

import os
import subprocess
import sys

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)

WEB_DIR = os.path.join(REPO_ROOT, "web")

JEST_TEST_FILE = os.path.join(
    WEB_DIR,
    "src",
    "__tests__",
    "components",
    "icons",
    "icons.test.tsx",
)

# Filter to the DecorCamera describe block only
JEST_TEST_NAME_PATTERN = "DecorCamera"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _npm_available() -> bool:
    result = subprocess.run(
        ["npm", "--version"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _node_modules_present() -> bool:
    return os.path.isdir(os.path.join(WEB_DIR, "node_modules"))


def _run_jest() -> subprocess.CompletedProcess:
    """Run the DecorCamera Jest tests from the web/ directory."""
    cmd = [
        "npm",
        "test",
        "--",
        f"--testPathPatterns={os.path.relpath(JEST_TEST_FILE, WEB_DIR)}",
        f"--testNamePattern={JEST_TEST_NAME_PATTERN}",
        "--verbose",
        "--no-coverage",
        "--forceExit",
    ]
    return subprocess.run(
        cmd,
        cwd=WEB_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _npm_available(), reason="npm is not available")
@pytest.mark.skipif(
    not _node_modules_present(),
    reason="web/node_modules not installed — run `npm install` inside web/",
)
class TestDecorCameraRenderingWithoutProps:
    """Verify DecorCamera renders a valid SVG when rendered without props."""

    def test_decor_camera_renders_svg_without_props(self):
        """
        Render <DecorCamera /> with no props.
        Assert it produces a valid <svg> element without crashing.
        """
        result = _run_jest()
        stdout = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"Jest tests for DecorCamera failed (exit code {result.returncode}).\n\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )

        # Confirm that at least the "renders an <svg> element" test passed
        assert "renders an <svg> element" in stdout, (
            "Expected Jest output to mention 'renders an <svg> element' but it was not "
            f"found in the output:\n{stdout}"
        )
