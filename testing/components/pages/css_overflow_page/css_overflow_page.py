"""
CSSOverflowPage component — reads overflow-related CSS properties from the
application's global stylesheet (web/src/app/globals.css) without requiring
a browser.

Parses arbitrary selector rule blocks (not just ``:root``) to allow inspection
of element-level overflow declarations such as ``.page-wrap`` and ``.shell``.
"""
from __future__ import annotations

import pathlib
import re

_GLOBALS_CSS: pathlib.Path = (
    pathlib.Path(__file__).parents[4] / "web" / "src" / "app" / "globals.css"
)


def _strip_css_comments(text: str) -> str:
    """Remove all /* ... */ CSS comments from *text*."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


class CSSOverflowPage:
    """Component for querying overflow CSS properties from globals.css.

    Reads the stylesheet once on construction and exposes
    :meth:`get_rule_block_property` for extracting the value of any CSS
    property from any selector rule block.

    Example::

        css = CSSOverflowPage()
        assert css.get_rule_block_property(".shell", "overflow") == "clip"
        assert css.get_rule_block_property(".page-wrap", "overflow-x") == "clip"
    """

    def __init__(self, css_path: pathlib.Path = _GLOBALS_CSS) -> None:
        self._css_path = css_path
        self._clean_css: str = _strip_css_comments(css_path.read_text(encoding="utf-8"))

    def get_rule_block(self, selector: str) -> str:
        """Return the raw content of the first CSS rule block for *selector*.

        Returns an empty string when the selector is not found.
        """
        pattern = re.compile(
            rf"{re.escape(selector)}\s*\{{([^}}]*)\}}",
            re.DOTALL,
        )
        match = pattern.search(self._clean_css)
        return match.group(1) if match else ""

    def get_rule_block_property(self, selector: str, property_name: str) -> str:
        """Return the trimmed value of *property_name* within *selector*'s rule block.

        Uses a negative lookbehind to avoid matching sub-properties (e.g.
        ``overflow-x`` when searching for ``overflow``).

        Returns an empty string when the selector or property is not found.
        """
        block = self.get_rule_block(selector)
        if not block:
            return ""
        pattern = re.compile(
            rf"(?<![a-z-]){re.escape(property_name)}\s*:\s*([^;]+);",
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(block)
        return match.group(1).strip() if match else ""
