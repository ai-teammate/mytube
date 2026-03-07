"""LoginPage — Page Object for the /login page of the MyTube web application.

Encapsulates all interactions with the login form, exposing only high-level
actions and state queries to callers.  Raw selectors never leak outside this
class.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — the caller provides the full login URL.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from playwright.sync_api import Page, expect


class LoginPage:
    """Page Object for the MyTube login page."""

    # Selectors
    _EMAIL_INPUT = 'input[id="email"]'
    _PASSWORD_INPUT = 'input[id="password"]'
    # Exclude the site-header search submit (aria-label="Submit search") so that
    # this selector targets only the sign-in form button even when the full
    # AppShell header is rendered on the login page.
    _SIGN_IN_BUTTON = 'button[type="submit"]:not([aria-label="Submit search"])'
    _ERROR_ALERT = '[role="alert"]'

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, url: str) -> None:
        """Navigate the browser to the login page URL and wait for it to load."""
        self._page.goto(url, wait_until="domcontentloaded")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def fill_email(self, email: str) -> None:
        """Type *email* into the email input field."""
        self._page.fill(self._EMAIL_INPUT, email)

    def fill_password(self, password: str) -> None:
        """Type *password* into the password input field."""
        self._page.fill(self._PASSWORD_INPUT, password)

    def click_sign_in(self) -> None:
        """Click the Sign In submit button."""
        self._page.click(self._SIGN_IN_BUTTON)

    def login_as(self, email: str, password: str) -> None:
        """High-level action: fill the form and submit.

        Does NOT wait for navigation — the caller is responsible for asserting
        the post-login state.
        """
        self.fill_email(email)
        self.fill_password(password)
        self.click_sign_in()

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def get_current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    def is_on_home_page(self, home_url: str) -> bool:
        """Return True if the browser has navigated to *home_url*."""
        current = self._page.url.rstrip("/")
        target = home_url.rstrip("/")
        return current == target

    def get_error_message(self) -> str | None:
        """Return the visible error alert text, or None if no alert is shown or empty."""
        locator = self._page.locator(self._ERROR_ALERT)
        if locator.count() == 0:
            return None
        text = locator.text_content()
        return text if text else None

    def wait_for_navigation_to(self, url: str, timeout: float = 15_000) -> None:
        """Block until the page URL matches *url* (with trailing-slash tolerance)."""
        self._page.wait_for_url(
            lambda u: u.rstrip("/") == url.rstrip("/"),
            timeout=timeout,
        )

    def is_form_visible(self) -> bool:
        """Return True when the email input is present in the DOM."""
        return self._page.locator(self._EMAIL_INPUT).count() > 0

    def wait_for_form(self, timeout: int = 30_000) -> None:
        """Block until the email input is present in the DOM."""
        self._page.wait_for_selector(self._EMAIL_INPUT, timeout=timeout)

    # ------------------------------------------------------------------
    # Visibility / placeholder / text-colour checks
    # ------------------------------------------------------------------

    def is_email_input_visible(self) -> bool:
        """Return True if the email input is visible on the login page."""
        return self._page.locator(self._EMAIL_INPUT).is_visible()

    def get_email_placeholder(self) -> str:
        """Return the placeholder attribute of the email input, or empty string."""
        return self._page.locator(self._EMAIL_INPUT).get_attribute("placeholder") or ""

    def is_email_text_color_visible(self) -> bool:
        """Return False if the email input's computed text colour is fully transparent."""
        return self._is_text_color_visible(self._EMAIL_INPUT)

    def is_password_input_visible(self) -> bool:
        """Return True if the password input is visible on the login page."""
        return self._page.locator(self._PASSWORD_INPUT).is_visible()

    def get_password_placeholder(self) -> str:
        """Return the placeholder attribute of the password input, or empty string."""
        return self._page.locator(self._PASSWORD_INPUT).get_attribute("placeholder") or ""

    def is_password_text_color_visible(self) -> bool:
        """Return False if the password input's computed text colour is fully transparent."""
        return self._is_text_color_visible(self._PASSWORD_INPUT)

    def is_sign_in_button_visible(self) -> bool:
        """Return True if the Sign In button is visible on the login page."""
        return self._page.locator(self._SIGN_IN_BUTTON).is_visible()

    def get_sign_in_button_label(self) -> str:
        """Return the visible text / aria-label of the Sign In button."""
        label: str = self._page.evaluate(
            """(sel) => {
                const el = document.querySelector(sel);
                if (!el) return '';
                return (
                    el.innerText ||
                    el.textContent ||
                    el.getAttribute('aria-label') ||
                    ''
                ).trim();
            }""",
            self._SIGN_IN_BUTTON,
        )
        return label or ""

    def is_sign_in_button_text_color_visible(self) -> bool:
        """Return False if the Sign In button's computed text colour is fully transparent."""
        return self._is_text_color_visible(self._SIGN_IN_BUTTON)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_text_color_visible(self, selector: str) -> bool:
        """Return False if the computed ``color`` CSS property is fully transparent."""
        color: str | None = self._page.evaluate(
            """(sel) => {
                const el = document.querySelector(sel);
                if (!el) return null;
                return window.getComputedStyle(el).color;
            }""",
            selector,
        )
        if color is None:
            return False
        return color != "rgba(0, 0, 0, 0)"
