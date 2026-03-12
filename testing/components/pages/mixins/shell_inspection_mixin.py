"""Mixin providing shell/layout inspection methods for page objects."""
from __future__ import annotations


class ShellInspectionMixin:
    """Shared shell-inspection helpers for page objects.

    Requires the mixing class to expose ``self._page`` (a Playwright ``Page``).
    """

    def has_shell_class(self) -> bool:
        """Return True if a .shell element is present in the DOM."""
        return self._page.locator(".shell").count() > 0

    def has_page_wrap_class(self) -> bool:
        """Return True if a .page-wrap element is present in the DOM."""
        return self._page.locator(".page-wrap").count() > 0

    def has_shell_like_styles(self) -> str | None:
        """Return className of first element with shell styles (borderRadius=24px, maxWidth=1320px), or None."""
        return self._page.evaluate("""() => {
            for (const el of document.querySelectorAll('body *')) {
                const s = window.getComputedStyle(el);
                if (s.borderRadius === '24px' && s.maxWidth === '1320px')
                    return el.className || el.tagName;
            }
            return null;
        }""")

    def has_shell_like_styles_excluding_auth_card(self) -> str | None:
        """Return className of first shell-styled element outside .auth-card, or None.

        The .auth-card element legitimately uses border-radius for its card design.
        This method skips any element that is a descendant of .auth-card so that
        only shell-specific layout styles are detected.
        """
        return self._page.evaluate("""() => {
            for (const el of document.querySelectorAll('body *')) {
                if (el.closest('.auth-card')) continue;
                const s = window.getComputedStyle(el);
                if (s.borderRadius === '24px' && s.maxWidth === '1320px')
                    return el.className || el.tagName;
            }
            return null;
        }""")
