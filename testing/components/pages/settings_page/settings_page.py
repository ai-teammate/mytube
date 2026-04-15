"""SettingsPage — Page Object for the /settings page of the MyTube web application.

Encapsulates all interactions with the Account Settings form, exposing only
high-level actions and state queries to callers.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — the caller provides the settings URL.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from __future__ import annotations

from playwright.sync_api import Page


class SettingsPage:
    """Page Object for the MyTube Account Settings page (/settings)."""

    _AVATAR_URL_INPUT = 'input[id="avatar_url"]'
    _AVATAR_PREVIEW_CONTAINER = '[role="img"][aria-label="Avatar preview"]'
    _AVATAR_PREVIEW_IMG = '[role="img"][aria-label="Avatar preview"] img'
    _USERNAME_INPUT = 'input[id="username"]'
    _LOADING_TEXT = "Loading\u2026"

    def __init__(self, page: Page) -> None:
        self._page = page

    def navigate(self, settings_url: str) -> None:
        """Navigate to the settings URL and wait for the form to be ready."""
        self._page.goto(settings_url, wait_until="domcontentloaded")
        # Wait for RequireAuth to pass through (loading spinner gone)
        try:
            self._page.wait_for_selector(
                f"text={self._LOADING_TEXT}", state="hidden", timeout=20_000
            )
        except Exception:
            pass
        # Wait for avatar URL input to appear (confirms settings form is rendered)
        self._page.wait_for_selector(self._AVATAR_URL_INPUT, timeout=20_000)

    def fill_avatar_url(self, url: str) -> None:
        """Clear the Avatar URL field and replace its content with *url*.

        Uses Playwright's locator.fill() which sets the value atomically and
        dispatches the input event that React's synthetic onChange system picks up.
        """
        self._page.locator(self._AVATAR_URL_INPUT).fill(url)

    def get_avatar_url_input_value(self) -> str:
        """Return the current value of the Avatar URL input field."""
        return self._page.input_value(self._AVATAR_URL_INPUT)

    def is_avatar_preview_container_visible(self, timeout: float = 5_000) -> bool:
        """Return True when the avatar preview container (role=img) is visible."""
        try:
            self._page.wait_for_selector(
                self._AVATAR_PREVIEW_CONTAINER, state="visible", timeout=timeout
            )
            return True
        except Exception:
            return False

    def get_avatar_preview_img_src_from_dom(self) -> str | None:
        """Return the src attribute of the avatar preview <img> read directly from the DOM.

        Does NOT wait — evaluates the current DOM state immediately.  Returns
        None when the element is absent (e.g. image load failed, SVG shown).
        """
        return self._page.evaluate(
            """() => {
                const img = document.querySelector(
                    '[role="img"][aria-label="Avatar preview"] img'
                );
                return img ? img.getAttribute('src') : null;
            }"""
        )

    def wait_for_avatar_img_src(self, expected_src: str, timeout: float = 8_000) -> str | None:
        """Wait until the avatar preview img src equals *expected_src*.

        Polls the DOM repeatedly (via wait_for_function) and returns the src
        value captured at the moment the condition is met.  Returns None when
        the timeout is exceeded without the condition becoming true.
        """
        try:
            handle = self._page.wait_for_function(
                """(expectedSrc) => {
                    const img = document.querySelector(
                        '[role="img"][aria-label="Avatar preview"] img'
                    );
                    if (!img) return null;
                    const src = img.getAttribute('src');
                    return src === expectedSrc ? src : null;
                }""",
                expected_src,
                timeout=timeout,
            )
            if handle:
                return handle.json_value()
        except Exception:
            pass
        # Fallback: read current state one more time.
        return self.get_avatar_preview_img_src_from_dom()

    def current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url
