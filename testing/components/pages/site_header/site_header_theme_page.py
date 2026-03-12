"""
Page object for theme toggle testing of the SiteHeader component.
"""
from __future__ import annotations

from playwright.sync_api import Page

_PAGE_LOAD_TIMEOUT = 30_000   # ms


class SiteHeaderThemePage:
    """Page object for the theme toggle section of SiteHeader.

    Wraps all selectors and JavaScript evaluation so test assertions remain
    framework-agnostic and readable.
    """

    # The theme toggle button is the only <button> inside the header's
    # utility area that carries an `aria-label` starting with "Switch to".
    _TOGGLE_BTN = "header button[aria-label^='Switch to']"

    def __init__(self, page: Page) -> None:
        self._page = page

    def navigate(self, base_url: str) -> None:
        url = f"{base_url.rstrip('/')}/"
        self._page.goto(url, timeout=_PAGE_LOAD_TIMEOUT, wait_until="networkidle")
        self._page.wait_for_selector(self._TOGGLE_BTN, timeout=_PAGE_LOAD_TIMEOUT)

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def button_bounding_box(self) -> dict:
        """Return {width, height} of the toggle button via getBoundingClientRect."""
        return self._page.evaluate(
            """() => {
                const btn = document.querySelector("header button[aria-label^='Switch to']");
                if (!btn) return null;
                const r = btn.getBoundingClientRect();
                return { width: r.width, height: r.height };
            }"""
        )

    def button_is_circular(self) -> bool:
        """Return True when computed border-radius makes the button a circle."""
        return self._page.evaluate(
            """() => {
                const btn = document.querySelector("header button[aria-label^='Switch to']");
                if (!btn) return false;
                const cs = window.getComputedStyle(btn);
                // rounded-full produces border-radius: 9999px (or 50%).
                // A circle requires all four corners to be >= half the element size.
                const radius = parseFloat(cs.borderTopLeftRadius);
                const size   = parseFloat(cs.width);
                return radius >= size / 2;
            }"""
        )

    # ------------------------------------------------------------------
    # Icon presence helpers
    # ------------------------------------------------------------------

    def _svg_inside_button(self) -> str | None:
        """Return the innerHTML of the <svg> inside the toggle button."""
        return self._page.evaluate(
            """() => {
                const btn = document.querySelector("header button[aria-label^='Switch to']");
                if (!btn) return null;
                const svg = btn.querySelector('svg');
                return svg ? svg.innerHTML : null;
            }"""
        )

    def current_theme(self) -> str:
        """Return the value of body[data-theme], defaulting to 'light'."""
        return self._page.evaluate(
            "() => document.body.getAttribute('data-theme') || 'light'"
        )

    def has_moon_icon(self) -> bool:
        """Return True when the MoonIcon crescent-path SVG is inside the button."""
        inner = self._svg_inside_button()
        if not inner:
            return False
        # MoonIcon uses a single <path d="M21 12.79…">
        return "M21 12.79" in inner

    def has_sun_icon(self) -> bool:
        """Return True when the SunIcon (central circle + rays) is inside the button."""
        inner = self._svg_inside_button()
        if not inner:
            return False
        # SunIcon uses <circle cx="12" cy="12" r="4" /> plus line rays.
        return 'cx="12"' in inner and 'cy="12"' in inner

    # ------------------------------------------------------------------
    # Interaction helpers
    # ------------------------------------------------------------------

    def toggle_theme(self) -> None:
        """Click the theme toggle button."""
        self._page.locator(self._TOGGLE_BTN).click()
        # Wait for React re-render (icon swap is synchronous but we give the
        # browser one animation frame to apply the DOM update).
        self._page.wait_for_timeout(300)

    def force_light_theme(self) -> None:
        """Set localStorage + body attribute to light and reload if needed."""
        self._page.evaluate(
            """() => {
                localStorage.setItem('theme', 'light');
                document.body.setAttribute('data-theme', 'light');
            }"""
        )
        self._page.wait_for_timeout(200)

    def force_dark_theme(self) -> None:
        """Set localStorage + body attribute to dark and reload if needed."""
        self._page.evaluate(
            """() => {
                localStorage.setItem('theme', 'dark');
                document.body.setAttribute('data-theme', 'dark');
            }"""
        )
        self._page.wait_for_timeout(200)
