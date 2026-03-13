"""HeroSectionPage — Page Object for hero landing image attribute inspection.

Encapsulates all Playwright locator and evaluate logic for the landing
``<img>`` element in the hero section so that tests never call framework
APIs directly.
"""
from __future__ import annotations

from playwright.sync_api import Page

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

    def __init__(self, page: Page) -> None:
        self._page = page

    def navigate(self, url: str) -> None:
        """Navigate to *url* and wait for the DOM to be ready."""
        self._page.goto(url, timeout=_PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")

    def get_landing_image_attributes(self, url: str) -> dict:
        """Navigate to *url* and return ``alt``, ``width``, ``height``, ``src``
        for the hero landing ``<img>`` element.

        Raises
        ------
        AssertionError
            If no matching image element can be found on the page.
        """
        self.navigate(url)

        img_locator = self._page.locator(self._LANDING_IMG_SELECTOR).first
        try:
            img_locator.wait_for(state="attached", timeout=15_000)
        except Exception:
            img_locator = self._page.locator(self._HERO_IMG_FALLBACK).first
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
