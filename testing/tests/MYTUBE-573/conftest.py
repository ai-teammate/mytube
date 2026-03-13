"""Pytest fixtures for MYTUBE-573 tests.

Browser lifecycle is managed through the shared framework fixture so that
the test file itself stays free of Playwright internals.
"""
from __future__ import annotations

import os
import sys
from typing import Generator, NamedTuple

import pytest
from playwright.sync_api import Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Re-export the shared browser fixture from the framework layer.
from testing.frameworks.web.playwright.fixtures import browser  # noqa: F401

from testing.core.config.web_config import WebConfig
from testing.components.pages.hero_section.hero_section_component import (
    HeroSectionComponent,
)

_PAGE_LOAD_TIMEOUT = 30_000  # ms


class Viewport(NamedTuple):
    name: str
    width: int
    height: int


VIEWPORTS = [
    Viewport("mobile",  375,  812),
    Viewport("tablet",  768, 1024),
    Viewport("desktop", 1440, 900),
]


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(
    params=VIEWPORTS,
    ids=[v.name for v in VIEWPORTS],
)
def hero_page(
    browser: Browser, config: WebConfig, request: pytest.FixtureRequest
) -> Generator[tuple[HeroSectionComponent, Viewport], None, None]:
    """Open a page at the parametrised viewport and yield (HeroSectionComponent, Viewport).

    The browser lifecycle is managed here so the test body contains no
    Playwright internals.
    """
    vp: Viewport = request.param
    page: Page = browser.new_page(viewport={"width": vp.width, "height": vp.height})
    page.goto(config.base_url + "/", timeout=_PAGE_LOAD_TIMEOUT)
    page.wait_for_load_state("domcontentloaded", timeout=_PAGE_LOAD_TIMEOUT)
    hero = HeroSectionComponent(page)
    yield hero, vp
    page.close()
