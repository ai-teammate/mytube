"""
Page Object for the homepage (/).

Encapsulates selectors and interactions for the homepage discovery sections:
  - "Recently Uploaded" section
  - "Most Viewed" section

Each section contains a grid of VideoCard components with:
  - Thumbnail (image or placeholder)
  - Title (link to /v/<id>)
  - Uploader username (link to /u/<username>)
  - View count
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from playwright.sync_api import Page, expect


@dataclass
class SectionInfo:
    """Snapshot of a discovery section on the homepage."""
    heading: str
    card_count: int
    card_titles: List[str] = field(default_factory=list)
    card_hrefs: List[str] = field(default_factory=list)
    card_uploaders: List[str] = field(default_factory=list)
    card_view_counts: List[str] = field(default_factory=list)


class HomePage:
    """Page Object for the MyTube homepage (/).

    Sections rendered by HomePageClient.tsx:
      - <section aria-labelledby="recently-uploaded-heading">
      - <section aria-labelledby="most-viewed-heading">

    Each VideoCard contains:
      - Thumbnail anchor: a[href*='/v/'] with aria-label=<title>
      - Title anchor:     a[href*='/v/'] (text link)
      - Uploader anchor:  a[href*='/u/']
      - View count:       <p> with "{N} views"
    """

    # Section selectors
    _RECENTLY_UPLOADED_SECTION = "section[aria-labelledby='recently-uploaded-heading']"
    _MOST_VIEWED_SECTION = "section[aria-labelledby='most-viewed-heading']"

    # Heading selectors (h2 inside each section)
    _SECTION_HEADING = "h2"

    # Card selectors (inside each section)
    # Each VideoCard has a thumbnail anchor and a title anchor both pointing to /v/<id>
    _VIDEO_CARD = "div.rounded-lg"
    _CARD_TITLE_LINK = "a[href*='/v/']"
    _CARD_UPLOADER_LINK = "a[href*='/u/']"
    # Thumbnail anchor — link wrapping the image, identified by aria-label
    _CARD_THUMBNAIL_LINK = "a[href*='/v/'][aria-label]"
    # View count paragraph
    _CARD_VIEW_COUNT = "p.text-xs"

    # Loading indicator
    _LOADING_TEXT = "text=Loading…"
    # Error indicator — p[role='alert'] targets the app error paragraph,
    # excluding the always-present Next.js route announcer div
    _ERROR_ALERT = "p[role='alert']"

    def __init__(self, page: Page) -> None:
        self._page = page

    def navigate(self, base_url: str) -> None:
        """Navigate to the homepage and wait for content to load."""
        url = f"{base_url.rstrip('/')}/"
        self._page.goto(url)
        self._wait_for_content()

    def _wait_for_content(self) -> None:
        """Wait until the loading indicator disappears."""
        # Wait for the loading spinner to disappear
        loading = self._page.locator(self._LOADING_TEXT)
        # If loading is present, wait for it to go away
        try:
            loading.wait_for(state="visible", timeout=3_000)
            loading.wait_for(state="hidden", timeout=30_000)
        except Exception:
            # Loading text may never appear if load is instant
            pass

    def assert_recently_uploaded_section_visible(self) -> None:
        """Assert that the Recently Uploaded section is visible (auto-retries until timeout)."""
        expect(self._page.locator(self._RECENTLY_UPLOADED_SECTION)).to_be_visible()

    def assert_most_viewed_section_visible(self) -> None:
        """Assert that the Most Viewed section is visible (auto-retries until timeout)."""
        expect(self._page.locator(self._MOST_VIEWED_SECTION)).to_be_visible()

    def get_recently_uploaded_heading(self) -> str:
        """Return the text of the Recently Uploaded section heading."""
        return (
            self._page
            .locator(self._RECENTLY_UPLOADED_SECTION)
            .locator(self._SECTION_HEADING)
            .inner_text()
            .strip()
        )

    def get_most_viewed_heading(self) -> str:
        """Return the text of the Most Viewed section heading."""
        return (
            self._page
            .locator(self._MOST_VIEWED_SECTION)
            .locator(self._SECTION_HEADING)
            .inner_text()
            .strip()
        )

    def get_recently_uploaded_card_count(self) -> int:
        """Return the number of video cards in the Recently Uploaded section."""
        return self._get_card_count(self._RECENTLY_UPLOADED_SECTION)

    def get_most_viewed_card_count(self) -> int:
        """Return the number of video cards in the Most Viewed section."""
        return self._get_card_count(self._MOST_VIEWED_SECTION)

    def _get_card_count(self, section_selector: str) -> int:
        section = self._page.locator(section_selector)
        return section.locator(self._VIDEO_CARD).count()

    def get_recently_uploaded_section_info(self) -> SectionInfo:
        """Return full details about the Recently Uploaded section."""
        return self._get_section_info(
            self._RECENTLY_UPLOADED_SECTION, "Recently Uploaded"
        )

    def get_most_viewed_section_info(self) -> SectionInfo:
        """Return full details about the Most Viewed section."""
        return self._get_section_info(
            self._MOST_VIEWED_SECTION, "Most Viewed"
        )

    def _get_section_info(self, section_selector: str, heading: str) -> SectionInfo:
        section = self._page.locator(section_selector)
        cards = section.locator(self._VIDEO_CARD)
        count = cards.count()

        titles: List[str] = []
        hrefs: List[str] = []
        uploaders: List[str] = []
        view_counts: List[str] = []

        for i in range(count):
            card = cards.nth(i)

            # Title link (second a[href*='/v/'] — the text link, not the thumbnail)
            title_links = card.locator(self._CARD_TITLE_LINK)
            if title_links.count() > 0:
                # The text title link is the one with font-medium class
                title_link = card.locator("a.text-sm.font-medium")
                if title_link.count() > 0:
                    titles.append(title_link.inner_text().strip())
                    hrefs.append(title_link.get_attribute("href") or "")
                else:
                    # Fallback: use first title link
                    titles.append(title_links.first.inner_text().strip())
                    hrefs.append(title_links.first.get_attribute("href") or "")
            else:
                titles.append("")
                hrefs.append("")

            # Uploader link
            uploader_link = card.locator(self._CARD_UPLOADER_LINK)
            if uploader_link.count() > 0:
                uploaders.append(uploader_link.first.inner_text().strip())
            else:
                uploaders.append("")

            # View count paragraph
            view_p = card.locator(self._CARD_VIEW_COUNT)
            if view_p.count() > 0:
                view_counts.append(view_p.first.inner_text().strip())
            else:
                view_counts.append("")

        return SectionInfo(
            heading=heading,
            card_count=count,
            card_titles=titles,
            card_hrefs=hrefs,
            card_uploaders=uploaders,
            card_view_counts=view_counts,
        )

    def get_section_thumbnail_missing_indexes(self, section_selector: str) -> list:
        """Return indexes of cards in *section_selector* that have no thumbnail anchor."""
        section = self._page.locator(section_selector)
        cards = section.locator(self._VIDEO_CARD)
        missing = []
        for i in range(cards.count()):
            if cards.nth(i).locator(self._CARD_THUMBNAIL_LINK).count() == 0:
                missing.append(i)
        return missing

    def all_card_hrefs_match_video_pattern(self, section_selector: str) -> bool:
        """Return True if every video card link in the section matches /v/<id>."""
        section = self._page.locator(section_selector)
        links = section.locator(self._CARD_TITLE_LINK)
        count = links.count()
        if count == 0:
            return False  # guard: no links found is a failure, not a pass
        for i in range(count):
            href = links.nth(i).get_attribute("href") or ""
            if not re.search(r"/v/.+", href):  # use search to tolerate basePath prefix
                return False
        return True

    def recently_uploaded_cards_have_valid_hrefs(self) -> bool:
        return self.all_card_hrefs_match_video_pattern(self._RECENTLY_UPLOADED_SECTION)

    def most_viewed_cards_have_valid_hrefs(self) -> bool:
        return self.all_card_hrefs_match_video_pattern(self._MOST_VIEWED_SECTION)

    def is_error_displayed(self) -> bool:
        """Return True if an error alert is present."""
        return self._page.locator(self._ERROR_ALERT).is_visible()

    def current_url(self) -> str:
        return self._page.url

    def click_first_video_card_title(self) -> str:
        """Click the title link of the first video card on the page.

        Searches both homepage sections for the first available card title
        link and clicks it.  Returns the title text for later assertion.

        Raises ``AssertionError`` if no video cards are found.
        """
        title_link = self._page.locator("a.text-sm.font-medium").first
        assert title_link.count() > 0 or title_link.is_visible(), (
            "No video card title links found on the homepage. "
            "Ensure at least one video with 'ready' status is available."
        )
        title_text = title_link.inner_text().strip()
        title_link.click()
        return title_text

    def has_video_cards(self) -> bool:
        """Return True if at least one video card title link is present."""
        return self._page.locator("a.text-sm.font-medium").count() > 0

    def wait_for_navigation_to_watch(self, timeout: int = 30_000) -> None:
        """Wait until the browser URL contains a /v/<uuid> segment."""
        import re
        self._page.wait_for_url(re.compile(r"/v/[^/]+"), timeout=timeout)
