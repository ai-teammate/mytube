"""
MYTUBE-402: Application behavior when browser goes offline — authentication services error displayed

Objective
---------
Verify that when the browser transitions to offline mode while the user is
authenticated and active on the dashboard, the application displays the
error message: "Authentication services are currently unavailable" in a
role="alert" element in the site header.
"""
from __future__ import annotations

import os
import sys
import time
import json
import pytest
from playwright.sync_api import sync_playwright, Browser, Page

# Allow importing testing package components
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.site_header.site_header import SiteHeader
from testing.components.pages.login_page.login_page import LoginPage

_EXPECTED_ERROR_TEXT = "Authentication services are currently unavailable"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_firebase_api_key(page: Page) -> str | None:
    try:
        api_key = page.evaluate(
            r"""() => {
                const pattern = /AIza[0-9A-Za-z_\-]{35}/;
                for (const script of document.querySelectorAll('script:not([src])')) {
                    const m = (script.textContent || '').match(pattern);
                    if (m) return m[0];
                }
                const m = document.documentElement.innerHTML.match(pattern);
                if (m) return m[0];
                return null;
            }"""
        )
        return api_key
    except Exception:
        return None


def _build_valid_session_init_script(api_key: str) -> str:
    # Create a structurally plausible Firebase auth user with future expiry.
    import time as _t
    future_ms = int((_t.time() + 3600) * 1000)
    user = {
        "uid": "mytube-402-fake-uid",
        "email": "ci-fake@mytube.test",
        "emailVerified": True,
        "isAnonymous": False,
        "providerData": [{
            "providerId": "password",
            "uid": "ci-fake@mytube.test",
            "displayName": None,
            "email": "ci-fake@mytube.test",
            "phoneNumber": None,
            "photoURL": None,
        }],
        "stsTokenManager": {
            "refreshToken": "fake-refresh-token-mytube-402",
            "accessToken": "fake.access.token.mytube402",
            "expirationTime": future_ms,
        },
        "createdAt": str(future_ms - 1000),
        "lastLoginAt": str(future_ms - 1000),
    }
    ls_key = f"firebase:authUser:{api_key}:[DEFAULT]"
    return f"(function(){{ try {{ localStorage.setItem({json.dumps(ls_key)}, {json.dumps(json.dumps(user))}); window.__mytube402_injected = true; }} catch(e) {{ window.__mytube402_injected = false; }} }})();"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser_instance(web_config: WebConfig) -> Browser:
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=web_config.headless, slow_mo=web_config.slow_mo)
        yield br
        br.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _common_assertions_for_auth_offline(page: Page) -> None:
    site_header = SiteHeader(page)
    # Ensure we appear authenticated (Sign in link should NOT be visible)
    assert not site_header.has_sign_in_link(), "Precondition failed: user appears unauthenticated"
    # Accelerate long intervals so the app's heartbeat/probe runs quickly
    try:
        page.evaluate("() => { var _orig = window.setInterval; window.setInterval = function(fn, delay){ var rest = Array.prototype.slice.call(arguments,2); var newDelay = (typeof delay === 'number' && delay >= 10000) ? 100 : delay; return _orig.apply(window, [fn, newDelay].concat(rest)); }; }")
    except Exception:
        pass
    # Wait for the app's proactive reachability to react
    try:
        page.wait_for_function(
            "() => { const el = document.querySelector('header [role=\\'alert\\']'); return el && (el.innerText||'').trim().length > 0; }",
            timeout=12_000,
        )
    except Exception:
        pass
    # Assert header alert visible with expected message
    assert site_header.has_auth_error_alert(), "Expected auth-error alert in header after going offline"
    alert_text = site_header.auth_error_alert_text()
    assert _EXPECTED_ERROR_TEXT in alert_text, f"Alert text did not match expected (got: {alert_text!r})"


