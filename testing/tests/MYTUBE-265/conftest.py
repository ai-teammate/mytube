"""
Pytest configuration and fixtures for MYTUBE-265 tests.

This module provides centralized fixture configuration for all tests in the
MYTUBE-265 test suite, enabling environment-based configuration for CI and
local development environments.
"""
import os
import pytest
from playwright.sync_api import sync_playwright, Browser, Page

_PAGE_LOAD_TIMEOUT = 30_000  # ms — max time for initial page load


@pytest.fixture(scope="module")
def browser():
    """
    Launch a Chromium browser instance with environment-based configuration.
    
    Environment Variables:
    - PLAYWRIGHT_HEADLESS (default: "true"): Run browser in headless mode
    - PLAYWRIGHT_SLOW_MO (default: "0"): Slow down Playwright operations (milliseconds)
    
    Yields:
        Browser: A Chromium browser instance
    """
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))
    
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        yield br
        br.close()


@pytest.fixture(scope="module")
def page(browser: Browser) -> Page:
    """
    Create a fresh browser context and page for the test module.
    
    The page is configured with a default timeout for element waits and loads.
    
    Args:
        browser: Browser fixture providing the Chromium browser instance
        
    Yields:
        Page: A Playwright page instance for test interactions
    """
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()
