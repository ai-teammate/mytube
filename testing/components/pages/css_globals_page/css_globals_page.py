"""
CSSGlobalsPage component — reads CSS custom properties from the application's
global stylesheet (web/src/app/globals.css) without requiring a browser.

Parses the :root block to extract light-theme token values. Any dark-theme
overrides inside ``body[data-theme="dark"]`` are intentionally ignored so that
only the default (light) values are returned.
"""
from __future__ import annotations

import pathlib
import re

# Absolute path to the global stylesheet, resolved relative to this file so
# the component works regardless of where tests are invoked from.
_GLOBALS_CSS: pathlib.Path = (
    pathlib.Path(__file__).parents[4] / "web" / "src" / "app" / "globals.css"
)


def _extract_root_block(css_text: str) -> str:
    """Return the content of the first :root { ... } block in *css_text*.

    Stops at the first closing brace after ``:root {`` so that dark-theme
    overrides in later rule-sets are excluded.
    """
    match = re.search(r":root\s*\{([^}]*)\}", css_text, re.DOTALL)
    if not match:
        return ""
    return match.group(1)


class CSSGlobalsPage:
    """Component for querying CSS design-token values from globals.css.

    Reads the stylesheet once on construction. Call :meth:`get_light_token`
    to retrieve the value of any CSS custom property defined in the ``:root``
    block (light theme only — dark-theme overrides are excluded).

    Example::

        css = CSSGlobalsPage()
        assert css.get_light_token("--bg-page") == "#f8f9fa"
    """

    def __init__(self, css_path: pathlib.Path = _GLOBALS_CSS) -> None:
        self._css_path = css_path
        self._root_block: str = _extract_root_block(css_path.read_text())

    def get_light_token(self, var_name: str) -> str:
        """Return the trimmed value of *var_name* from the :root block.

        Raises ``AssertionError`` when the variable is not found so tests
        produce an informative failure message.
        """
        pattern = re.compile(
            rf"{re.escape(var_name)}\s*:\s*([^;]+);",
            re.DOTALL,
        )
        match = pattern.search(self._root_block)
        assert match, (
            f"{var_name} not found in the :root block of {self._css_path}. "
            "The token may be missing or the CSS file structure has changed."
        )
        return match.group(1).strip()
