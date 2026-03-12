"""
MYTUBE-457: Auth card layout and styling — container matches redesign specifications

Objective
---------
Verify that the login and registration pages use the centered auth card design
with specific styling tokens.

Steps
-----
1. Navigate to the /login or /register page.
2. Inspect the page background and centering.
3. Inspect the .auth-card element styles.

Expected Result
---------------
The page background is set to var(--bg-page) with min-height: 100vh and elements
are centered. The .auth-card has:
  - background: var(--bg-login)
  - border-radius: 24px
  - border: 1.5px solid var(--accent-login-border)
  - box-shadow: var(--shadow-main)
  - max-width: 400px

Test Approach
-------------
Dual-mode:

1. **Live Mode** (primary) — When APP_URL / WEB_BASE_URL is set, Playwright
   navigates to the deployed application and reads the computed styles of the
   page container and .auth-card elements.

2. **Static Mode** (fallback) — When no deployed URL is available, the test
   analyses the React source files (login/page.tsx and register/page.tsx) and
   globals.css directly to assert the correct CSS tokens and inline styles are
   in place.  This keeps the suite green in offline / build-only environments.

Run from repo root:
    pytest testing/tests/MYTUBE-457/test_mytube_457.py -v
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WEB_SRC = _REPO_ROOT / "web" / "src"
_LOGIN_PAGE = _WEB_SRC / "app" / "login" / "page.tsx"
_REGISTER_PAGE = _WEB_SRC / "app" / "register" / "page.tsx"
_GLOBALS_CSS = _WEB_SRC / "app" / "globals.css"

# ---------------------------------------------------------------------------
# Expected values (from redesign specification)
# ---------------------------------------------------------------------------

# Page container
_EXPECTED_CONTAINER_CLASSES = {"min-h-screen", "flex", "items-center", "justify-center"}
_EXPECTED_CONTAINER_BG_TOKEN = "var(--bg-page)"

# Auth card inline style values
_EXPECTED_CARD_BG = "var(--bg-login)"
_EXPECTED_CARD_BORDER_RADIUS_PX = 24  # rendered as "24px"
_EXPECTED_CARD_BORDER = "1.5px solid var(--accent-login-border)"
_EXPECTED_CARD_SHADOW = "var(--shadow-main)"
_EXPECTED_CARD_MAX_WIDTH_PX = 400  # rendered as "400px"

# Page load timeout in ms for Playwright
_PAGE_LOAD_TIMEOUT = 30_000

# ---------------------------------------------------------------------------
# Mode helpers
# ---------------------------------------------------------------------------


def _should_use_live_mode() -> bool:
    env_url = os.getenv("APP_URL", os.getenv("WEB_BASE_URL", ""))
    return bool(env_url and env_url.lower() not in ("false", "0", ""))


# ---------------------------------------------------------------------------
# Static analysis helpers
# ---------------------------------------------------------------------------


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_container_bg_inline_style(source: str, page_label: str) -> None:
    """Assert that the outermost page container has background: var(--bg-page) in an inline style."""
    pattern = re.compile(
        r'className=["\'][^"\']*min-h-screen[^"\']*["\'][^}]*?style=\{\{[^}]*background:\s*["\']var\(--bg-page\)["\']',
        re.DOTALL,
    )
    assert pattern.search(source), (
        f"{page_label}: expected outer container to have className containing 'min-h-screen' "
        f"and inline style with background: var(--bg-page). "
        f"Check the outermost <div> in the page component."
    )


def _assert_container_centering_classes(source: str, page_label: str) -> None:
    """Assert that the page container includes Tailwind centering classes."""
    for cls in _EXPECTED_CONTAINER_CLASSES:
        assert cls in source, (
            f"{page_label}: expected className '{cls}' to be present on the outer container div. "
            f"The page must use flex centering to satisfy the redesign specification."
        )


def _assert_auth_card_bg(source: str, page_label: str) -> None:
    """Assert that .auth-card has background: var(--bg-login)."""
    pattern = re.compile(
        r'className=["\'][^"\']*auth-card[^"\']*["\'][^}]*?style=\{\{[^}]*background:\s*["\']var\(--bg-login\)["\']',
        re.DOTALL,
    )
    assert pattern.search(source), (
        f"{page_label}: .auth-card must have inline style background: var(--bg-login). "
        f"Ensure the auth card <div> has both className='auth-card ...' and "
        f"style={{{{ background: 'var(--bg-login)', ... }}}}."
    )


def _assert_auth_card_border_radius(source: str, page_label: str) -> None:
    """Assert that .auth-card has borderRadius: 24."""
    pattern = re.compile(
        r'className=["\'][^"\']*auth-card[^"\']*["\'][^}]*?style=\{\{[^}]*borderRadius:\s*24[^0-9]',
        re.DOTALL,
    )
    assert pattern.search(source), (
        f"{page_label}: .auth-card must have inline style borderRadius: 24 (renders as 24px). "
        f"Found in the auth card <div> style prop."
    )


def _assert_auth_card_border(source: str, page_label: str) -> None:
    """Assert that .auth-card has border: '1.5px solid var(--accent-login-border)'."""
    pattern = re.compile(
        r'className=["\'][^"\']*auth-card[^"\']*["\'][^}]*?style=\{\{[^}]*border:\s*["\']1\.5px solid var\(--accent-login-border\)["\']',
        re.DOTALL,
    )
    assert pattern.search(source), (
        f"{page_label}: .auth-card must have inline style "
        f"border: '1.5px solid var(--accent-login-border)'. "
        f"Ensure the auth card uses the correct border token."
    )


def _assert_auth_card_box_shadow(source: str, page_label: str) -> None:
    """Assert that .auth-card has boxShadow: 'var(--shadow-main)'."""
    pattern = re.compile(
        r'className=["\'][^"\']*auth-card[^"\']*["\'][^}]*?style=\{\{[^}]*boxShadow:\s*["\']var\(--shadow-main\)["\']',
        re.DOTALL,
    )
    assert pattern.search(source), (
        f"{page_label}: .auth-card must have inline style boxShadow: 'var(--shadow-main)'. "
        f"Ensure the auth card uses the correct shadow token."
    )


def _assert_auth_card_max_width(source: str, page_label: str) -> None:
    """Assert that .auth-card has maxWidth: 400."""
    pattern = re.compile(
        r'className=["\'][^"\']*auth-card[^"\']*["\'][^}]*?style=\{\{[^}]*maxWidth:\s*400[^0-9]',
        re.DOTALL,
    )
    assert pattern.search(source), (
        f"{page_label}: .auth-card must have inline style maxWidth: 400 (renders as 400px). "
        f"Ensure the auth card is constrained to 400px maximum width."
    )


# ---------------------------------------------------------------------------
# Live Playwright helpers
# ---------------------------------------------------------------------------


def _get_page_container_styles(page, url: str) -> dict:
    """Navigate to url and return inline-style properties of the page wrapper."""
    page.goto(url, timeout=_PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")
    page.wait_for_selector(".auth-card", timeout=20_000)

    return page.evaluate("""() => {
        // The outer wrapper is the direct parent of .auth-card
        const card = document.querySelector('.auth-card');
        const container = card ? card.parentElement : null;
        if (!container) return {};
        const cs = window.getComputedStyle(container);
        return {
            minHeight: cs.minHeight,
            display:   cs.display,
            alignItems: cs.alignItems,
            justifyContent: cs.justifyContent,
            background: container.style.background || cs.backgroundColor,
        };
    }""")


def _get_auth_card_styles(page) -> dict:
    """Return computed and inline styles of the .auth-card element."""
    return page.evaluate("""() => {
        const card = document.querySelector('.auth-card');
        if (!card) return {};
        const cs = window.getComputedStyle(card);
        return {
            background:    card.style.background,
            borderRadius:  cs.borderRadius,
            border:        card.style.border,
            boxShadow:     card.style.boxShadow,
            maxWidth:      card.style.maxWidth,
        };
    }""")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def live_pages(config: WebConfig):
    """Yields (login_page, register_page) Playwright Page objects for live tests."""
    if not _should_use_live_mode():
        pytest.skip("Live mode skipped: APP_URL/WEB_BASE_URL not set")

    from playwright.sync_api import sync_playwright

    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        login_page = browser.new_page()
        register_page = browser.new_page()
        yield login_page, register_page
        browser.close()


# ---------------------------------------------------------------------------
# Static tests (always run — no browser required)
# ---------------------------------------------------------------------------


class TestAuthCardStaticAnalysis:
    """MYTUBE-457 (Static): Verify auth-card styling tokens in source files."""

    @pytest.mark.parametrize("page_file,label", [
        (_LOGIN_PAGE, "login/page.tsx"),
        (_REGISTER_PAGE, "register/page.tsx"),
    ])
    def test_page_container_has_bg_page_style(self, page_file: Path, label: str) -> None:
        """
        Step 2 (static) — outer container must declare background: var(--bg-page).
        The Tailwind class 'min-h-screen' and inline style ensure the background
        fills the full viewport with the correct design token.
        """
        source = _read_source(page_file)
        _assert_container_bg_inline_style(source, label)

    @pytest.mark.parametrize("page_file,label", [
        (_LOGIN_PAGE, "login/page.tsx"),
        (_REGISTER_PAGE, "register/page.tsx"),
    ])
    def test_page_container_has_centering_classes(self, page_file: Path, label: str) -> None:
        """
        Step 2 (static) — outer container must have flex + centering Tailwind classes:
        min-h-screen, flex, items-center, justify-center.
        """
        source = _read_source(page_file)
        _assert_container_centering_classes(source, label)

    @pytest.mark.parametrize("page_file,label", [
        (_LOGIN_PAGE, "login/page.tsx"),
        (_REGISTER_PAGE, "register/page.tsx"),
    ])
    def test_auth_card_has_bg_login(self, page_file: Path, label: str) -> None:
        """
        Step 3 (static) — .auth-card must have background: var(--bg-login).
        """
        source = _read_source(page_file)
        _assert_auth_card_bg(source, label)

    @pytest.mark.parametrize("page_file,label", [
        (_LOGIN_PAGE, "login/page.tsx"),
        (_REGISTER_PAGE, "register/page.tsx"),
    ])
    def test_auth_card_has_border_radius_24(self, page_file: Path, label: str) -> None:
        """
        Step 3 (static) — .auth-card must have borderRadius: 24 (renders as 24px).
        """
        source = _read_source(page_file)
        _assert_auth_card_border_radius(source, label)

    @pytest.mark.parametrize("page_file,label", [
        (_LOGIN_PAGE, "login/page.tsx"),
        (_REGISTER_PAGE, "register/page.tsx"),
    ])
    def test_auth_card_has_correct_border(self, page_file: Path, label: str) -> None:
        """
        Step 3 (static) — .auth-card must have border: '1.5px solid var(--accent-login-border)'.
        """
        source = _read_source(page_file)
        _assert_auth_card_border(source, label)

    @pytest.mark.parametrize("page_file,label", [
        (_LOGIN_PAGE, "login/page.tsx"),
        (_REGISTER_PAGE, "register/page.tsx"),
    ])
    def test_auth_card_has_box_shadow_main(self, page_file: Path, label: str) -> None:
        """
        Step 3 (static) — .auth-card must have boxShadow: 'var(--shadow-main)'.
        """
        source = _read_source(page_file)
        _assert_auth_card_box_shadow(source, label)

    @pytest.mark.parametrize("page_file,label", [
        (_LOGIN_PAGE, "login/page.tsx"),
        (_REGISTER_PAGE, "register/page.tsx"),
    ])
    def test_auth_card_has_max_width_400(self, page_file: Path, label: str) -> None:
        """
        Step 3 (static) — .auth-card must have maxWidth: 400 (renders as 400px).
        """
        source = _read_source(page_file)
        _assert_auth_card_max_width(source, label)

    def test_globals_css_defines_bg_page(self) -> None:
        """
        Step 2 (static) — globals.css :root block must define --bg-page.
        """
        source = _read_source(_GLOBALS_CSS)
        root_match = re.search(r":root\s*\{([^}]*)\}", source, re.DOTALL)
        assert root_match, "globals.css :root block not found"
        root_block = root_match.group(1)
        assert "--bg-page" in root_block, (
            "globals.css :root block must define --bg-page token. "
            "The page background depends on this CSS variable."
        )

    def test_globals_css_defines_bg_login(self) -> None:
        """
        Step 3 (static) — globals.css :root block must define --bg-login.
        """
        source = _read_source(_GLOBALS_CSS)
        root_match = re.search(r":root\s*\{([^}]*)\}", source, re.DOTALL)
        assert root_match, "globals.css :root block not found"
        root_block = root_match.group(1)
        assert "--bg-login" in root_block, (
            "globals.css :root block must define --bg-login token. "
            "The auth card background depends on this CSS variable."
        )

    def test_globals_css_defines_accent_login_border(self) -> None:
        """
        Step 3 (static) — globals.css :root block must define --accent-login-border.
        """
        source = _read_source(_GLOBALS_CSS)
        root_match = re.search(r":root\s*\{([^}]*)\}", source, re.DOTALL)
        assert root_match, "globals.css :root block not found"
        root_block = root_match.group(1)
        assert "--accent-login-border" in root_block, (
            "globals.css :root block must define --accent-login-border token."
        )

    def test_globals_css_defines_shadow_main(self) -> None:
        """
        Step 3 (static) — globals.css :root block must define --shadow-main.
        """
        source = _read_source(_GLOBALS_CSS)
        root_match = re.search(r":root\s*\{([^}]*)\}", source, re.DOTALL)
        assert root_match, "globals.css :root block not found"
        root_block = root_match.group(1)
        assert "--shadow-main" in root_block, (
            "globals.css :root block must define --shadow-main token."
        )


# ---------------------------------------------------------------------------
# Live Playwright tests (only run when APP_URL / WEB_BASE_URL is set)
# ---------------------------------------------------------------------------


class TestAuthCardLive:
    """MYTUBE-457 (Live): Verify auth-card computed styles in the deployed app."""

    def test_login_page_container_min_height(self, live_pages) -> None:
        """
        Step 2 (live) — /login outer container must have min-height: 100vh.
        """
        login_page, _ = live_pages
        config = WebConfig()
        styles = _get_page_container_styles(login_page, config.login_url())
        assert styles.get("minHeight") == "100vh", (
            f"/login page container minHeight is '{styles.get('minHeight')}', expected '100vh'. "
            f"The Tailwind class 'min-h-screen' must be present on the outer container."
        )

    def test_login_page_container_is_flex_centered(self, live_pages) -> None:
        """
        Step 2 (live) — /login outer container must use flexbox centering.
        """
        login_page, _ = live_pages
        styles = login_page.evaluate("""() => {
            const card = document.querySelector('.auth-card');
            const container = card ? card.parentElement : null;
            if (!container) return {};
            const cs = window.getComputedStyle(container);
            return { display: cs.display, alignItems: cs.alignItems, justifyContent: cs.justifyContent };
        }""")
        assert styles.get("display") == "flex", (
            f"/login container display is '{styles.get('display')}', expected 'flex'."
        )
        assert styles.get("alignItems") == "center", (
            f"/login container alignItems is '{styles.get('alignItems')}', expected 'center'."
        )
        assert styles.get("justifyContent") == "center", (
            f"/login container justifyContent is '{styles.get('justifyContent')}', expected 'center'."
        )

    def test_login_auth_card_border_radius(self, live_pages) -> None:
        """
        Step 3 (live) — /login .auth-card computed border-radius must be 24px.
        """
        login_page, _ = live_pages
        styles = _get_auth_card_styles(login_page)
        assert styles.get("borderRadius") == "24px", (
            f"/login .auth-card borderRadius is '{styles.get('borderRadius')}', expected '24px'."
        )

    def test_login_auth_card_max_width(self, live_pages) -> None:
        """
        Step 3 (live) — /login .auth-card inline maxWidth must be 400px.
        """
        login_page, _ = live_pages
        styles = _get_auth_card_styles(login_page)
        assert styles.get("maxWidth") == "400px", (
            f"/login .auth-card maxWidth is '{styles.get('maxWidth')}', expected '400px'."
        )

    def test_register_page_container_min_height(self, live_pages) -> None:
        """
        Step 2 (live) — /register outer container must have min-height: 100vh.
        """
        _, register_page = live_pages
        config = WebConfig()
        styles = _get_page_container_styles(register_page, config.register_url())
        assert styles.get("minHeight") == "100vh", (
            f"/register page container minHeight is '{styles.get('minHeight')}', expected '100vh'."
        )

    def test_register_auth_card_border_radius(self, live_pages) -> None:
        """
        Step 3 (live) — /register .auth-card computed border-radius must be 24px.
        """
        _, register_page = live_pages
        styles = _get_auth_card_styles(register_page)
        assert styles.get("borderRadius") == "24px", (
            f"/register .auth-card borderRadius is '{styles.get('borderRadius')}', expected '24px'."
        )

    def test_register_auth_card_max_width(self, live_pages) -> None:
        """
        Step 3 (live) — /register .auth-card inline maxWidth must be 400px.
        """
        _, register_page = live_pages
        styles = _get_auth_card_styles(register_page)
        assert styles.get("maxWidth") == "400px", (
            f"/register .auth-card maxWidth is '{styles.get('maxWidth')}', expected '400px'."
        )
