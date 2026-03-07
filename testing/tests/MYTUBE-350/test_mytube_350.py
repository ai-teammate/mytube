"""
MYTUBE-350: Auth status resolving — loading indicator displayed.

Objective
---------
Verify that the application displays a loading state while the Firebase
authentication status is being determined.

Preconditions
-------------
Artificial network delay introduced to Firebase authentication initialization.
This is implemented via ``page.add_init_script()`` which wraps
``IDBFactory.prototype.open`` to delay the IndexedDB success callback.
Firebase relies on IndexedDB to read its cached auth state; delaying this
forces ``loading`` to remain ``true`` for a measurable duration.

Steps
-----
1. Load the application or navigate to a protected route (``/upload/``).
2. Observe the UI before the authentication state is confirmed.

Expected Result
---------------
The application displays an appropriate loading indicator or skeleton screen,
preventing the flickering of protected content or premature redirects.

Test approach
-------------
Protected routes are wrapped by ``RequireAuth`` (web/src/components/RequireAuth.tsx),
which renders a full-page spinner while ``loading`` is ``true``:

  <div class="animate-spin rounded-full border-4 border-blue-600 …" aria-hidden="true"/>
  <p class="text-sm text-gray-600">Loading…</p>

The test:
1. Injects an ``add_init_script`` that delays IDBFactory.prototype.open success
   callbacks by ``_IDB_DELAY_MS`` milliseconds, simulating the precondition of
   "artificial network delay to Firebase auth initialization".
2. Navigates to a protected route (``/upload/``) with ``wait_until="commit"``
   so Playwright returns as soon as the response is committed — before React
   hydration and before the delayed IDB success fires.
3. Asserts that the loading spinner and "Loading…" text are visible.
4. Waits for the auth state to resolve (IDB delay expires → Firebase callback
   fires → ``loading`` becomes ``false`` → unauthenticated user is redirected
   to ``/login/``).
5. Asserts that the loading spinner is hidden after auth resolves.

Two test cases are included:
  - ``test_loading_spinner_visible_while_auth_pending``:
      Core verification — spinner is shown during auth state resolution.
  - ``test_no_protected_content_shown_while_auth_pending``:
      Guard — protected content (upload form) is NOT rendered while loading.

Environment variables
---------------------
APP_URL / WEB_BASE_URL  Base URL of the deployed web application.
                        Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      Slow-motion delay in ms (default: 0).

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest module-scoped browser fixture.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import logging
import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page, expect

_logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms — maximum time to load the page
_LOADING_VISIBLE_TIMEOUT = 5_000  # ms — time allowed for spinner to appear
_AUTH_RESOLVE_TIMEOUT = 20_000    # ms — time for auth to resolve after delay

# Artificial delay applied to Firebase IndexedDB operations (in milliseconds).
# This simulates "artificial network delay to Firebase auth initialization"
# as specified in the preconditions.  The delay must be long enough for
# Playwright to reliably assert the loading state, but not so long that the
# test suite becomes slow.
_IDB_DELAY_MS = 3_000  # 3 seconds

# JavaScript injected before page load to delay Firebase's IndexedDB auth
# state resolution, simulating the artificial delay precondition.
_FIREBASE_DELAY_INIT_SCRIPT = f"""
(function () {{
    var _delay = {_IDB_DELAY_MS};
    var _origOpen = IDBFactory.prototype.open;

    IDBFactory.prototype.open = function () {{
        var request = _origOpen.apply(this, arguments);

        // Wrap dispatchEvent on this IDBRequest to delay 'success' events.
        // Firebase uses the IDBRequest.onsuccess / 'success' event to read
        // its cached auth user from IndexedDB.  By delaying it we extend
        // the window during which loading===true so the spinner is observable.
        var _origDispatch = request.dispatchEvent.bind(request);
        request.dispatchEvent = function (event) {{
            if (event && event.type === 'success') {{
                var self = this;
                setTimeout(function () {{ _origDispatch(event); }}, _delay);
                return true;
            }}
            return _origDispatch(event);
        }};

        // Also intercept the onsuccess property setter in case Firebase
        // attaches the handler via the property (not addEventListener).
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

# CSS selectors / text matchers for the loading indicator rendered by RequireAuth
_SPINNER_SELECTOR = ".animate-spin"
_LOADING_TEXT_SELECTOR = "text=Loading\u2026"   # "Loading…" (ellipsis U+2026)

# Selector for the upload-form title — rendered only when auth succeeds
_UPLOAD_FORM_TITLE_SELECTOR = "h1:text('Upload video')"

# URL pattern matching the login redirect
_LOGIN_URL_PATTERN = "**/login**"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuthLoadingIndicator:
    """MYTUBE-350: Loading indicator is shown while Firebase auth state resolves."""

    def test_loading_spinner_visible_while_auth_pending(
        self,
        browser: Browser,
        web_config: WebConfig,
    ) -> None:
        """Loading spinner and 'Loading…' text must be visible on a protected route
        before Firebase resolves the authentication state.

        Steps
        -----
        1. Inject IDB delay script to simulate Firebase auth initialization delay.
        2. Navigate to ``/upload/`` (a protected route) with ``wait_until="commit"``.
        3. Assert ``.animate-spin`` spinner is visible (step 3 of test spec).
        4. Assert the ``Loading…`` text is visible (step 3 of test spec).
        5. Wait for auth to resolve → redirect to ``/login/`` (step 4).
        6. Assert spinner is hidden after auth resolves (step 4).
        """
        context = browser.new_context()
        context.add_init_script(_FIREBASE_DELAY_INIT_SCRIPT)
        page: Page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

        try:
            protected_url = web_config.upload_url()
            _logger.info("Navigating to protected route: %s", protected_url)

            # Step 1+2 — navigate; return as soon as the response is committed
            # (before JS hydration and the delayed IDB success fires).
            page.goto(protected_url, wait_until="commit", timeout=_PAGE_LOAD_TIMEOUT)

            # Step 3 — spinner must be visible while auth is pending
            spinner = page.locator(_SPINNER_SELECTOR)
            expect(spinner).to_be_visible(timeout=_LOADING_VISIBLE_TIMEOUT), (
                "Expected the loading spinner (.animate-spin) to be visible on "
                f"{protected_url!r} while Firebase auth state is being resolved, "
                "but the spinner was not found. "
                "Check RequireAuth.tsx renders the spinner while loading===true."
            )

            # Step 4 — "Loading…" text must also be visible
            loading_text = page.locator(_LOADING_TEXT_SELECTOR)
            expect(loading_text).to_be_visible(timeout=_LOADING_VISIBLE_TIMEOUT), (
                "Expected the 'Loading…' text to be visible on "
                f"{protected_url!r} while Firebase auth state is pending, "
                "but it was not found. "
                "Check RequireAuth.tsx renders the loading paragraph."
            )

            _logger.info(
                "Loading indicator confirmed visible; waiting for auth to resolve…"
            )

            # Step 5 — wait for auth to resolve; unauthenticated users are
            # redirected to /login/?next=<path>
            try:
                page.wait_for_url(_LOGIN_URL_PATTERN, timeout=_AUTH_RESOLVE_TIMEOUT)
                _logger.info("Redirected to login page: %s", page.url)
            except Exception as exc:
                _logger.warning(
                    "wait_for_url to login timed out (%s); checking spinner state.", exc
                )

            # Step 6 — spinner must be hidden after auth resolves
            expect(spinner).to_be_hidden(timeout=_AUTH_RESOLVE_TIMEOUT), (
                "Expected the loading spinner to disappear after Firebase auth "
                "state resolved, but the spinner is still visible. "
                f"Current URL: {page.url!r}."
            )

        finally:
            context.close()

    def test_no_protected_content_shown_while_auth_pending(
        self,
        browser: Browser,
        web_config: WebConfig,
    ) -> None:
        """Protected content (upload form) must NOT be rendered while auth is loading.

        While the loading indicator is visible, the upload form title
        ('Upload video') must not be present.  This ensures the loading guard
        prevents flickering of protected content before auth is confirmed.

        Steps
        -----
        1. Inject IDB delay script.
        2. Navigate to ``/upload/`` with ``wait_until="commit"``.
        3. Assert spinner is visible (auth still loading).
        4. Assert upload form title is NOT visible (no premature render of
           protected content).
        5. Release the delay and wait for redirect to login.
        """
        context = browser.new_context()
        context.add_init_script(_FIREBASE_DELAY_INIT_SCRIPT)
        page: Page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

        try:
            protected_url = web_config.upload_url()

            page.goto(protected_url, wait_until="commit", timeout=_PAGE_LOAD_TIMEOUT)

            # Confirm we are in the loading state
            spinner = page.locator(_SPINNER_SELECTOR)
            expect(spinner).to_be_visible(timeout=_LOADING_VISIBLE_TIMEOUT)

            # Protected content must NOT appear while auth is pending
            upload_form_title = page.locator(_UPLOAD_FORM_TITLE_SELECTOR)
            assert not upload_form_title.is_visible(), (
                "Protected content ('Upload video' form title) was rendered "
                "before Firebase auth state resolved. "
                "RequireAuth must render only the loading spinner while "
                f"loading===true. Current URL: {page.url!r}."
            )

            _logger.info(
                "Confirmed: protected content hidden while auth is loading."
            )

            # Wait for auth to resolve
            try:
                page.wait_for_url(_LOGIN_URL_PATTERN, timeout=_AUTH_RESOLVE_TIMEOUT)
            except Exception as exc:
                _logger.warning(
                    "wait_for_url to login timed out (%s).", exc
                )

        finally:
            context.close()

    def test_loading_indicator_on_dashboard_route(
        self,
        browser: Browser,
        web_config: WebConfig,
    ) -> None:
        """Loading indicator must also appear on the /dashboard/ protected route.

        Verifies the loading behaviour is consistent across multiple protected
        routes, not just /upload/.
        """
        context = browser.new_context()
        context.add_init_script(_FIREBASE_DELAY_INIT_SCRIPT)
        page: Page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

        try:
            dashboard_url = web_config.dashboard_url()
            _logger.info("Navigating to protected route: %s", dashboard_url)

            page.goto(dashboard_url, wait_until="commit", timeout=_PAGE_LOAD_TIMEOUT)

            spinner = page.locator(_SPINNER_SELECTOR)
            expect(spinner).to_be_visible(timeout=_LOADING_VISIBLE_TIMEOUT), (
                "Expected the loading spinner to be visible on "
                f"{dashboard_url!r} while Firebase auth state is pending. "
                "Check that RequireAuth is used on the dashboard page."
            )

            loading_text = page.locator(_LOADING_TEXT_SELECTOR)
            expect(loading_text).to_be_visible(timeout=_LOADING_VISIBLE_TIMEOUT), (
                "Expected 'Loading…' text to be visible on "
                f"{dashboard_url!r} while auth state is pending."
            )

            # Wait for auth to resolve
            try:
                page.wait_for_url(_LOGIN_URL_PATTERN, timeout=_AUTH_RESOLVE_TIMEOUT)
            except Exception as exc:
                _logger.warning(
                    "wait_for_url to login timed out (%s).", exc
                )

            expect(spinner).to_be_hidden(timeout=_AUTH_RESOLVE_TIMEOUT)

        finally:
            context.close()
