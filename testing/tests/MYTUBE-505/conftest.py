"""Pytest configuration and fixtures for MYTUBE-505 tests."""
import os
import pytest
from playwright.sync_api import sync_playwright, Browser, Page

_PAGE_LOAD_TIMEOUT = 30_000  # ms


@pytest.fixture(scope="module")
def browser():
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))

    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        yield br
        br.close()


@pytest.fixture(scope="module")
def page(browser: Browser) -> Page:
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()
