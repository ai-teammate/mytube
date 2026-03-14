"""HeroSectionPage — Page Object for hero landing image attribute inspection.

Encapsulates all Playwright locator, evaluate, and browser lifecycle logic
for the landing ``<img>`` element in the hero section so that tests never
call framework APIs directly.

Accepts either:
- a ``playwright.sync_api.Page`` (caller owns browser lifecycle), or
- a ``WebConfig`` (component owns browser lifecycle internally).
"""
from __future__ import annotations

from typing import Union

from playwright.sync_api import Page, sync_playwright

from testing.core.config.web_config import WebConfig

_VIEWPORT = {"width": 1280, "height": 800}
_PAGE_LOAD_TIMEOUT = 30_000  # ms


class HeroSectionPage:
    """Page Object for the homepage hero landing image."""

    # Selectors tried in order to find the landing image
    _LANDING_IMG_SELECTOR = (
        "img[src*='landing_image'], "
        "[class*='visualCanvas'] img, "
        "[class*='frostedOverlay'] img"
    )
    _HERO_IMG_FALLBACK = "section[aria-label='Hero'] img"

    def __init__(self, page_or_config: Union[Page, WebConfig]) -> None:
        if isinstance(page_or_config, WebConfig):
            self._config: WebConfig | None = page_or_config
            self._page: Page | None = None
        else:
            self._config = None
            self._page = page_or_config

    def navigate(self, url: str) -> None:
        """Navigate to *url* and wait for the DOM to be ready.

        Only valid when the instance was constructed with a ``Page`` object.
        """
        assert self._page is not None, (
            "navigate() requires HeroSectionPage to be constructed with a Page object."
        )
        self._page.goto(url, timeout=_PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")

    def get_landing_image_attributes(self, url: str | None = None) -> dict:
        """Return ``alt``, ``width``, ``height``, ``src`` for the hero landing ``<img>``.

        When constructed with a ``WebConfig``, the component creates and tears
        down its own browser instance internally (Playwright lifecycle is fully
        encapsulated).  The *url* argument defaults to ``config.home_url()`` in
        that case but can be overridden.

        When constructed with a ``Page`` object, *url* is required and the
        caller is responsible for the browser lifecycle.

        Raises
        ------
        AssertionError
            If no matching image element can be found on the page.
        """
        if self._config is not None:
            target_url = url if url is not None else self._config.home_url()
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=self._config.headless)
                try:
                    page = browser.new_page()
                    page.set_viewport_size(_VIEWPORT)
                    return self._extract_image_attributes(page, target_url)
                finally:
                    browser.close()
        else:
            assert url is not None, (
                "url is required when HeroSectionPage is constructed with a Page object."
            )
            assert self._page is not None
            return self._extract_image_attributes(self._page, url)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_image_attributes(self, page: Page, url: str) -> dict:
        """Navigate *page* to *url* and extract landing image attributes."""
        page.goto(url, timeout=_PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")

        img_locator = page.locator(self._LANDING_IMG_SELECTOR).first
        try:
            img_locator.wait_for(state="attached", timeout=15_000)
        except Exception:
            img_locator = page.locator(self._HERO_IMG_FALLBACK).first
            img_locator.wait_for(state="attached", timeout=10_000)

        assert img_locator.count() > 0, (
            "No <img> element for the hero landing image was found on the homepage. "
            "Expected: an <img> with src containing 'landing_image' inside the hero section."
        )

        return img_locator.evaluate(
            """(el) => ({
                alt:    el.getAttribute('alt'),
                width:  el.getAttribute('width'),
                height: el.getAttribute('height'),
                src:    el.getAttribute('src') || el.currentSrc || '',
            })"""
        )
