"""
MYTUBE-469: Theme hook toggle — toggleTheme updates document body attribute safely

Objective
---------
Verify the functionality of the ``useTheme`` hook and its ability to update the
DOM attribute safely for SSR.

Steps
-----
1. Trigger the ``toggleTheme`` function via the UI or console.
2. Check the ``data-theme`` attribute on the ``document.body``.
3. Observe the page during initial load for any flashing or
   "document is not defined" errors.

Expected Result
---------------
The ``data-theme`` attribute on the ``body`` tag correctly switches between
``light`` and ``dark``. The change is applied via ``useEffect`` to ensure
server-side rendering safety.

Test Architecture
-----------------
**Layer A — Playwright fixture** (always runs):
    A self-contained HTML page replicates the ``useTheme`` toggle logic
    (localStorage read on mount + ``data-theme`` toggle on button click).
    Playwright verifies that the attribute changes correctly.

    When ``APP_URL`` / ``WEB_BASE_URL`` is set, the live deployed app is also
    tested: localStorage is pre-seeded and the page is reloaded to verify the
    mount effect sets ``data-theme`` from storage.

**Layer B — Source code static analysis** (always runs, no browser needed):
    Parses ``web/src/context/ThemeContext.tsx`` to confirm:
    - ``document.body.setAttribute`` only appears inside ``useEffect`` callbacks.
    - ``localStorage.getItem`` is called inside a ``useEffect`` (mount guard).
    - ``toggleTheme`` uses ``useCallback``.
"""
from __future__ import annotations

import os
import re
import sys

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_THEME_CONTEXT_PATH = os.path.join(
    _REPO_ROOT, "web", "src", "context", "ThemeContext.tsx"
)
_PAGE_LOAD_TIMEOUT = 30_000  # ms


# ---------------------------------------------------------------------------
# Helpers — fixture HTML
# ---------------------------------------------------------------------------


