"""Global alerts component for tests.

Encapsulates querying global alert elements (role="alert") and provides
intent-revealing helpers such as has_auth_unavailable_alert().
"""
from __future__ import annotations

from playwright.sync_api import Page

AUTH_UNAVAILABLE_TEXT = "Authentication services are currently unavailable"


class GlobalAlerts:
    """Wrapper around global alert UI elements used by tests."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def has_auth_unavailable_alert(self) -> bool:
        """Return True if any alert element contains the auth-unavailable text."""
        alerts = self.page.locator("[role='alert']")
        try:
            count = alerts.count()
        except Exception:
            # If locator evaluation fails, consider no alerts present.
            return False

        for i in range(count):
            text = (alerts.nth(i).text_content() or "").strip()
            if AUTH_UNAVAILABLE_TEXT in text:
                return True
        return False
