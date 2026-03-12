"""SiteHeader — Page Object for the global site header component.

Encapsulates all interactions with the SiteHeader (logo, search, nav links)
shared across every page of the MyTube web application.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — callers supply the base URL when navigating.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from __future__ import annotations

from playwright.sync_api import Page


class SiteHeader:
    """Page Object for the MyTube site header rendered by SiteHeader.tsx.

    The header is present on every page and contains:
      - Logo link: <a href="/" class="…text-red-600…">mytube</a>
      - Search input and button
      - Primary navigation links (Home, Upload, My Videos, Playlists)
    """

    # Logo: the "mytube" branded link that always navigates to /
    _LOGO_LINK = "header a.text-red-600"

    def __init__(self, page: Page) -> None:
        self._page = page

    def click_logo(self) -> None:
        """Click the site logo link in the header."""
        self._page.locator(self._LOGO_LINK).first.click()

    def logo_is_visible(self) -> bool:
        """Return True if the logo link is visible in the header."""
        return self._page.locator(self._LOGO_LINK).first.is_visible()

    def logo_href(self) -> str:
        """Return the href attribute of the logo link."""
        return self._page.locator(self._LOGO_LINK).first.get_attribute("href") or ""

    def logo_text(self) -> str:
        """Return the text content of the logo link."""
        return self._page.locator(self._LOGO_LINK).first.inner_text().strip()

    # ------------------------------------------------------------------
    # Auth-state assertions
    # ------------------------------------------------------------------

    # role="alert" span rendered by SiteHeader.tsx when authError=true.
    # Scoped to <header> to avoid false positives from other alert elements
    # (toasts, form validation, etc.) elsewhere on the page.
    _AUTH_ERROR_ALERT_SELECTOR = "header [role='alert']"

    # "Sign in" navigation link rendered when not authenticated and no auth error.
    # Scoped to <header> to avoid matching form buttons/headings on other pages.
    _SIGN_IN_LINK_SELECTOR = "header a:has-text('Sign in')"

    def has_auth_error_alert(self) -> bool:
        """Return True if the auth-error alert is visible in the site header.

        The alert is the ``<span role="alert">`` rendered by SiteHeader.tsx
        when ``authError=true``.  It contains the text
        "Authentication services are currently unavailable".
        """
        locator = self._page.locator(self._AUTH_ERROR_ALERT_SELECTOR)
        return locator.count() > 0 and locator.first.is_visible()

    def auth_error_alert_text(self) -> str:
        """Return the text content of the auth-error alert, or empty string."""
        locator = self._page.locator(self._AUTH_ERROR_ALERT_SELECTOR)
        if locator.count() == 0 or not locator.first.is_visible():
            return ""
        return (locator.first.text_content() or "").strip()

    def has_sign_in_link(self) -> bool:
        """Return True if the 'Sign in' navigation link is visible in the header.

        This checks *only* ``<a>`` elements inside ``<header>`` to avoid
        matching 'Sign in' buttons or headings on other parts of the page
        (e.g., the login form's ``<h2>Sign in</h2>``).
        """
        locator = self._page.locator(self._SIGN_IN_LINK_SELECTOR)
        return locator.count() > 0 and locator.first.is_visible()

    # ------------------------------------------------------------------
    # Avatar (authenticated user) helpers
    # ------------------------------------------------------------------

    # The avatar span rendered by SiteHeader.tsx inside the header utility
    # area when the user is authenticated.  It carries ``rounded-full`` and
    # is the only span containing a single letter directly inside the
    # ``<header>`` button that opens the account menu.
    _AVATAR_SELECTOR = "header button span.rounded-full"

    # Green colour stop used in both light and dark --gradient-hero.
    _AVATAR_GREEN_HEX = "#62c235"

    def avatar_wait(self, timeout: float = 10_000) -> None:
        """Wait until the avatar span appears in the header (confirms auth state)."""
        self._page.wait_for_selector(self._AVATAR_SELECTOR, timeout=timeout)

    def avatar_is_visible(self) -> bool:
        """Return True if the avatar span is present and visible in the header."""
        locator = self._page.locator(self._AVATAR_SELECTOR)
        return locator.count() > 0 and locator.first.is_visible()

    def avatar_css(self) -> dict[str, str]:
        """Return computed CSS properties of the avatar span as a dict.

        Keys: ``borderRadius``, ``backgroundImage``, ``background``.
        Returns an empty dict when the element is not in the DOM.
        """
        return self._page.evaluate(
            """(sel) => {
                const el = document.querySelector(sel);
                if (!el) return {};
                const s = window.getComputedStyle(el);
                return {
                    borderRadius: s.borderRadius,
                    backgroundImage: s.backgroundImage,
                    background: s.background,
                };
            }""",
            self._AVATAR_SELECTOR,
        )

    def avatar_text(self) -> str:
        """Return the trimmed text content of the avatar span."""
        el = self._page.query_selector(self._AVATAR_SELECTOR)
        if el is None:
            return ""
        return (el.text_content() or "").strip()

    @staticmethod
    def avatar_contains_green(css_value: str) -> bool:
        """Return True if *css_value* contains the green colour stop #62c235."""
        # Browsers may convert hex → rgb; compare both forms.
        return (
            "62c235" in css_value.lower()
            or "rgb(98, 194, 53)" in css_value
        )

    @staticmethod
    def avatar_contains_purple(css_value: str) -> bool:
        """Return True if *css_value* contains any known purple colour stop."""
        lower = css_value.lower()
        if "6d40cb" in lower or "9370db" in lower:
            return True
        # RGB forms: rgb(109, 64, 203)  or  rgb(147, 112, 219)
        if "rgb(109, 64, 203)" in lower or "rgb(147, 112, 219)" in lower:
            return True
        return False
