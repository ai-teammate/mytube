"""SettingsPage — Page Object for the /settings page of the MyTube web application.

Encapsulates all interactions with the Account Settings form, exposing only
high-level actions and state queries to callers.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — the caller provides the base URL.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from __future__ import annotations

from playwright.sync_api import Page


class SettingsPage:
    """Page Object for the MyTube Account Settings page (/settings)."""

    _AVATAR_URL_INPUT = "#avatar_url"
    _USERNAME_INPUT = "#username"
    _SAVE_BUTTON = 'button[type="submit"]'
    _AVATAR_PREVIEW_WRAPPER = '[role="img"][aria-label="Avatar preview"]'
    _AVATAR_PREVIEW_IMG = '[role="img"][aria-label="Avatar preview"] img'

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, base_url: str) -> None:
        """Navigate to /settings and wait for the page to be interactive."""
        url = f"{base_url.rstrip('/')}/settings/"
        self._page.goto(url, wait_until="domcontentloaded")
        # Wait for the form to appear (auth guard may redirect then back).
        self._page.wait_for_selector(self._AVATAR_URL_INPUT, timeout=30_000)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def fill_avatar_url(self, url: str) -> None:
        """Clear the Avatar URL input and type *url* into it."""
        self._page.fill(self._AVATAR_URL_INPUT, url)

    # ------------------------------------------------------------------
    # State queries — avatar preview
    # ------------------------------------------------------------------

    def wait_for_avatar_preview(self, timeout: int = 15_000) -> None:
        """Block until the avatar preview <img> element is visible."""
        self._page.wait_for_selector(self._AVATAR_PREVIEW_IMG, state="visible", timeout=timeout)

    def is_avatar_preview_visible(self) -> bool:
        """Return True if the avatar preview <img> element is visible."""
        locator = self._page.locator(self._AVATAR_PREVIEW_IMG)
        return locator.count() > 0 and locator.first.is_visible()

    def get_avatar_preview_src(self) -> str:
        """Return the src attribute of the preview <img> element, or empty string."""
        return self._page.evaluate(
            """() => {
                const img = document.querySelector('[role="img"][aria-label="Avatar preview"] img');
                return img ? (img.getAttribute('src') || '') : '';
            }"""
        )

    def get_avatar_preview_classes(self) -> str:
        """Return the class attribute of the preview <img> element."""
        return self._page.evaluate(
            """() => {
                const img = document.querySelector('[role="img"][aria-label="Avatar preview"] img');
                return img ? (img.getAttribute('class') || '') : '';
            }"""
        )

    def get_avatar_preview_computed_size(self) -> tuple[float, float]:
        """Return (width, height) in pixels as computed by the browser."""
        result: list = self._page.evaluate(
            """() => {
                const img = document.querySelector('[role="img"][aria-label="Avatar preview"] img');
                if (!img) return [0, 0];
                const r = img.getBoundingClientRect();
                return [r.width, r.height];
            }"""
        )
        return float(result[0]), float(result[1])

    def get_avatar_wrapper_computed_border_radius(self) -> str:
        """Return the computed border-radius of the avatar preview wrapper."""
        return self._page.evaluate(
            """() => {
                const el = document.querySelector('[role="img"][aria-label="Avatar preview"]');
                if (!el) return '';
                return window.getComputedStyle(el).borderRadius;
            }"""
        )

    def get_avatar_img_object_fit(self) -> str:
        """Return the computed object-fit CSS property of the preview <img>."""
        return self._page.evaluate(
            """() => {
                const img = document.querySelector('[role="img"][aria-label="Avatar preview"] img');
                if (!img) return '';
                return window.getComputedStyle(img).objectFit;
            }"""
        )
