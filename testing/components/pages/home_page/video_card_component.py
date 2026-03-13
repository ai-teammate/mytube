"""
Component class for VideoCard thumbnail CSS transition inspection.

Encapsulates all DOM/CSS inspection helpers for VideoCard thumbnail images,
following the component-abstraction architecture pattern established by
SiteHeader and HomePage.
"""
from __future__ import annotations

from playwright.sync_api import Page


class VideoCardComponent:
    """Page-object component for VideoCard thumbnail transition inspection.

    Wraps all ``page.evaluate()`` calls and CSS-selector internals so that
    tests never interact with the DOM or JS APIs directly.

    Usage::

        component = VideoCardComponent(page)
        rule = component.find_fade_css_rule()
        images = component.get_images_with_opacity_transition()
    """

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Stylesheet inspection
    # ------------------------------------------------------------------

    def find_fade_css_rule(self) -> dict | None:
        """Search all loaded stylesheets for a rule that applies an opacity
        fade-in transition to ``img`` elements inside a thumbnail container.

        Returns a dict with ``cssText`` (up to 400 characters) if a matching
        rule is found, otherwise ``None``.
        """
        return self._page.evaluate("""() => {
            for (const sheet of document.styleSheets) {
                try {
                    for (const rule of sheet.cssRules) {
                        const text = rule.cssText || '';
                        if (text.includes('img') &&
                            text.includes('opacity') &&
                            text.includes('transition')) {
                            return { cssText: text.substring(0, 400) };
                        }
                    }
                } catch (e) {
                    // Ignore CORS-blocked cross-origin stylesheets
                }
            }
            return null;
        }""")

    # ------------------------------------------------------------------
    # Image transition inspection
    # ------------------------------------------------------------------

    def get_images_with_opacity_transition(self) -> list:
        """Return computed-style data for ``img`` elements that have an
        explicit ``opacity`` CSS transition with a non-zero duration.

        Only images with ``transitionProperty == 'opacity'`` *and* a non-zero
        ``transitionDuration`` are included — images that only carry the
        browser default ``all 0s ease`` are excluded.
        """
        return self._page.evaluate("""() => {
            const results = [];
            const allImgs = document.querySelectorAll('#video-grid img, main img');
            for (const img of allImgs) {
                const cs = window.getComputedStyle(img);
                const transitionProperty = (cs.transitionProperty || '').toLowerCase();
                const transitionDuration = cs.transitionDuration || '0s';
                const hasOpacityTransition = (
                    transitionProperty === 'opacity' ||
                    transitionProperty.includes('opacity')
                );
                if (hasOpacityTransition && transitionDuration !== '0s') {
                    results.push({
                        src: img.src,
                        opacity: cs.opacity,
                        transition: cs.transition,
                        transitionProperty: cs.transitionProperty,
                        transitionDuration: cs.transitionDuration,
                        transitionTimingFunction: cs.transitionTimingFunction,
                        classList: img.classList.toString(),
                        complete: img.complete,
                        naturalWidth: img.naturalWidth,
                    });
                }
            }
            return results;
        }""")

    def find_any_thumbnail_image(self) -> dict | None:
        """Return computed-style data for the first VideoCard thumbnail
        ``<img>`` found on the page, using multiple selector strategies as
        fallback to cope with CSS-module class name hashing.
        """
        return self._page.evaluate("""() => {
            const candidates = [
                '#video-grid img',
                'a[class*="thumb"] img',
                'a[class*="Thumb"] img',
                'div[class*="thumb"] img',
                'div[class*="Thumb"] img',
                '[class*="card"] a img',
                '[class*="card"] img',
            ];
            for (const sel of candidates) {
                const el = document.querySelector(sel);
                if (el) {
                    const cs = window.getComputedStyle(el);
                    return {
                        selector: sel,
                        src: el.src,
                        opacity: cs.opacity,
                        transition: cs.transition,
                        transitionProperty: cs.transitionProperty,
                        transitionDuration: cs.transitionDuration,
                        transitionTimingFunction: cs.transitionTimingFunction,
                        classList: el.classList.toString(),
                        complete: el.complete,
                    };
                }
            }
            return null;
        }""")

    def get_transition_style(self, selector: str) -> dict | None:
        """Return a dict with ``opacity``, ``transition``, ``transitionProperty``,
        ``transitionDuration``, and ``transitionTimingFunction`` computed styles
        for the element matching *selector*, or ``None`` if no element is found.
        """
        return self._page.evaluate(
            """(sel) => {
                const el = document.querySelector(sel);
                if (!el) return null;
                const cs = window.getComputedStyle(el);
                return {
                    opacity: cs.opacity,
                    transition: cs.transition,
                    transitionProperty: cs.transitionProperty,
                    transitionDuration: cs.transitionDuration,
                    transitionTimingFunction: cs.transitionTimingFunction,
                };
            }""",
            selector,
        )

    def get_loaded_images_opacity(self) -> list:
        """Return opacity data for fully-loaded ``img`` elements that carry an
        explicit ``opacity`` transition.  Used to verify ``opacity: 1`` after
        the ``onLoad`` callback fires.
        """
        return self._page.evaluate("""() => {
            const imgs = document.querySelectorAll('#video-grid img, main img');
            const results = [];
            for (const img of imgs) {
                if (img.complete && img.naturalWidth > 0) {
                    const cs = window.getComputedStyle(img);
                    const tp = (cs.transitionProperty || '').toLowerCase();
                    if (tp === 'opacity' || tp.includes('opacity')) {
                        results.push({
                            src: img.src.substring(0, 80),
                            opacity: parseFloat(cs.opacity),
                            classList: img.classList.toString(),
                        });
                    }
                }
            }
            return results;
        }""")
