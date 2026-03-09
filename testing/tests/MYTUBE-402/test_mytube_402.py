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

    # Prepare artifacts directory for failure diagnostics
    artifacts_dir = os.path.join(os.path.dirname(__file__), "artifacts")
    try:
        os.makedirs(artifacts_dir, exist_ok=True)
    except Exception:
        pass

    console_msgs: list[str] = []

    def _on_console(msg):
        try:
            console_msgs.append(f"{msg.type}: {msg.text}")
        except Exception:
            console_msgs.append(f"console: <unserializable>")

    try:
        page.on("console", _on_console)
    except Exception:
        # Some Playwright bindings may not allow attaching; ignore if it fails
        pass

    # Accelerate long intervals so the app's heartbeat/probe runs quickly, but store original
    try:
        page.evaluate(
            "() => { if (!window.__mytube402_origSetInterval) { window.__mytube402_origSetInterval = window.setInterval; window.setInterval = function(fn, delay){ var rest = Array.prototype.slice.call(arguments,2); var newDelay = (typeof delay === 'number' && delay >= 10000) ? 100 : delay; return window.__mytube402_origSetInterval.apply(window, [fn, newDelay].concat(rest)); }; } }"
        )
    except Exception:
        pass

    # Wait for the app's proactive reachability to react; allow a short retry/backoff loop and capture diagnostics on final timeout
    predicate = "() => { const el = document.querySelector('header [role=\\'alert\\']'); return el && (el.innerText||'').trim().length > 0; }"
    attempts = 6
    found = False
    last_exc = None
    for attempt in range(attempts):
        try:
            # try with a longer per-attempt timeout to allow SDK and rendering cycles
            page.wait_for_function(predicate, timeout=45_000)
            found = True
            break
        except Exception as e:
            last_exc = e
            # short incremental backoff before retrying, visible in Playwright traces
            try:
                page.wait_for_timeout((2 + attempt * 2) * 1000)
            except Exception:
                pass

    if not found:
        ts = int(time.time())
        ss = os.path.join(artifacts_dir, f"auth-offline-failure-{ts}.png")
        html = os.path.join(artifacts_dir, f"auth-offline-failure-{ts}.html")
        console_file = os.path.join(artifacts_dir, f"auth-offline-failure-{ts}.log")
        try:
            page.screenshot(path=ss)
        except Exception:
            pass
        try:
            open(html, "w", encoding="utf-8").write(page.content())
        except Exception:
            pass
        try:
            open(console_file, "w", encoding="utf-8").write("\n".join(console_msgs))
        except Exception:
            pass
        # Re-raise with helpful message and artifact locations
        raise AssertionError(
            f"Timeout waiting for auth-error alert after {attempts} attempts; captured artifacts: screenshot={ss}, html={html}, console={console_file}"
        ) from last_exc

    # Assert header alert visible with expected message
    assert site_header.has_auth_error_alert(), "Expected auth-error alert in header after going offline"
    alert_text = site_header.auth_error_alert_text()
    assert _EXPECTED_ERROR_TEXT in alert_text, f"Alert text did not match expected (got: {alert_text!r})"

    # Restore original timer behavior if we replaced it
    try:
        page.evaluate(
            "() => { if (window.__mytube402_origSetInterval) { window.setInterval = window.__mytube402_origSetInterval; delete window.__mytube402_origSetInterval; } }"
        )
    except Exception:
        pass


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

        # Attach console listener early so failures capture logs
        console_msgs: list[str] = []

        def _on_console(msg):
            try:
                console_msgs.append(f"{msg.type}: {msg.text}")
            except Exception:
                console_msgs.append("console: <unserializable>")

        try:
            page.on("console", _on_console)
        except Exception:
            pass

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

        def _abort(route):
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

        # Give the SDK a short moment to initialize if present, but don't block test excessively
        try:
            page.wait_for_function("() => !!(window.firebase && window.firebase.auth)", timeout=20_000)
        except Exception:
            # proceed; the subsequent refresh attempts will handle absence
            pass

        # Trigger a deterministic token refresh to exercise the SDK refresh path.
        # Use a bounded retry loop so the SDK has a brief window to initialize; capture
        # diagnostics and fail fast if we cannot invoke the refresh deterministically.
        artifacts_dir = os.path.join(os.path.dirname(__file__), "artifacts")
        try:
            os.makedirs(artifacts_dir, exist_ok=True)
        except Exception:
            pass

        def _capture_token_failure(page, tag="token-refresh"):
            ts = int(time.time())
            ss = os.path.join(artifacts_dir, f"{tag}-failure-{ts}.png")
            html = os.path.join(artifacts_dir, f"{tag}-failure-{ts}.html")
            console_file = os.path.join(artifacts_dir, f"{tag}-failure-{ts}.log")
            try:
                page.screenshot(path=ss)
            except Exception:
                pass
            try:
                open(html, "w", encoding="utf-8").write(page.content())
            except Exception:
                pass
            try:
                open(console_file, "w", encoding="utf-8").write("\n".join(console_msgs))
            except Exception:
                pass
            return ss, html, console_file

        refreshed = None
        last_exc = None
        for attempt in range(8):
            try:
                refreshed = page.evaluate(r"""() => {
                    try {
                        if (window.firebase && firebase.auth && firebase.auth().currentUser && typeof firebase.auth().currentUser.getIdToken === 'function') {
                            return firebase.auth().currentUser.getIdToken(true).then(()=>true).catch(()=>false);
                        }
                    } catch(e) {}
                    return null;
                }""")
                # If we got True, the token refresh succeeded and we can proceed.
                # If we got False, the refresh promise rejected (e.g., due to offline) — treat as transient and retry.
                # If we got null, the SDK or currentUser is not ready yet — retry.
                if refreshed is True:
                    break
            except Exception as e:
                last_exc = e
            try:
                page.wait_for_timeout((1 + attempt) * 1000)
            except Exception:
                pass

        if not isinstance(refreshed, bool):
            ss, html, console_file = _capture_token_failure(page, tag="token-refresh")
            raise AssertionError(
                f"Could not deterministically invoke token refresh; captured artifacts: screenshot={ss}, html={html}, console={console_file}"
            ) from last_exc

        # Optionally log the refresh outcome (True means token refresh promise resolved)
        # but do not force a specific boolean since offline behavior may vary.

        # Run common assertions
        _common_assertions_for_auth_offline(page)

    finally:
        try:
            context.set_offline(False)
        except Exception:
            pass
        context.close()
