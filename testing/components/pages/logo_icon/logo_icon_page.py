"""LogoIconPage — Page Object for the LogoIcon SVG component.

Encapsulates all DOM interactions with the LogoIcon SVG element rendered
on a test fixture page. Follows the project's layered architecture:

    tests/ → components/ → frameworks/ → core/

All Playwright interactions are confined here so tests remain framework-agnostic.
"""
from __future__ import annotations

from playwright.sync_api import Page


class LogoIconPage:
    """Page Object for a page that renders the LogoIcon SVG component.

    Expects the SVG to be a direct child of ``#root``:

        <div id="root">
          <svg xmlns="…" viewBox="…" fill="…" aria-hidden="true">…</svg>
        </div>
    """

    _SVG_SELECTOR = "#root > svg"

    def __init__(self, page: Page) -> None:
        self._page = page

    def svg_count(self) -> int:
        """Return the number of <svg> elements inside #root."""
        return self._page.locator(self._SVG_SELECTOR).count()

    def get_view_box(self) -> str | None:
        """Return the ``viewBox`` attribute of the root SVG element."""
        return self._page.locator(self._SVG_SELECTOR).get_attribute("viewBox")

    def get_fill(self) -> str | None:
        """Return the ``fill`` attribute of the root SVG element."""
        return self._page.locator(self._SVG_SELECTOR).get_attribute("fill")
