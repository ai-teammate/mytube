"""
FooterComponent — Page Object for the global site footer.

Encapsulates selectors and assertions for SiteFooter.tsx:
  - Copyright notice (<p> with © <year> mytube. All rights reserved.)
  - Footer navigation with Terms (<a href="/terms">) and Privacy (<a href="/privacy">)
"""
from __future__ import annotations

from playwright.sync_api import Page, expect


class FooterComponent:
    """Page Object for the global SiteFooter rendered on every page.

    The SiteFooter renders as:
      <footer class="bg-white border-t ...">
        <p class="text-sm text-gray-500">© <year> mytube. All rights reserved.</p>
        <nav aria-label="Footer navigation">
          <a href="/terms">Terms</a>
          <a href="/privacy">Privacy</a>
        </nav>
      </footer>
    """

    _FOOTER = "footer"
    _COPYRIGHT = "footer p.text-sm.text-gray-500"
    _FOOTER_NAV = "nav[aria-label='Footer navigation']"
    # Use href*= (contains) to tolerate a Next.js basePath prefix (e.g. /mytube/terms/)
    _TERMS_LINK = "nav[aria-label='Footer navigation'] a[href*='/terms']"
    _PRIVACY_LINK = "nav[aria-label='Footer navigation'] a[href*='/privacy']"

    def __init__(self, page: Page) -> None:
        self._page = page

    def scroll_into_view(self) -> None:
        """Scroll to the footer so it is visible in the viewport."""
        footer = self._page.locator(self._FOOTER)
        footer.scroll_into_view_if_needed()

    def assert_footer_visible(self) -> None:
        """Assert the footer element is visible."""
        expect(self._page.locator(self._FOOTER)).to_be_visible()

    def assert_copyright_visible(self) -> None:
        """Assert the copyright paragraph is visible."""
        expect(self._page.locator(self._COPYRIGHT)).to_be_visible()

    def assert_terms_link_visible(self) -> None:
        """Assert the Terms link is visible."""
        expect(self._page.locator(self._TERMS_LINK)).to_be_visible()

    def assert_privacy_link_visible(self) -> None:
        """Assert the Privacy link is visible."""
        expect(self._page.locator(self._PRIVACY_LINK)).to_be_visible()

    def get_copyright_text(self) -> str:
        """Return the copyright paragraph text."""
        return self._page.locator(self._COPYRIGHT).inner_text().strip()

    def get_terms_link_href(self) -> str:
        """Return the href attribute of the Terms link."""
        return self._page.locator(self._TERMS_LINK).get_attribute("href") or ""

    def get_privacy_link_href(self) -> str:
        """Return the href attribute of the Privacy link."""
        return self._page.locator(self._PRIVACY_LINK).get_attribute("href") or ""

    def get_terms_link_text(self) -> str:
        """Return the visible text of the Terms link."""
        return self._page.locator(self._TERMS_LINK).inner_text().strip()

    def get_privacy_link_text(self) -> str:
        """Return the visible text of the Privacy link."""
        return self._page.locator(self._PRIVACY_LINK).inner_text().strip()
