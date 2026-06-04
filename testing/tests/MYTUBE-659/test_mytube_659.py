"""
MYTUBE-659: Hero section headline update — headline displays 'MYTUBE: corp video portal'

Objective
---------
Verify that the homepage hero headline correctly displays the updated corporate portal text.

Steps
-----
1. Navigate to the application homepage.
2. Locate the main H1 headline in the Hero section via HeroSectionComponent.

Expected Result
---------------
The headline text is exactly "MYTUBE: corp video portal".

Architecture
------------
- Playwright sync API (headless Chromium).
- HeroSectionComponent: page-object for the hero section.
- WebConfig: centralises env var access.

Environment variables
---------------------
APP_URL / WEB_BASE_URL  Base URL of the deployed web app.
                        Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-659/test_mytube_659.py -v
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.pages.hero_section.hero_section_component import HeroSectionComponent
from testing.core.config.web_config import WebConfig

_EXPECTED_HEADLINE = "MYTUBE: corp video portal"
_PAGE_LOAD_TIMEOUT = 30_000  # ms


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def hero_headline(config: WebConfig) -> str:
    """Launch Chromium, navigate to the homepage, and return the hero H1 text."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=config.headless,
            slow_mo=config.slow_mo,
        )
        try:
            page = browser.new_page()
            page.goto(config.home_url(), timeout=_PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")
            hero = HeroSectionComponent(page)
            return hero.get_hero_headline()
        finally:
            browser.close()


def test_hero_headline_exact_text(hero_headline: str) -> None:
    """The hero section H1 must be exactly 'MYTUBE: corp video portal'."""
    assert hero_headline == _EXPECTED_HEADLINE, (
        f"Hero headline mismatch.\n"
        f"  Expected: {_EXPECTED_HEADLINE!r}\n"
        f"  Actual:   {hero_headline!r}"
    )
