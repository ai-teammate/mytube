"""
MYTUBE-423: Icon library structure — directory and index file created correctly.

Objective:
    Verify that the icons directory and the central export file are correctly
    initialized under web/src/components/.

Test steps:
    1. Navigate to the web/src/components/ directory.
    2. Verify the existence of the icons/ folder.
    3. Verify the existence of web/src/components/icons/index.ts.

Expected Result:
    The directory and the central index file exist to serve as a single source
    of truth for assets.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)

COMPONENTS_DIR = os.path.join(REPO_ROOT, "web", "src", "components")
ICONS_DIR = os.path.join(COMPONENTS_DIR, "icons")
ICONS_INDEX = os.path.join(ICONS_DIR, "index.ts")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_components_directory_exists():
    """Step 1: The web/src/components/ directory must exist."""
    assert os.path.isdir(COMPONENTS_DIR), (
        f"Expected components directory at {COMPONENTS_DIR!r} but it was not found."
    )


def test_icons_directory_exists():
    """Step 2: The icons/ folder must exist inside web/src/components/."""
    assert os.path.isdir(ICONS_DIR), (
        f"Expected icons directory at {ICONS_DIR!r} but it was not found."
    )


def test_icons_index_file_exists():
    """Step 3: web/src/components/icons/index.ts must exist."""
    assert os.path.isfile(ICONS_INDEX), (
        f"Expected index file at {ICONS_INDEX!r} but it was not found."
    )