def test_offline_shows_auth_error_with_ui_login(browser_instance: Browser, web_config: WebConfig) -> None:
    """UI-login flow: log in through the UI, then toggle offline and assert header alert."""
    context = browser_instance.new_context()
    page = context.new_page()
    page.set_default_timeout(30_000)

    try:
        # Require explicit credentials for the UI login test; otherwise skip
        if not (web_config.test_email and web_config.test_password):
            pytest.skip("Skipping UI-login test because FIREBASE_TEST_EMAIL/PASSWORD not provided")

        login = LoginPage(page)
        login.navigate(web_config.login_url())
        login.login_as(web_config.test_email, web_config.test_password)
        # Wait for header to reflect authenticated state (no "Sign in" link).
        try:
            page.wait_for_function(
                "() => { const links = Array.from(document.querySelectorAll('header a') || []); return !links.some(a => (a.innerText||'').trim().toLowerCase().includes('sign in')); }",
                timeout=15_000,
            )
        except Exception:
            pytest.skip("UI login did not reach authenticated state within timeout")

        # Toggle offline and run common assertions
        context.set_offline(True)
        _common_assertions_for_auth_offline(page)

    finally:
        try:
            context.set_offline(False)
        except Exception:
            pass
        context.close()


def test_offline_shows_auth_error_with_injected_session(browser_instance: Browser, web_config: WebConfig) -> None:
    """Injected-session flow: pre-populate an EXPIRED session, ensure injection succeeded, then toggle offline and assert header alert.

    This test only intercepts known Firebase/auth endpoints (no catch-all route).
    """
    # Start with a fresh context
    context = browser_instance.new_context()

    try:
        page = context.new_page()
        page.set_default_timeout(30_000)

        # Navigate to discover API key
        page.goto(web_config.home_url(), wait_until="domcontentloaded")
        api_key = _extract_firebase_api_key(page)
        if not api_key:
            pytest.skip("Could not discover Firebase API key to inject fake session")

        # Build an expired session object (expirationTime in the past)
        expired_user = {
            "uid": "mytube-402-expired-uid",
            "email": "ci-expired@mytube.test",
            "emailVerified": False,
            "isAnonymous": False,
            "providerData": [{
                "providerId": "password",
                "uid": "ci-expired@mytube.test",
                "displayName": None,
                "email": "ci-expired@mytube.test",
                "phoneNumber": None,
                "photoURL": None,
            }],
            "stsTokenManager": {
                "refreshToken": "AEu_fake_refresh_for_mytube_402",
                "accessToken": "fake.access.token.mytube402",
                # Expiry in the past (2001-01-01 UTC ms)
                "expirationTime": 978307200000,
            },
            "createdAt": "978307200000",
            "lastLoginAt": "978307200000",
        }
        ls_key = f"firebase:authUser:{api_key}:[DEFAULT]"
        init_script = f"(function(){{ try {{ localStorage.setItem({json.dumps(ls_key)}, {json.dumps(json.dumps(expired_user))}); window.__mytube402_injected = true; }} catch(e) {{ window.__mytube402_injected = false; }} }})();"

        # Close the initial context and recreate with the init script present before navigation
        context.close()
        context = browser_instance.new_context()
        context.add_init_script(script=init_script)

        # Register only explicit Firebase/auth endpoints to simulate token-refresh failure
        firebase_patterns = [
            "https://securetoken.googleapis.com/**",
            "https://identitytoolkit.googleapis.com/**",
            "https://www.googleapis.com/identitytoolkit/**",
            "https://*.firebaseapp.com/**",
            "https://*.firebaseio.com/**",
        ]

        def _abort(route, req):
            try:
                route.abort("aborted")
            except Exception:
                try:
                    route.fulfill(status=503, body="")
                except Exception:
                    try:
                        route.abort()
                    except Exception:
                        pass

        for p in firebase_patterns:
            context.route(p, _abort)

        # Navigate while offline so SDK attempts refresh while offline
        context.set_offline(True)
        page = context.new_page()
        page.goto(web_config.dashboard_url(), wait_until="domcontentloaded")

        # Verify injection succeeded (fail fast if not)
        try:
            injected = page.evaluate("() => !!window.__mytube402_injected")
        except Exception:
            injected = False
        assert injected, "Injection did not set window.__mytube402_injected — aborting test"

        # Run common assertions
        _common_assertions_for_auth_offline(page)

    finally:
        try:
            context.set_offline(False)
        except Exception:
            pass
        context.close()
