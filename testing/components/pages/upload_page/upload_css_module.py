"""
UploadCSSModule component — parses CSS rules from upload.module.css without
requiring a running browser or server.

Provides typed query methods for inspecting the upload page's CSS module so
that tests remain decoupled from the file system and parsing implementation.
"""
from __future__ import annotations

import pathlib
import re

_UPLOAD_CSS: pathlib.Path = (
    pathlib.Path(__file__).parents[4] / "web" / "src" / "app" / "upload" / "upload.module.css"
)


def _normalise(value: str) -> str:
    """Collapse whitespace and lowercase *value* for loose comparison."""
    return re.sub(r"\s+", " ", value).strip().lower()


def _extract_rule(css: str, selector_fragment: str, css_path: pathlib.Path) -> str:
    """Return the declaration block of the first rule whose selector contains *selector_fragment*.

    Raises ``AssertionError`` with an informative message when the rule is not found.
    """
    pattern = rf"\.{re.escape(selector_fragment)}\s*\{{([^}}]*)\}}"
    match = re.search(pattern, css, re.DOTALL | re.IGNORECASE)
    if not match:
        raise AssertionError(
            f"CSS rule for '.{selector_fragment}' not found in {css_path.name}."
        )
    return match.group(1)


class UploadCSSModule:
    """Component for querying CSS rules from upload.module.css.

    Reads the stylesheet once on construction and exposes typed helpers for
    each CSS class relevant to the progress bar redesign.

    Example::

        css = UploadCSSModule()
        assert css.get_property("progressShell", "background") is not None
    """

    def __init__(self, css_path: pathlib.Path = _UPLOAD_CSS) -> None:
        self._css_path = css_path
        self._css_text = css_path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def get_rule_body(self, selector_fragment: str) -> str:
        """Return the raw (normalised) declaration block for *selector_fragment*."""
        raw = _extract_rule(self._css_text, selector_fragment, self._css_path)
        return _normalise(raw)

    def rule_contains(self, selector_fragment: str, snippet: str) -> bool:
        """Return True when the normalised rule body contains *snippet*."""
        return snippet.lower() in self.get_rule_body(selector_fragment)

    def file_exists(self) -> bool:
        """Return True when the CSS module file exists on disk."""
        return self._css_path.exists()

    # ------------------------------------------------------------------
    # Pseudo-element helpers
    # ------------------------------------------------------------------

    def get_pseudo_element_rule_body(self, pseudo_element: str) -> str:
        """Return the normalised declaration block for a ::pseudo-element rule.

        Returns an empty string when the rule is not found.
        """
        pattern = rf"{re.escape(pseudo_element)}\s*\{{([^}}]*)\}}"
        match = re.search(pattern, self._css_text, re.DOTALL | re.IGNORECASE)
        return _normalise(match.group(1)) if match else ""

    def pseudo_element_rule_exists(self, pseudo_element: str) -> bool:
        """Return True when a rule for *pseudo_element* exists in the stylesheet."""
        return bool(self.get_pseudo_element_rule_body(pseudo_element))
