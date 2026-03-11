"""
MYTUBE-427: Icon library exports — all required icons available from index.ts

Objective
---------
Verify that all seven specific icons defined in the story scope are exported
from the library's entry point: web/src/components/icons/index.ts

Steps
-----
1. Open web/src/components/icons/index.ts.
2. Check for the export of: LogoIcon, DecorPlay, DecorFilm, DecorCamera,
   DecorWave, SunIcon, and MoonIcon.

Expected Result
---------------
All components are correctly exported, making them available for consistent
import across the codebase.

Test approach
-------------
Static source-code analysis: read the index.ts file and assert that each
required icon name appears as a named export.
"""
import os
import re

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ICONS_INDEX_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "web",
    "src",
    "components",
    "icons",
    "index.ts",
)

REQUIRED_ICONS = [
    "LogoIcon",
    "DecorPlay",
    "DecorFilm",
    "DecorCamera",
    "DecorWave",
    "SunIcon",
    "MoonIcon",
]

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_icons_index_file_exists():
    """The icons index.ts entry point must exist."""
    assert os.path.isfile(ICONS_INDEX_PATH), (
        f"icons/index.ts not found at expected path: {ICONS_INDEX_PATH}"
    )


@pytest.mark.parametrize("icon_name", REQUIRED_ICONS)
def test_icon_exported(icon_name):
    """Each required icon must have a named export in index.ts."""
    with open(ICONS_INDEX_PATH, encoding="utf-8") as fh:
        content = fh.read()

    # Match patterns like:
    #   export { default as IconName }
    #   export { IconName }
    #   export * from "./IconName"   (re-export by file name)
    #   export type { IconName }
    export_pattern = re.compile(
        rf"""
        (?:
            export\s+\{{[^}}]*\b{re.escape(icon_name)}\b[^}}]*\}}   # named export block
            |
            export\s+\*\s+from\s+['"][^'"]*{re.escape(icon_name)}['"]  # star re-export
            |
            export\s+(?:default\s+)?(?:const|class|function|type|interface)\s+{re.escape(icon_name)}\b  # direct export
        )
        """,
        re.VERBOSE,
    )

    assert export_pattern.search(content), (
        f"'{icon_name}' is not exported from icons/index.ts.\n"
        f"File contents:\n{content}"
    )
