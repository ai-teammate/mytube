"""
Pytest fixtures for the MYTUBE-366 cross-browser text visibility test suite.

Provides a shared ``pw_page`` fixture that manages the full Playwright browser
lifecycle (sync_playwright → Browser → BrowserContext → Page) so individual
test methods never instantiate framework objects directly.

The fixture is function-scoped so that each test gets a clean browser context.
``browser_name`` is injected by pytest from the ``@pytest.mark.parametrize``
declaration on the test class.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

_PAGE_LOAD_TIMEOUT = 30_000  # ms


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    """Return a single WebConfig instance shared across the test module."""
    return WebConfig()


@pytest.fixture
def pw_page(browser_name: str, web_config: WebConfig) -> Page:
    """Launch *browser_name*, yield a configured Page, then close everything.

    Skips gracefully if the browser binary is unavailable on the host system
    (common for WebKit on headless Linux CI runners).

    ``browser_name`` is provided by the ``@pytest.mark.parametrize`` on the
    test class — pytest resolves it automatically as a fixture argument.
    """
    with sync_playwright() as pw:
        launcher = getattr(pw, browser_name)
        try:
            browser = launcher.launch(
                headless=web_config.headless,
                slow_mo=web_config.slow_mo,
            )
        except Exception as exc:
            pytest.skip(
                f"Browser '{browser_name}' could not be launched: {exc}"
            )
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            yield page
        finally:
            context.close()
            browser.close()
