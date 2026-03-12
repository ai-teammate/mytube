"""NonAuthShellPage — lightweight page object for verifying that the AppShell
is present on routes that share a string prefix with auth routes but are
*not* the auth routes themselves (e.g. /login-help, /register-confirmation).

These routes do not correspond to real pages in the application; navigating
to them causes GitHub Pages to serve the static-export 404.html, which is
rendered through the root layout and therefore wrapped by AppShell.
"""
from __future__ import annotations

from playwright.sync_api import Page

from testing.components.pages.mixins.shell_inspection_mixin import ShellInspectionMixin


class NonAuthShellPage(ShellInspectionMixin):
    """Page Object for any URL that is NOT an auth route.

    Provides navigation and shell-inspection helpers via ShellInspectionMixin.
    The page can be any URL — the only concern is whether the AppShell wrapper
    is correctly applied.
    """

    def __init__(self, page: Page) -> None:
        self._page = page

    def navigate(self, url: str) -> None:
        """Navigate to *url* and wait for DOM content to be loaded."""
        self._page.goto(url, wait_until="domcontentloaded")

    def get_current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url
