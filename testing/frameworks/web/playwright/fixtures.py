"""Shared Playwright browser fixtures for the testing framework layer.

Tests must not instantiate sync_playwright or Chromium directly.  Instead,
they should consume the ``browser`` fixture exposed here (by importing it in
their local ``conftest.py``), keeping framework concerns out of test files.

Usage in a test-folder conftest.py
-----------------------------------
    from testing.frameworks.web.playwright.fixtures import browser  # noqa: F401

The ``browser`` fixture is then automatically available to all tests in that
folder without any further changes.
"""
from __future__ import annotations

import os

import pytest
from playwright.sync_api import sync_playwright, Browser


@pytest.fixture(scope="module")
def browser() -> Browser:
    """Launch a Chromium browser instance configured via environment variables.

    Environment Variables
    ---------------------
    PLAYWRIGHT_HEADLESS   Run browser headless (default: ``true``).
    PLAYWRIGHT_SLOW_MO    Slow-motion delay in ms (default: ``0``).

    Yields
    ------
    Browser
        A Chromium browser instance that is closed after the module finishes.
    """
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))

    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        yield br
        br.close()
