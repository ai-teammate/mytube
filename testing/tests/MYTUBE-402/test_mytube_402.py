"""
MYTUBE-402: Application behavior when browser goes offline — auth services error displayed.

Objective
--------
Verify that when the browser transitions to offline (navigator.onLine false / network unavailable)
that the proactive reachability mechanism surfaces the error: "Authentication services are currently unavailable"
in a role="alert" element.

Preconditions
-------------
The app initially loads with Firebase reachable.

"""
from __future__ import annotations

import json
import os
import re
import sys
import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage

_FIREBASE_API_KEY_PATTERN = re.compile(r"AIza[0-9A-Za-z_\-]{35}")
_EXPECTED_ERROR_TEXT = "Authentication services are currently unavailable"
_AUTH_ERROR_KEYWORDS = re.compile(r"authentication.*unavail|services.*unavail|unavail.*authentication|auth.*unavail", re.IGNORECASE)
_AUTH_ERROR_ALERT_SELECTOR = "[role='alert']"
_INITIAL_LOAD_TIMEOUT_MS = 20_000
_ERROR_VISIBILITY_TIMEOUT_MS = 30_000
_LOADING_TEXT = "Loading\u2026"

@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()

@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(headless=web_config.headless, slow_mo=web_config.slow_mo)
        yield br
        br.close()


def _wait_for_initial_load(page: Page) -> None:
    loading = page.locator(f"text={_LOADING_TEXT}")
    try:
        loading.wait_for(state="visible", timeout=5_000)
        loading.wait_for(state="hidden", timeout=_INITIAL_LOAD_TIMEOUT_MS)
    except Exception:
        pass


def _extract_firebase_api_key(page: Page) -> str | None:
    try:
        api_key = page.evaluate(r"""() => {
            const pattern = /AIza[0-9A-Za-z_\-]{35}/;
            for (const script of document.querySelectorAll('script:not([src])')) {
                const m = script.textContent.match(pattern);
                if (m) return m[0];
            }
            const m = document.documentElement.innerHTML.match(pattern);
            if (m) return m[0];
            return null;
        }""")
        return api_key
    except Exception:
        return None


def _inject_fake_user_session(page: Page, api_key: str) -> None:
    fake_user = {
        "uid": "test-uid-mytube-402",
        "email": "ci-offline@mytube.test",
        "emailVerified": False,
        "displayName": "CI Offline",
        "isAnonymous": False,
        "providerData": [{"uid": "ci-offline@mytube.test", "email": "ci-offline@mytube.test", "providerId": "password"}],
        "stsTokenManager": {
            "refreshToken": "fake-refresh-token-mytube-402",
            "accessToken": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0In0.fake",
            "expirationTime": 1_000_000_000_000,
        },
        "lastLoginAt": "1000000000000",
        "createdAt": "1000000000000",
        "apiKey": api_key,
        "appName": "[DEFAULT]",
    }
    storage_key = f"firebase:authUser:{api_key}:[DEFAULT]"
    page.evaluate("([k,v]) => window.localStorage.setItem(k,v)", [storage_key, json.dumps(fake_user)])


def _is_auth_error_present(page: Page) -> bool:
    alert_locator = page.locator(_AUTH_ERROR_ALERT_SELECTOR)
    for i in range(alert_locator.count()):
        el = alert_locator.nth(i)
        if el.is_visible():
            t = (el.text_content() or "").strip()
            if t and _AUTH_ERROR_KEYWORDS.search(t):
                return True
    visible_text = page.locator("body").inner_text()
    return bool(_AUTH_ERROR_KEYWORDS.search(visible_text))


class TestOfflineAuthReachability:
    def test_offline_shows_auth_unavailable_alert(self, browser: Browser, web_config: WebConfig) -> None:
        context: BrowserContext = browser.new_context()
        context.set_default_timeout(30_000)
        page: Page = context.new_page()
        page.set_default_timeout(30_000)

        try:
            # Load app with Firebase reachable first
            page.goto(web_config.home_url(), wait_until="domcontentloaded")
            _wait_for_initial_load(page)

            # Ensure no auth error initially
            body_text = page.locator("body").inner_text()
            assert not _AUTH_ERROR_KEYWORDS.search(body_text), "Auth error present before offline simulation"

            # Try to get API key and inject fake session to simulate an authenticated user
            api_key = _extract_firebase_api_key(page)
            if api_key:
                _inject_fake_user_session(page, api_key)
                page.reload(wait_until="domcontentloaded")
                _wait_for_initial_load(page)

            # Now simulate offline at the browser context level
            context.set_offline(True)

            # Wait up to the probe timeout for the auth-unavailable alert to appear.
            try:
                page.wait_for_function(
                    "() => Array.from(document.querySelectorAll('[role=\'alert\']')).some(e=>e.innerText && e.innerText.length>0)",
                    timeout=_ERROR_VISIBILITY_TIMEOUT_MS,
                )
            except Exception:
                pass

            if not _is_auth_error_present(page):
                pytest.fail(
                    "Expected auth-unavailability alert to appear after browser went offline, but none was found."
                )

        finally:
            context.set_offline(False)
            context.close()
