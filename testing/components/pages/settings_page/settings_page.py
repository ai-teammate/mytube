"""SettingsPage — Page Object for the /settings page of the MyTube web application.

Encapsulates all interactions with the Account Settings form, including the
AvatarPreview component, exposing only high-level actions and state queries.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — the caller provides the full settings URL.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from __future__ import annotations

from playwright.sync_api import Page


class SettingsPage:
    """Page Object for the MyTube Account Settings page (/settings)."""

    # Selectors
    _AVATAR_URL_INPUT = 'input[id="avatar_url"]'
    _USERNAME_INPUT = 'input[id="username"]'

    # AvatarPreview selectors
    _AVATAR_PREVIEW_CONTAINER = '[role="img"][aria-label="Avatar preview"]'
    _AVATAR_PREVIEW_IMG = '[role="img"][aria-label="Avatar preview"] img'
    _AVATAR_PREVIEW_SVG = '[role="img"][aria-label="Avatar preview"] svg'

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, url: str) -> None:
        """Navigate to the settings page URL and wait for it to load."""
        self._page.goto(url, wait_until="domcontentloaded")
        self._page.wait_for_load_state("networkidle")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def fill_avatar_url(self, url: str) -> None:
        """Clear the Avatar URL input and type *url* into it."""
        self._page.wait_for_selector(self._AVATAR_URL_INPUT, timeout=15_000)
        self._page.fill(self._AVATAR_URL_INPUT, url)

    def clear_avatar_url(self) -> None:
        """Clear the Avatar URL input field."""
        self._page.fill(self._AVATAR_URL_INPUT, "")

    # ------------------------------------------------------------------
    # AvatarPreview state queries
    # ------------------------------------------------------------------

    def is_avatar_preview_container_visible(self, timeout: float = 10_000) -> bool:
        """Return True if the AvatarPreview container div is visible."""
        locator = self._page.locator(self._AVATAR_PREVIEW_CONTAINER)
        try:
            locator.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def is_avatar_img_present(self) -> bool:
        """Return True if the <img> element is present inside the AvatarPreview container."""
        return self._page.locator(self._AVATAR_PREVIEW_IMG).count() > 0

    def is_avatar_svg_placeholder_visible(self, timeout: float = 10_000) -> bool:
        """Return True if the SVG placeholder is visible inside the AvatarPreview container.

        The SVG is shown when the image URL is empty or fails to load.
        """
        locator = self._page.locator(self._AVATAR_PREVIEW_SVG)
        try:
            locator.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def wait_for_avatar_error_fallback(self, timeout: float = 15_000) -> None:
        """Wait until the AvatarPreview switches to the SVG fallback state.

        This happens when the browser fires onError on the <img> element,
        which sets React state error=true, removes the <img> and renders the SVG.
        """
        self._page.wait_for_selector(
            self._AVATAR_PREVIEW_SVG,
            state="visible",
            timeout=timeout,
        )

    def is_avatar_preview_container_has_bg_gray(self) -> bool:
        """Return True if the AvatarPreview container has the expected grey background."""
        container = self._page.locator(self._AVATAR_PREVIEW_CONTAINER).first
        classes: str = container.get_attribute("class") or ""
        return "bg-gray-200" in classes

    def is_settings_page_loaded(self, timeout: float = 20_000) -> bool:
        """Return True if the settings page title/heading is visible."""
        try:
            self._page.wait_for_selector(
                'h1:has-text("Account settings")',
                timeout=timeout,
            )
            return True
        except Exception:
            return False

    def get_avatar_url_value(self) -> str:
        """Return the current value of the Avatar URL input."""
        return self._page.input_value(self._AVATAR_URL_INPUT)
