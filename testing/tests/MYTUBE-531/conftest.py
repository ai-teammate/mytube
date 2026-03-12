"""Pytest fixtures for MYTUBE-531 tests.

Browser lifecycle is managed through the shared framework fixture so that
the test file itself stays free of Playwright internals.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Re-export the shared browser fixture from the framework layer.
from testing.frameworks.web.playwright.fixtures import browser  # noqa: F401

from testing.core.config.web_config import WebConfig

_PAGE_LOAD_TIMEOUT = 30_000  # ms


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser_page(browser: Browser, config: WebConfig) -> Page:
    """Open a 1280×720 page and navigate to the homepage."""
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    page.goto(config.home_url(), timeout=_PAGE_LOAD_TIMEOUT, wait_until="networkidle")
    yield page
    page.close()
