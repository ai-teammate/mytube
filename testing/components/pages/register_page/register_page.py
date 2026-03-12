"""Page Object for the /register page.

Encapsulates all interactions with the registration form.
Depends on a Playwright Page instance injected via constructor.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Page, Request, Response


@dataclass
class RegistrationResult:
    """Outcome of a registration attempt."""

    redirected_away: bool
    """True if the page navigated away from /register after submission."""

    api_me_called: bool
    """True if GET /api/me was observed in network traffic."""

    api_me_status: Optional[int]
    """HTTP status of the /api/me request, or None if it was not called."""

    error_message: Optional[str]
    """Text of the error alert shown on the page, or None if no error."""

    final_url: str
    """The URL of the page after the registration attempt completes."""


class RegisterPage:
    """Page Object for the registration form at /register.

    All selectors and form interactions are encapsulated here.
    Tests call high-level methods and never touch raw locators directly.
    """

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, base_url: str) -> None:
        """Navigate to the /register page and wait until it is loaded.

        Waits for the Firebase auth loading state to resolve before returning,
        so that the registration form is visible and interactive.
        """
        url = base_url.rstrip("/") + "/register/"
        self._page.goto(url, wait_until="networkidle")
        # Wait for the loading spinner to disappear (Firebase auth resolves)
        # and the form heading to become visible.
        self._page.wait_for_selector("h1", timeout=20_000)

    # ------------------------------------------------------------------
    # Shell / layout inspection
    # ------------------------------------------------------------------

    def has_shell_class(self) -> bool:
        """Return True if a .shell element is present in the DOM."""
        return self._page.locator(".shell").count() > 0

    def has_page_wrap_class(self) -> bool:
        """Return True if a .page-wrap element is present in the DOM."""
        return self._page.locator(".page-wrap").count() > 0

    def has_shell_like_styles(self) -> str | None:
        """Return className of first element with shell styles (borderRadius=24px, maxWidth=1320px), or None."""
        return self._page.evaluate("""() => {
            for (const el of document.querySelectorAll('body *')) {
                const s = window.getComputedStyle(el);
                if (s.borderRadius === '24px' && s.maxWidth === '1320px')
                    return el.className || el.tagName;
            }
            return null;
        }""")

    # ------------------------------------------------------------------
    # Assertions (state queries)
    # ------------------------------------------------------------------

    def current_url(self) -> str:
        """Return the current URL of the page."""
        return self._page.url

    def is_on_register_page(self) -> bool:
        """Return True if the register form heading is visible."""
        return self._page.locator("h1").filter(has_text="Create an account").is_visible()

    def has_file_not_found_error(self) -> bool:
        """Return True if the page body contains a GitHub Pages 404 error text."""
        return "file not found" in self._page.inner_text("body").lower()

    def hard_refresh(self, settle_timeout: int = 20_000) -> None:
        """Simulate a hard browser refresh (Ctrl+R) and wait for the page to settle."""
        self._page.reload(wait_until="networkidle")
        try:
            self._page.wait_for_selector("h1", timeout=settle_timeout)
        except Exception:
            pass  # Assertion in the test will produce a clear failure message

    def get_error_message(self) -> Optional[str]:
        """Return the text of the error alert, or None if absent or empty."""
        alert = self._page.get_by_role("alert")
        if alert.count() == 0:
            return None
        text = alert.inner_text().strip()
        return text if text else None

    # ------------------------------------------------------------------
    # Auth-switch link ("Sign in" → /login)
    # ------------------------------------------------------------------

    _SWITCH_LINK = 'p a[href*="/login"]'

    def get_switch_link_color(self) -> str:
        """Return the computed color of the switch-to-login link."""
        return self._page.evaluate(
            "(sel) => getComputedStyle(document.querySelector(sel)).color",
            self._SWITCH_LINK,
        )

    def hover_switch_link(self) -> None:
        """Hover the switch-to-login link and wait for CSS transitions."""
        self._page.hover(self._SWITCH_LINK)
        self._page.wait_for_timeout(300)

    def get_switch_link_text_decoration(self) -> str:
        """Return the computed textDecorationLine of the switch link."""
        return self._page.evaluate(
            "(sel) => getComputedStyle(document.querySelector(sel)).textDecorationLine",
            self._SWITCH_LINK,
        )

    def wait_for_switch_link(self, timeout: int = 30_000) -> None:
        """Block until the switch-to-login link is present in the DOM."""
        self._page.wait_for_selector(self._SWITCH_LINK, timeout=timeout)

    # ------------------------------------------------------------------
    # Form interactions
    # ------------------------------------------------------------------

    def fill_email(self, email: str) -> None:
        self._page.get_by_label("Email").fill(email)

    def fill_password(self, password: str) -> None:
        self._page.get_by_label("Password").fill(password)

    def submit(self) -> None:
        """Click the submit button and wait for network to settle."""
        self._page.get_by_role("button", name="Create account").click()

    # ------------------------------------------------------------------
    # High-level flows
    # ------------------------------------------------------------------

    def register_and_capture(
        self,
        email: str,
        password: str,
        base_url: str,
        timeout_ms: int = 30_000,
    ) -> RegistrationResult:
        """Fill the form, submit it, and capture the network + navigation result.

        Intercepts all requests so that GET /api/me can be detected even if
        the browser redirects before the response is received.

        Parameters
        ----------
        email:
            Email address to enter into the form.
        password:
            Password to enter into the form.
        base_url:
            The deployed application base URL (e.g. http://localhost:3000).
        timeout_ms:
            Maximum milliseconds to wait for navigation after form submission.
        """
        register_url_fragment = "/register"
        api_me_requests: list[Request] = []
        api_me_responses: list[Response] = []

        # Capture every request to /api/me regardless of origin.
        def on_request(req: Request) -> None:
            if "/api/me" in req.url and req.method == "GET":
                api_me_requests.append(req)

        def on_response(resp: Response) -> None:
            if "/api/me" in resp.url:
                api_me_responses.append(resp)

        self._page.on("request", on_request)
        self._page.on("response", on_response)

        try:
            self.fill_email(email)
            self.fill_password(password)

            try:
                with self._page.expect_navigation(timeout=timeout_ms, wait_until="networkidle"):
                    self.submit()
            except Exception:
                # Navigation may not have occurred (e.g., error shown instead).
                # Wait for the network to become idle so any /api/me calls finish.
                self._page.wait_for_load_state("networkidle", timeout=timeout_ms)

            final_url = self._page.url
            redirected_away = register_url_fragment not in final_url

            api_me_status: Optional[int] = None
            if api_me_responses:
                api_me_status = api_me_responses[0].status

            return RegistrationResult(
                redirected_away=redirected_away,
                api_me_called=len(api_me_requests) > 0,
                api_me_status=api_me_status,
                error_message=self.get_error_message(),
                final_url=final_url,
            )

        finally:
            self._page.remove_listener("request", on_request)
            self._page.remove_listener("response", on_response)
