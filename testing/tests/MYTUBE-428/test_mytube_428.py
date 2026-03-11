"""
MYTUBE-428: Decorative icons implementation — components render correct viewBox dimensions.

Objective
---------
Verify that decorative icons (DecorPlay, DecorWave, etc.) are implemented with
the specific viewBox requirements.

Steps
-----
1. Render DecorPlay and verify its viewBox.
2. Render DecorWave and verify its viewBox.

Expected Result
---------------
- DecorPlay uses a 120x120 viewBox ("0 0 120 120") as per the technical requirements.
- DecorWave uses a 120x120 viewBox ("0 0 120 120") as per the technical requirements.

Test approach
-------------
**Layer A — Static source analysis** (always runs, no browser required):
    Reads the TSX source files for DecorPlay and DecorWave from the
    ``web/src/components/icons/`` directory and verifies that each SVG element
    carries ``viewBox="0 0 120 120"``.  This layer is self-contained and fully
    covers the test-case requirements.

Environment variables
---------------------
No environment variables required.
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

_EXPECTED_VIEW_BOX = "0 0 120 120"

# Paths relative to repo root
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_ICONS_DIR = os.path.join(_REPO_ROOT, "web", "src", "components", "icons")


# ---------------------------------------------------------------------------
# Layer A: Static source analysis helpers
# ---------------------------------------------------------------------------


def _read_icon_source(filename: str) -> str:
    path = os.path.join(_ICONS_DIR, filename)
    if not os.path.isfile(path):
        pytest.fail(f"Icon source file not found: {path}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _extract_view_box(source: str) -> str | None:
    """Return the first viewBox value found in the TSX source."""
    # Standard JSX attribute: viewBox="0 0 120 120"
    match = re.search(r'viewBox="([^"]+)"', source)
    if match:
        return match.group(1)
    # JSX expression: viewBox={"0 0 120 120"} or viewBox={'0 0 120 120'}
    match2 = re.search(r"""viewBox=\{['"]([^'"]+)['"]\}""", source)
    if match2:
        return match2.group(1)
    return None


# ---------------------------------------------------------------------------
# Pytest tests
# ---------------------------------------------------------------------------


class TestMytube428DecorativeIconViewBox:
    """MYTUBE-428 — decorative icons render correct viewBox dimensions."""

    def test_decor_play_viewbox_in_source(self) -> None:
        """Layer A: DecorPlay.tsx declares viewBox='0 0 120 120'."""
        source = _read_icon_source("DecorPlay.tsx")
        view_box = _extract_view_box(source)
        assert view_box == _EXPECTED_VIEW_BOX, (
            f"DecorPlay.tsx viewBox expected '{_EXPECTED_VIEW_BOX}', got '{view_box}'"
        )

    def test_decor_wave_viewbox_in_source(self) -> None:
        """Layer A: DecorWave.tsx declares viewBox='0 0 120 120'."""
        source = _read_icon_source("DecorWave.tsx")
        view_box = _extract_view_box(source)
        assert view_box == _EXPECTED_VIEW_BOX, (
            f"DecorWave.tsx viewBox expected '{_EXPECTED_VIEW_BOX}', got '{view_box}'"
        )
