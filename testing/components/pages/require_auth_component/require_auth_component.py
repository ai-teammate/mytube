"""RequireAuthComponent — Page Object for the RequireAuth loading overlay.

Encapsulates all selectors and assertion methods for the loading state rendered
by ``RequireAuth`` (web/src/components/RequireAuth.tsx) while Firebase
authentication status is being resolved.

The RequireAuth component renders the following while ``loading === true``:

  <div class="min-h-screen flex items-center justify-center">
    <div class="flex flex-col items-center gap-3">
      <div class="h-8 w-8 animate-spin rounded-full border-4 border-blue-600
                  border-t-transparent" aria-hidden="true" />
      <p class="text-sm text-gray-600">Loading…</p>
    </div>
  </div>

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- All waits use Playwright's built-in auto-wait mechanisms (``expect``).
- No hardcoded URLs — callers handle navigation.
- The IDB-delay init script constant is exposed as a class-level attribute so
  any test can inject it without re-implementing the mechanism.
"""
from __future__ import annotations

from playwright.sync_api import Page, expect

# ---------------------------------------------------------------------------
# IDB delay script (class constant) so any test can reuse without duplicating
# ---------------------------------------------------------------------------

#: Milliseconds to delay Firebase's IndexedDB success callbacks.
#: This keeps ``loading === true`` for a measurable window so assertions
#: against the loading state are reliable.
FIREBASE_IDB_DELAY_MS: int = 3_000

#: JavaScript init script that wraps ``IDBFactory.prototype.open`` to delay
#: the ``success`` event / ``onsuccess`` handler by ``FIREBASE_IDB_DELAY_MS`` ms.
#: Inject with ``context.add_init_script(FIREBASE_DELAY_INIT_SCRIPT)`` before
#: navigating to any protected route.
FIREBASE_DELAY_INIT_SCRIPT: str = f"""
(function () {{
    var _delay = {FIREBASE_IDB_DELAY_MS};
    var _origOpen = IDBFactory.prototype.open;

    IDBFactory.prototype.open = function () {{
        var request = _origOpen.apply(this, arguments);

        // Delay 'success' dispatch events so Firebase auth state resolution
        // is postponed, keeping loading===true for _delay ms.
        var _origDispatch = request.dispatchEvent.bind(request);
        request.dispatchEvent = function (event) {{
            if (event && event.type === 'success') {{
                var self = this;
                setTimeout(function () {{ _origDispatch(event); }}, _delay);
                return true;
            }}
            return _origDispatch(event);
        }};

        // Also intercept the onsuccess property setter for Firebase's
        // property-based callback attachment pattern.
        var _storedHandler = null;
        Object.defineProperty(request, 'onsuccess', {{
            get: function () {{ return _storedHandler; }},
            set: function (fn) {{
                _storedHandler = fn
                    ? function (event) {{
                          var self = this;
                          setTimeout(function () {{ fn.call(self, event); }}, _delay);
                      }}
                    : fn;
            }},
            configurable: true,
        }});

        return request;
    }};
}})();
"""


class RequireAuthComponent:
    """Page Object for the RequireAuth loading overlay rendered by Firebase auth.

    Owns all selectors for the spinner and "Loading…" text, and exposes
    high-level assertion methods for use in tests.

    Parameters
    ----------
    page:
        The Playwright ``Page`` instance for the current browser tab.
    loading_visible_timeout:
        Maximum time in ms to wait for the loading indicator to appear.
        Defaults to 5 000 ms.
    auth_resolve_timeout:
        Maximum time in ms to wait for the auth state to resolve (spinner
        to disappear / redirect to login).  Defaults to 20 000 ms.
    """

    # CSS selectors — mirror RequireAuth.tsx render output
    _SPINNER_SELECTOR = ".animate-spin"
    _LOADING_TEXT_SELECTOR = "text=Loading\u2026"    # "Loading…" (U+2026)
    _UPLOAD_FORM_TITLE_SELECTOR = "h1:text('Upload video')"

    # URL pattern matching post-auth redirect for unauthenticated users
    _LOGIN_URL_PATTERN = "**/login**"

    def __init__(
        self,
        page: Page,
        loading_visible_timeout: int = 5_000,
        auth_resolve_timeout: int = 20_000,
    ) -> None:
        self._page = page
        self._loading_visible_timeout = loading_visible_timeout
        self._auth_resolve_timeout = auth_resolve_timeout

    # ------------------------------------------------------------------
    # Assertions
    # ------------------------------------------------------------------

    def assert_loading_spinner_visible(self) -> None:
        """Assert that the ``.animate-spin`` loading spinner is visible."""
        expect(
            self._page.locator(self._SPINNER_SELECTOR),
            message=(
                "Expected the loading spinner (.animate-spin) to be visible "
                "while Firebase auth state is being resolved. "
                "Check that RequireAuth.tsx renders the spinner while loading===true."
            ),
        ).to_be_visible(timeout=self._loading_visible_timeout)

    def assert_loading_text_visible(self) -> None:
        """Assert that the 'Loading…' paragraph is visible."""
        expect(
            self._page.locator(self._LOADING_TEXT_SELECTOR),
            message=(
                "Expected the 'Loading…' paragraph to be visible while "
                "Firebase auth state is being resolved. "
                "Check that RequireAuth.tsx renders the loading paragraph."
            ),
        ).to_be_visible(timeout=self._loading_visible_timeout)

    def assert_spinner_hidden(self) -> None:
        """Assert that the ``.animate-spin`` spinner has disappeared."""
        expect(
            self._page.locator(self._SPINNER_SELECTOR),
            message=(
                "Expected the loading spinner to disappear after Firebase auth "
                "state resolved, but the spinner is still visible."
            ),
        ).to_be_hidden(timeout=self._auth_resolve_timeout)

    def assert_upload_form_title_hidden(self) -> None:
        """Assert that the 'Upload video' form title is NOT visible.

        Uses Playwright's retry-based ``to_be_hidden`` (rather than a one-shot
        ``is_visible()`` check) so the assertion is resilient under varying CI load.
        """
        expect(
            self._page.locator(self._UPLOAD_FORM_TITLE_SELECTOR),
            message=(
                "Protected content ('Upload video' form title) was rendered "
                "before Firebase auth state resolved. "
                "RequireAuth must render only the loading spinner while loading===true."
            ),
        ).to_be_hidden(timeout=self._loading_visible_timeout)

    # ------------------------------------------------------------------
    # Helper actions
    # ------------------------------------------------------------------

    def wait_for_auth_redirect_to_login(self) -> None:
        """Wait for the unauthenticated redirect to ``/login/``.

        Silently swallows timeouts — tests that call this method should
        separately assert the post-auth state using the assertion methods above.
        """
        try:
            self._page.wait_for_url(
                self._LOGIN_URL_PATTERN,
                timeout=self._auth_resolve_timeout,
            )
        except Exception:
            pass
