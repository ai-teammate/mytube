"""
MYTUBE-434: Verify font cleanup — Geist font references are removed

Objective
---------
Ensure that all previous references to the Geist font have been removed from
the application styles.

Steps
-----
1. Open the application and view the page source or main CSS bundle.
2. Search for the string "Geist".
3. Inspect the font-family of the body and html tags.

Expected Result
---------------
No references to "Geist" are found in the CSS or rendered HTML, and the font
is not being loaded by the browser.

Test Approach
-------------
Two complementary strategies:

1. **Static source analysis** — scan every .css, .ts, .tsx, and .js file under
   web/src/ for the string "Geist" (case-insensitive).  Files in __tests__/
   are excluded because test assertions like ``not.toContain("geist")`` are
   allowed to mention the word.

2. **Jest rendered-HTML assertion** — delegates to the existing Jest test
   ``does NOT include Geist font variables in body className`` inside
   ``src/__tests__/app/layout.test.tsx``.  This runs the Next.js RootLayout
   through React Testing Library / jsdom and asserts that neither ``geist``
   nor ``--font-geist`` appear in the body className at runtime.

Run from repo root:
    pytest testing/tests/MYTUBE-434/test_mytube_434.py -v
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]   # …/mytube/
_WEB_SRC = _REPO_ROOT / "web" / "src"
_WEB_DIR = _REPO_ROOT / "web"

_LAYOUT_TEST_FILE = "__tests__/app/layout.test.tsx"
_GEIST_TEST_NAME = "does NOT include Geist font variables in body className"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _source_files() -> list[Path]:
    """Return all .css / .ts / .tsx / .js files under web/src/, excluding
    __tests__/ sub-trees so that test assertions mentioning "geist" are not
    flagged as false positives."""
    extensions = {".css", ".ts", ".tsx", ".js"}
    results = []
    for path in _WEB_SRC.rglob("*"):
        if path.suffix not in extensions:
            continue
        if "__tests__" in path.parts:
            continue
        results.append(path)
    return results


def _run_jest(test_name_pattern: str) -> subprocess.CompletedProcess:
    cmd = [
        "npm",
        "test",
        "--",
        f"--testPathPatterns={_LAYOUT_TEST_FILE}",
        f"--testNamePattern={test_name_pattern}",
        "--verbose",
        "--no-coverage",
        "--forceExit",
    ]
    return subprocess.run(
        cmd,
        cwd=str(_WEB_DIR),
        capture_output=True,
        text=True,
        timeout=120,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGeistFontRemoved:
    """MYTUBE-434: Geist font references must be absent from the application."""

    def test_no_geist_in_css_files(self):
        """
        Step 1-2 (static): scan every .css file under web/src/ for "Geist".
        The string must not appear in any stylesheet.
        """
        offending: list[str] = []
        for path in _source_files():
            if path.suffix != ".css":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "geist" in text.lower():
                rel = path.relative_to(_REPO_ROOT)
                offending.append(str(rel))

        assert not offending, (
            "The following CSS file(s) still contain 'Geist' references:\n"
            + "\n".join(f"  • {f}" for f in offending)
            + "\nAll Geist font references must be removed from stylesheets."
        )

    def test_no_geist_in_typescript_files(self):
        """
        Step 1-2 (static): scan every .ts and .tsx file under web/src/
        (excluding __tests__/) for "Geist".
        The string must not appear in any source module.
        """
        offending: list[str] = []
        for path in _source_files():
            if path.suffix not in {".ts", ".tsx"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "geist" in text.lower():
                rel = path.relative_to(_REPO_ROOT)
                offending.append(str(rel))

        assert not offending, (
            "The following TypeScript file(s) still contain 'Geist' references:\n"
            + "\n".join(f"  • {f}" for f in offending)
            + "\nAll Geist font references must be removed from the source."
        )

    def test_no_geist_in_layout_tsx(self):
        """
        Step 1-2 (targeted): directly verify that the root layout file
        web/src/app/layout.tsx does not import or reference Geist.
        """
        layout_path = _WEB_SRC / "app" / "layout.tsx"
        assert layout_path.exists(), f"layout.tsx not found at {layout_path}"
        text = layout_path.read_text(encoding="utf-8")
        assert "geist" not in text.lower(), (
            f"web/src/app/layout.tsx still references 'Geist'.\n"
            f"Relevant content:\n"
            + "\n".join(
                f"  line {i+1}: {line.rstrip()}"
                for i, line in enumerate(text.splitlines())
                if "geist" in line.lower()
            )
        )

    def test_body_does_not_use_geist_font_class(self):
        """
        Step 3 (dynamic via Jest + jsdom): render RootLayout and assert that
        the <body> element's className does not contain 'geist' or
        '--font-geist'.  Delegates to the existing Jest test in
        src/__tests__/app/layout.test.tsx.
        """
        result = _run_jest(_GEIST_TEST_NAME)
        combined = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"Jest test '{_GEIST_TEST_NAME}' FAILED (exit code {result.returncode}).\n\n"
            f"=== STDOUT ===\n{result.stdout}\n\n"
            f"=== STDERR ===\n{result.stderr}"
        )

        assert result.stdout or result.stderr, (
            f"Jest produced no output for test '{_GEIST_TEST_NAME}'."
        )
