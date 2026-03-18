"""
PlaylistCSSModule component — parses CSS rules from PlaylistPageClient.module.css
without requiring a running browser or server.

Provides typed query methods for inspecting the playlist page's CSS module so
that tests remain decoupled from the file system and parsing implementation.
"""
from __future__ import annotations

import pathlib
import re

_PLAYLIST_CSS: pathlib.Path = (
    pathlib.Path(__file__).parents[4]
    / "web"
    / "src"
    / "app"
    / "pl"
    / "[id]"
    / "PlaylistPageClient.module.css"
)


def _normalise(value: str) -> str:
    """Collapse whitespace and lowercase *value* for loose comparison."""
    return re.sub(r"\s+", " ", value).strip().lower()


class PlaylistCSSModule:
    """Component for querying CSS rules from PlaylistPageClient.module.css.

    Reads the stylesheet once on construction and exposes typed helpers for
    inspecting the design-token usage across the playlist page layout classes.

    Example::

        css = PlaylistCSSModule()
        assert css.rule_contains("page", "var(--bg-page)")
    """

    def __init__(self, css_path: pathlib.Path = _PLAYLIST_CSS) -> None:
        self._css_path = css_path
        self._css_text = css_path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def file_exists(self) -> bool:
        """Return True when the CSS module file exists on disk."""
        return self._css_path.exists()

    def get_rule_body(self, class_name: str) -> str:
        """Return the normalised declaration block for *.class_name* rule.

        Returns an empty string when the rule is not found.
        """
        pattern = rf"\.{re.escape(class_name)}\s*\{{([^}}]*)\}}"
        match = re.search(pattern, self._css_text, re.DOTALL | re.IGNORECASE)
        return _normalise(match.group(1)) if match else ""

    def rule_contains(self, class_name: str, snippet: str) -> bool:
        """Return True when the normalised rule body for *class_name* contains *snippet*."""
        return snippet.lower() in self.get_rule_body(class_name)

    def file_contains(self, snippet: str) -> bool:
        """Return True when *snippet* appears anywhere in the stylesheet text."""
        return snippet in self._css_text

    def file_contains_ignorecase(self, snippet: str) -> bool:
        """Return True when *snippet* appears anywhere in the stylesheet (case-insensitive)."""
        return snippet.lower() in self._css_text.lower()