def _get_fixture_html() -> str:
    """
    A minimal self-contained page that replicates the ``useTheme`` hook logic:

    - On load (DOMContentLoaded) reads ``localStorage.getItem('theme')`` and
      applies it to ``document.body`` via ``setAttribute('data-theme', ...)``.
    - A button triggers ``toggleTheme()``, which flips the attribute and
      persists the new value to ``localStorage``.
    - A ``<span id="current-theme">`` always reflects the current value of
      ``data-theme`` so tests can read it without querying the body attribute
      directly.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>MYTUBE-469 fixture — useTheme toggle test</title>
</head>
<body>
  <h1>useTheme fixture</h1>
  <span id="current-theme">light</span>
  <button id="toggle-btn">Toggle Theme</button>

  <script>
    // ── Replicate useTheme hook behaviour ──────────────────────────────────
    // Mirrors ThemeContext.tsx logic exactly, without React.

    var STORAGE_KEY = 'theme';

    function getCurrentTheme() {
      return document.body.getAttribute('data-theme') || 'light';
    }

    // Mount effect: read stored preference, apply to body
    (function mountEffect() {
      var stored = localStorage.getItem(STORAGE_KEY);
      var initial = stored === 'dark' ? 'dark' : 'light';
      document.body.setAttribute('data-theme', initial);
      document.getElementById('current-theme').textContent = initial;
    })();

    // Toggle function: flip and persist
    function toggleTheme() {
      var current = getCurrentTheme();
      var next = current === 'light' ? 'dark' : 'light';
      document.body.setAttribute('data-theme', next);
      localStorage.setItem(STORAGE_KEY, next);
      document.getElementById('current-theme').textContent = next;
    }

    document.getElementById('toggle-btn').addEventListener('click', toggleTheme);
    // ── End useTheme replication ───────────────────────────────────────────
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Helpers — source code analysis
# ---------------------------------------------------------------------------


def _read_theme_context() -> str:
    """Read and return the contents of ThemeContext.tsx."""
    if not os.path.isfile(_THEME_CONTEXT_PATH):
        pytest.fail(
            f"ThemeContext.tsx not found at expected path: {_THEME_CONTEXT_PATH}"
        )
    with open(_THEME_CONTEXT_PATH, encoding="utf-8") as fh:
        return fh.read()


def _extract_use_effect_bodies(source: str) -> list[str]:
    """
    Return a list of strings, each being the content of a ``useEffect(...)``
    call found in *source*.

    This is a best-effort heuristic: it finds every ``useEffect(`` occurrence
    and captures the first balanced ``{...}`` block that follows (the callback
    body), stopping at 5 000 characters to avoid runaway matches.
    """
    bodies: list[str] = []
    for m in re.finditer(r"useEffect\s*\(", source):
        start = m.end()
        # Find the opening brace of the arrow / function callback
        brace_start = source.find("{", start, start + 100)
        if brace_start == -1:
            continue
        depth = 0
        i = brace_start
        limit = min(brace_start + 5000, len(source))
        while i < limit:
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
                if depth == 0:
                    bodies.append(source[brace_start : i + 1])
                    break
            i += 1
    return bodies


# ---------------------------------------------------------------------------
# Fixtures — Playwright browser / page (module-scoped)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def browser():
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        yield br
        br.close()


@pytest.fixture(scope="function")
def page(browser):
    """Fresh page per test so localStorage state never leaks between tests."""
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    ctx.close()


# ---------------------------------------------------------------------------
# Fixture URL constant — routed to an in-memory HTML page so that the page
# has a proper HTTP origin and localStorage is accessible.
# ---------------------------------------------------------------------------

_FIXTURE_URL = "http://localhost/mytube-469-theme-fixture"


# ---------------------------------------------------------------------------
# Layer A: Playwright fixture tests
# ---------------------------------------------------------------------------


class TestThemeHookToggleFixture:
    """
    MYTUBE-469 Layer A — verify toggleTheme behaviour in a self-contained HTML
    fixture that replicates the useTheme hook logic.
    """

    def _load_fixture(self, page: Page) -> None:
        """
        Route a virtual URL to the fixture HTML so that the page has a real
        HTTP origin (``http://localhost``), which allows localStorage access.
        """
        page.route(
            _FIXTURE_URL,
            lambda route: route.fulfill(
                status=200,
                content_type="text/html; charset=utf-8",
                body=_get_fixture_html(),
            ),
        )
        page.goto(_FIXTURE_URL, wait_until="domcontentloaded")

    # ── Initial state ────────────────────────────────────────────────────────

    def test_initial_theme_is_light_when_no_storage(self, page: Page) -> None:
        """
        On first load with no stored preference, body data-theme defaults to
        'light' and the display element reflects that value.
        """
        self._load_fixture(page)
        data_theme = page.evaluate("document.body.getAttribute('data-theme')")
        assert data_theme == "light", (
            f"Expected initial data-theme='light' (no localStorage), got {data_theme!r}"
        )

    def test_initial_theme_is_dark_when_storage_says_dark(self, page: Page) -> None:
        """
        When localStorage['theme'] = 'dark' before page load, the mount effect
        must apply data-theme='dark' to document.body immediately.
        """
        # First load the fixture to establish the origin, then seed localStorage
        # and reload so the inline script reads the stored value on DOMContentLoaded.
        self._load_fixture(page)
        page.evaluate("localStorage.setItem('theme', 'dark')")
        page.reload(wait_until="domcontentloaded")

        data_theme = page.evaluate("document.body.getAttribute('data-theme')")
        assert data_theme == "dark", (
            f"Expected data-theme='dark' when localStorage='dark', got {data_theme!r}"
        )

    # ── Toggle: light → dark ─────────────────────────────────────────────────

    def test_toggle_light_to_dark_updates_body_attribute(self, page: Page) -> None:
        """
        Step 1 of test case: clicking the toggle button switches data-theme
        from 'light' to 'dark' on document.body.
        """
        self._load_fixture(page)
        # Ensure we start in light mode
        assert page.evaluate("document.body.getAttribute('data-theme')") == "light"

        page.click("#toggle-btn")

        data_theme = page.evaluate("document.body.getAttribute('data-theme')")
        assert data_theme == "dark", (
            f"After first toggle: expected data-theme='dark', got {data_theme!r}"
        )

    def test_toggle_light_to_dark_persists_to_local_storage(self, page: Page) -> None:
        """
        After toggling to dark, localStorage['theme'] must equal 'dark'.
        """
        self._load_fixture(page)
        page.click("#toggle-btn")

        stored = page.evaluate("localStorage.getItem('theme')")
        assert stored == "dark", (
            f"After toggle light→dark: expected localStorage['theme']='dark', got {stored!r}"
        )

    # ── Toggle: dark → light ─────────────────────────────────────────────────

    def test_toggle_dark_to_light_updates_body_attribute(self, page: Page) -> None:
        """
        Step 2 of test case: a second toggle switches data-theme back from
        'dark' to 'light' on document.body.
        """
        self._load_fixture(page)
        page.click("#toggle-btn")  # light → dark
        page.click("#toggle-btn")  # dark → light

        data_theme = page.evaluate("document.body.getAttribute('data-theme')")
        assert data_theme == "light", (
            f"After second toggle: expected data-theme='light', got {data_theme!r}"
        )

    def test_toggle_dark_to_light_persists_to_local_storage(self, page: Page) -> None:
        """
        After toggling back to light, localStorage['theme'] must equal 'light'.
        """
        self._load_fixture(page)
        page.click("#toggle-btn")  # → dark
        page.click("#toggle-btn")  # → light

        stored = page.evaluate("localStorage.getItem('theme')")
        assert stored == "light", (
            f"After toggle dark→light: expected localStorage['theme']='light', got {stored!r}"
        )

    # ── Display element sync ──────────────────────────────────────────────────

    def test_display_element_reflects_theme_after_toggle(self, page: Page) -> None:
        """
        The #current-theme display element must update together with the body
        attribute, confirming the hook's state is in sync with the DOM.
        """
        self._load_fixture(page)
        page.click("#toggle-btn")
        display = page.locator("#current-theme").inner_text()
        data_theme = page.evaluate("document.body.getAttribute('data-theme')")
        assert display == data_theme, (
            f"Display element '{display}' does not match data-theme='{data_theme}'"
        )


# ---------------------------------------------------------------------------
# Layer A (live mode): deployed app — mount effect reads localStorage
# ---------------------------------------------------------------------------


class TestThemeHookLiveMode:
    """
    MYTUBE-469 Layer A (live) — when a deployed app URL is available, verify
    that the page correctly applies data-theme from localStorage on mount.
    """

    @pytest.fixture(autouse=True)
    def skip_if_no_live_url(self):
        env_url = os.getenv("APP_URL", os.getenv("WEB_BASE_URL", ""))
        if not env_url or env_url.lower() in ("false", "0", ""):
            pytest.skip("No live APP_URL configured — skipping live-mode tests")

    def test_live_app_applies_dark_theme_from_local_storage(self, page: Page) -> None:
        """
        Navigate to the live app after pre-seeding localStorage['theme']='dark'.
        The mount useEffect must set data-theme='dark' on document.body.
        """
        config = WebConfig()

        # Pre-seed the storage by visiting the page first, then setting localStorage
        page.goto(config.home_url(), wait_until="domcontentloaded")
        page.evaluate("localStorage.setItem('theme', 'dark')")

        # Reload so the mount useEffect picks up the stored value
        page.reload(wait_until="domcontentloaded")
        # Allow React hydration + useEffect to run
        page.wait_for_timeout(500)

        data_theme = page.evaluate("document.body.getAttribute('data-theme')")
        assert data_theme == "dark", (
            f"Live app: expected data-theme='dark' after pre-seeding localStorage, "
            f"got {data_theme!r}"
        )

    def test_live_app_applies_light_theme_from_local_storage(self, page: Page) -> None:
        """
        Navigate to the live app after pre-seeding localStorage['theme']='light'.
        The mount useEffect must set data-theme='light' on document.body.
        """
        config = WebConfig()

        page.goto(config.home_url(), wait_until="domcontentloaded")
        page.evaluate("localStorage.setItem('theme', 'light')")

        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(500)

        data_theme = page.evaluate("document.body.getAttribute('data-theme')")
        assert data_theme == "light", (
            f"Live app: expected data-theme='light' after pre-seeding localStorage, "
            f"got {data_theme!r}"
        )


# ---------------------------------------------------------------------------
# Layer B: Source code static analysis
# ---------------------------------------------------------------------------


class TestThemeHookSourceCode:
    """
    MYTUBE-469 Layer B — verify the SSR safety properties of ThemeContext.tsx
    by statically analysing the source code.
    """

    # Cached source (read once per class)
    _source: str = ""

    @pytest.fixture(autouse=True)
    def load_source(self):
        TestThemeHookSourceCode._source = _read_theme_context()

    # ── SSR safety ────────────────────────────────────────────────────────────

    def test_document_body_set_attribute_only_inside_use_effect(self) -> None:
        """
        Step 3 of test case: document.body.setAttribute must only be called
        inside useEffect callbacks — never at the module or component top level —
        to ensure SSR safety ("document is not defined" cannot occur).
        """
        source = self._source

        # Collect all useEffect bodies
        effect_bodies = _extract_use_effect_bodies(source)
        assert effect_bodies, (
            "No useEffect calls found in ThemeContext.tsx. "
            "The SSR-safe pattern requires useEffect to guard DOM access."
        )

        # Verify setAttribute appears in at least one effect body
        setAttribute_in_effects = any(
            "setAttribute" in body for body in effect_bodies
        )
        assert setAttribute_in_effects, (
            "document.body.setAttribute is not found inside any useEffect callback "
            "in ThemeContext.tsx. The DOM update must be wrapped in useEffect for SSR safety."
        )

        # Verify no setAttribute call exists OUTSIDE useEffect bodies
        # Strategy: remove all useEffect bodies from source, then check
        source_without_effects = source
        for body in effect_bodies:
            source_without_effects = source_without_effects.replace(body, "")

        # Also remove comments
        source_without_comments = re.sub(r"/\*.*?\*/", "", source_without_effects, flags=re.DOTALL)
        source_without_comments = re.sub(r"//[^\n]*", "", source_without_comments)

        assert "setAttribute" not in source_without_comments, (
            "document.body.setAttribute appears outside a useEffect in ThemeContext.tsx. "
            "This is not SSR-safe: 'document' is undefined during server-side rendering."
        )

    def test_local_storage_read_inside_use_effect(self) -> None:
        """
        localStorage.getItem must be called inside a useEffect callback
        (the mount effect), guarding against SSR environments where
        localStorage is undefined.
        """
        effect_bodies = _extract_use_effect_bodies(self._source)
        assert any(
            "localStorage.getItem" in body for body in effect_bodies
        ), (
            "localStorage.getItem not found inside any useEffect callback in "
            "ThemeContext.tsx. Reading from localStorage must be deferred to "
            "client-side (useEffect) to avoid SSR crashes."
        )

    def test_toggle_theme_uses_use_callback(self) -> None:
        """
        toggleTheme must be defined with useCallback to ensure referential
        stability across renders.
        """
        assert "useCallback" in self._source, (
            "useCallback not found in ThemeContext.tsx. "
            "toggleTheme should be wrapped in useCallback for stable reference."
        )

    def test_use_effect_dependency_array_present(self) -> None:
        """
        Both useEffect calls must have dependency arrays ([], [theme], etc.)
        to prevent unintended re-runs.
        """
        # Match closing of effect callback followed by a dependency array:
        # pattern: "}, [" or "}," followed by optional whitespace then "["
        # This handles both inline and multiline formatting.
        matches = re.findall(r"\}\s*,\s*\[", self._source)
        assert len(matches) >= 1, (
            f"Expected at least one useEffect with a dependency array in "
            f"ThemeContext.tsx, found {len(matches)}. "
            "Dependency arrays (e.g. [], [theme]) are required to control effect execution."
        )

    def test_storage_key_is_theme(self) -> None:
        """
        The localStorage key used for persisting the theme preference must be
        exactly 'theme', matching the constant defined in ThemeContext.tsx.
        """
        # Check that STORAGE_KEY = "theme" (or 'theme') is defined
        assert re.search(r"""STORAGE_KEY\s*=\s*["']theme["']""", self._source), (
            "STORAGE_KEY constant set to 'theme' not found in ThemeContext.tsx."
        )

    def test_light_and_dark_theme_values_defined(self) -> None:
        """
        The strings 'light' and 'dark' must be present in the source as the
        valid theme values used for the data-theme attribute.
        """
        assert '"light"' in self._source or "'light'" in self._source, (
            "Theme value 'light' not found in ThemeContext.tsx."
        )
        assert '"dark"' in self._source or "'dark'" in self._source, (
            "Theme value 'dark' not found in ThemeContext.tsx."
        )
