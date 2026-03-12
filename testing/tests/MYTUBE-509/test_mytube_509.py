"""
MYTUBE-509: Progress bar redesign styling — green gradient and rounded track

Objective
---------
Verify the visual appearance of the progress bar matches the redesign
specifications (gradient fill and height).

Steps
-----
1. Observe the progress bar shell (.progressShell / .progress-shell).
2. Inspect the fill element style while upload is active.

Expected Result
---------------
* The track background is rgba(127, 127, 127, 0.18).
* The fill uses a gradient from var(--accent-cta) to var(--accent-cta-end).
* The bar height is exactly 10px with a border-radius of 999px.

Test Approach
-------------
Static analysis — delegates to UploadCSSModule (for upload.module.css) and
CSSGlobalsPage (for globals.css) components.  This verifies the implementation
without requiring a running server.

Run from repo root:
    pytest testing/tests/MYTUBE-509/test_mytube_509.py -v
"""
from __future__ import annotations

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.pages.upload_page.upload_css_module import UploadCSSModule
from testing.components.pages.css_globals_page.css_globals_page import CSSGlobalsPage


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProgressBarCSSModule:
    """MYTUBE-509 (Static): Verify upload.module.css contains the redesign styles."""

    # -- Step 1: progress shell / track ----------------------------------------

    def test_upload_css_exists(self) -> None:
        """upload.module.css must exist at the expected path."""
        css = UploadCSSModule()
        assert css.file_exists(), (
            "upload.module.css not found at the expected path. "
            "The progress bar styles are expected to live in this file."
        )

    def test_progress_shell_background(self) -> None:
        """Step 1 — .progressShell background must be rgba(127,127,127,0.18)."""
        css = UploadCSSModule()
        rule = css.get_rule_body("progressShell")
        assert (
            "rgba(127, 127, 127, 0.18)" in rule or "rgba(127,127,127,0.18)" in rule
        ), (
            f".progressShell background is not set to rgba(127,127,127,0.18).\n"
            f"Rule body found:\n{rule}"
        )

    def test_progress_shell_height(self) -> None:
        """Step 1 — .progressShell height must be exactly 10px."""
        css = UploadCSSModule()
        assert css.rule_contains("progressShell", "height: 10px"), (
            f".progressShell height is not '10px'.\n"
            f"Rule body found:\n{css.get_rule_body('progressShell')}"
        )

    def test_progress_shell_border_radius(self) -> None:
        """Step 1 — .progressShell border-radius must be 999px."""
        css = UploadCSSModule()
        assert css.rule_contains("progressShell", "border-radius: 999px"), (
            f".progressShell border-radius is not '999px'.\n"
            f"Rule body found:\n{css.get_rule_body('progressShell')}"
        )

    # -- Step 2: progress fill / gradient --------------------------------------

    def test_progress_fill_uses_gradient(self) -> None:
        """Step 2 — .progressFill background must use a linear-gradient."""
        css = UploadCSSModule()
        assert css.rule_contains("progressFill", "linear-gradient"), (
            f".progressFill background does not use linear-gradient.\n"
            f"Rule body found:\n{css.get_rule_body('progressFill')}"
        )

    def test_progress_fill_gradient_uses_accent_cta(self) -> None:
        """Step 2 — .progressFill gradient must reference var(--accent-cta)."""
        css = UploadCSSModule()
        assert css.rule_contains("progressFill", "var(--accent-cta)"), (
            f".progressFill gradient does not reference var(--accent-cta).\n"
            f"Rule body found:\n{css.get_rule_body('progressFill')}"
        )

    def test_progress_fill_gradient_uses_accent_cta_end(self) -> None:
        """Step 2 — .progressFill gradient must reference var(--accent-cta-end)."""
        css = UploadCSSModule()
        assert css.rule_contains("progressFill", "var(--accent-cta-end)"), (
            f".progressFill gradient does not reference var(--accent-cta-end).\n"
            f"Rule body found:\n{css.get_rule_body('progressFill')}"
        )

    def test_progress_fill_height_full(self) -> None:
        """Step 2 — .progressFill height must be 100% (fills the shell)."""
        css = UploadCSSModule()
        assert css.rule_contains("progressFill", "height: 100%"), (
            f".progressFill height is not '100%'.\n"
            f"Rule body found:\n{css.get_rule_body('progressFill')}"
        )

    # -- globals.css CSS variable definitions ----------------------------------

    def test_globals_css_defines_accent_cta(self) -> None:
        """globals.css :root must define --accent-cta used by the fill gradient."""
        css_globals = CSSGlobalsPage()
        assert css_globals.get_light_token("--accent-cta") is not None, (
            "globals.css does not define --accent-cta. "
            "This CSS variable is required by the progress fill gradient."
        )

    def test_globals_css_defines_accent_cta_end(self) -> None:
        """globals.css :root must define --accent-cta-end used by the fill gradient."""
        css_globals = CSSGlobalsPage()
        assert css_globals.get_light_token("--accent-cta-end") is not None, (
            "globals.css does not define --accent-cta-end. "
            "This CSS variable is required by the progress fill gradient."
        )
