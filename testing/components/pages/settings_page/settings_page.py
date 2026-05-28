"""SettingsPage — Page Object for the /settings page of the MyTube web application.

Encapsulates all interactions with the Account Settings form, including the
AvatarPreview component, exposing only high-level actions and state queries.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — the caller provides the settings URL.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from __future__ import annotations

from playwright.sync_api import Page


class SettingsPage:
    """Page Object for the MyTube Account Settings page (/settings)."""

    # Selectors
    _AVATAR_URL_INPUT = 'input[id="avatar_url"]'
    _USERNAME_INPUT = 'input[id="username"]'
    _SAVE_BUTTON = 'button[type="submit"]'
    _LOADING_TEXT = "Loading\u2026"
    _AVATAR_FILE_INPUT = 'input[id="avatar_file"]'
    _UPLOAD_ERROR_ALERT = 'input[id="avatar_file"] ~ p[role="alert"]'

    # AvatarPreview selectors
    _AVATAR_PREVIEW_CONTAINER = '[role="img"][aria-label="Avatar preview"]'
    _AVATAR_PREVIEW_IMG = '[role="img"][aria-label="Avatar preview"] img'
    _AVATAR_PREVIEW_WRAPPER = '[role="img"][aria-label="Avatar preview"]'
    _AVATAR_PREVIEW_SVG = '[role="img"][aria-label="Avatar preview"] svg'

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, settings_url: str) -> None:
        """Navigate to the settings URL and wait for the form to be ready."""
        self._page.goto(settings_url, wait_until="domcontentloaded")
        # Wait for RequireAuth to pass through (loading spinner gone)
        try:
            self._page.wait_for_selector(
                f"text={self._LOADING_TEXT}", state="hidden", timeout=20_000
            )
        except Exception:
            pass
        # Wait for avatar URL input to appear (confirms settings form is rendered)
        self._page.wait_for_selector(self._AVATAR_URL_INPUT, timeout=20_000)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def fill_avatar_url(self, url: str) -> None:
        """Clear the Avatar URL field and replace its content with *url*.

        Uses Playwright's locator.fill() which sets the value atomically and
        dispatches the input event that React's synthetic onChange system picks up.
        """
        self._page.locator(self._AVATAR_URL_INPUT).fill(url)

    def get_avatar_url_input_value(self) -> str:
        """Return the current value of the Avatar URL input field."""
        return self._page.input_value(self._AVATAR_URL_INPUT)

    def clear_avatar_url(self) -> None:
        """Clear the Avatar URL input field."""
        self._page.fill(self._AVATAR_URL_INPUT, "")

    # ------------------------------------------------------------------
    # State queries — avatar preview (MYTUBE-612 API)
    # ------------------------------------------------------------------

    def is_avatar_preview_container_visible(self, timeout: float = 5_000) -> bool:
        """Return True when the avatar preview container (role=img) is visible."""
        try:
            self._page.wait_for_selector(
                self._AVATAR_PREVIEW_CONTAINER, state="visible", timeout=timeout
            )
            return True
        except Exception:
            return False

    def get_avatar_preview_img_src_from_dom(self) -> str | None:
        """Return the src attribute of the avatar preview <img> read directly from the DOM.

        Does NOT wait — evaluates the current DOM state immediately.  Returns
        None when the element is absent (e.g. image load failed, SVG shown).
        """
        return self._page.evaluate(
            """() => {
                const img = document.querySelector(
                    '[role="img"][aria-label="Avatar preview"] img'
                );
                return img ? img.getAttribute('src') : null;
            }"""
        )

    def wait_for_avatar_img_src(self, expected_src: str, timeout: float = 8_000) -> str | None:
        """Wait until the avatar preview img src equals *expected_src*.

        Polls the DOM repeatedly (via wait_for_function) and returns the src
        value captured at the moment the condition is met.  Returns None when
        the timeout is exceeded without the condition becoming true.
        """
        try:
            handle = self._page.wait_for_function(
                """(expectedSrc) => {
                    const img = document.querySelector(
                        '[role="img"][aria-label="Avatar preview"] img'
                    );
                    if (!img) return null;
                    const src = img.getAttribute('src');
                    return src === expectedSrc ? src : null;
                }""",
                expected_src,
                timeout=timeout,
            )
            if handle:
                return handle.json_value()
        except Exception:
            pass
        # Fallback: read current state one more time.
        return self.get_avatar_preview_img_src_from_dom()

    # ------------------------------------------------------------------
    # State queries — avatar preview (extended API from main)
    # ------------------------------------------------------------------

    def is_avatar_img_present(self) -> bool:
        """Return True if the <img> element is present inside the AvatarPreview container."""
        return self._page.locator(self._AVATAR_PREVIEW_IMG).count() > 0

    def is_avatar_svg_placeholder_visible(self, timeout: float = 10_000) -> bool:
        """Return True if the SVG placeholder is visible inside the AvatarPreview container.

        The SVG is shown when the image URL is empty or fails to load.
        """
        locator = self._page.locator(self._AVATAR_PREVIEW_SVG)
        try:
            locator.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def wait_for_avatar_error_fallback(self, timeout: float = 15_000) -> None:
        """Wait until the AvatarPreview switches to the SVG fallback state.

        This happens when the browser fires onError on the <img> element,
        which sets React state error=true, removes the <img> and renders the SVG.
        """
        self._page.wait_for_selector(
            self._AVATAR_PREVIEW_SVG,
            state="visible",
            timeout=timeout,
        )

    def is_avatar_preview_container_has_bg_gray(self) -> bool:
        """Return True if the AvatarPreview container has the expected grey background."""
        container = self._page.locator(self._AVATAR_PREVIEW_CONTAINER).first
        classes: str = container.get_attribute("class") or ""
        return "bg-gray-200" in classes

    def is_settings_page_loaded(self, timeout: float = 20_000) -> bool:
        """Return True if the settings page title/heading is visible."""
        try:
            self._page.wait_for_selector(
                'h1:has-text("Account settings")',
                timeout=timeout,
            )
            return True
        except Exception:
            return False

    def get_avatar_wrapper_computed_border_radius(self) -> str:
        """Return the computed border-radius of the avatar preview wrapper."""
        return self._page.evaluate(
            """() => {
                const el = document.querySelector('[role="img"][aria-label="Avatar preview"]');
                if (!el) return '';
                return window.getComputedStyle(el).borderRadius;
            }"""
        )

    def get_avatar_img_object_fit(self) -> str:
        """Return the computed object-fit CSS property of the preview <img>."""
        return self._page.evaluate(
            """() => {
                const img = document.querySelector('[role="img"][aria-label="Avatar preview"] img');
                if (!img) return '';
                return window.getComputedStyle(img).objectFit;
            }"""
        )

    def get_avatar_url_value(self) -> str:
        """Return the current value of the Avatar URL input."""
        return self._page.input_value(self._AVATAR_URL_INPUT)

    def current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    # ------------------------------------------------------------------
    # Avatar file upload actions (MYTUBE-633 / MYTUBE-634 / MYTUBE-637)
    # ------------------------------------------------------------------

    _FILE_INPUT = 'input[id="avatar_file"]'
    _AVATAR_FILE_INPUT = 'input[id="avatar_file"]'
    _UPLOAD_BUTTON = 'button[type="button"]:has-text("Upload")'
    _UPLOAD_BUTTON_NAME = "Upload"
    _UPLOAD_ERROR_ALERT = 'p[role="alert"]'
    _UPLOAD_ERROR_PRIMARY = '[id="avatar_file"] ~ [role="alert"]'
    _UPLOAD_ERROR_FALLBACK = 'p[role="alert"]'
    _UPLOAD_SUCCESS_STATUS = 'p[role="status"]'

    def set_avatar_file(self, file_payload) -> None:
        """Set a file on the hidden avatar file input via Playwright's set_input_files.

        *file_payload* may be a file-path string (for MYTUBE-633/637 style tests) or a
        dict with keys ``name``, ``mimeType``, and ``buffer`` (bytes), as accepted
        by Playwright's ``set_input_files`` (for MYTUBE-635 style tests).
        """
        self._page.locator(self._AVATAR_FILE_INPUT).set_input_files(file_payload)
    def wait_for_upload_success_message(self, timeout: float = 10_000) -> bool:
        """Wait for and return True when the upload success status message is visible."""
        try:
            self._page.wait_for_selector(
                'p[role="status"]:has-text("Avatar uploaded successfully")',
                state="visible",
                timeout=timeout,
            )
            return True
        except Exception:
            return False

    def get_upload_error_message(self, timeout: float = 10_000) -> str | None:
        """Wait for and return the upload error message text, or None if not shown."""
        try:
            locator = self._page.locator(self._UPLOAD_ERROR_ALERT)
            locator.wait_for(state="visible", timeout=timeout)
            return locator.text_content()
        except Exception:
            return None

    def is_upload_error_visible(self, timeout: float = 10_000) -> bool:
        """Return True if the upload error alert paragraph is visible."""
        try:
            self._page.locator(self._UPLOAD_ERROR_ALERT).wait_for(
                state="visible", timeout=timeout
            )
            return True
        except Exception:
            return False

    def get_upload_error_text(self, timeout: float = 5_000) -> str:
        """Wait for the upload error alert to become visible and return its text.

        Tries the sibling-of-input selector first and falls back to any
        ``p[role="alert"]`` on the page.
        """
        locator = self._page.locator(self._UPLOAD_ERROR_PRIMARY).or_(
            self._page.locator(self._UPLOAD_ERROR_FALLBACK)
        )
        locator.first.wait_for(state="visible", timeout=timeout)
        return locator.first.inner_text()

    def is_upload_button_disabled(self) -> bool:
        """Return True if the Upload button currently has the disabled attribute."""
        return self._page.get_by_role(
            "button", name=self._UPLOAD_BUTTON_NAME, exact=True
        ).is_disabled()

    def is_upload_button_visible(self) -> bool:
        """Return True if the Upload button is present and visible."""
        return self._page.locator(self._UPLOAD_BUTTON).is_visible()

    def is_upload_button_enabled(self) -> bool:
        """Return True if the Upload button is enabled (not disabled)."""
        return self._page.locator(self._UPLOAD_BUTTON).is_enabled()

    def get_upload_error_element_count(self) -> int:
        """Return the number of upload error alert paragraphs present in the DOM."""
        return self._page.locator(self._UPLOAD_ERROR_ALERT).count()

    # ------------------------------------------------------------------
    # Avatar upload actions and state queries (MYTUBE-634 API)
    # ------------------------------------------------------------------

    _UPLOAD_BUTTON = 'button[type="button"]:has-text("Upload")'

    def select_avatar_file(self, path: str) -> None:
        """Attach a local file to the avatar file input."""
        self._page.locator(self._AVATAR_FILE_INPUT).set_input_files(path)

    def wait_for_upload_button_enabled(self, timeout: float = 5_000) -> None:
        """Wait until the Upload button is enabled (a file has been selected)."""
        self._page.wait_for_function(
            """() => {
                const btns = [...document.querySelectorAll('button[type="button"]')];
                const btn = btns.find(b => b.textContent.includes('Upload'));
                return btn && !btn.disabled;
            }""",
            timeout=timeout,
        )

    def click_upload_button(self) -> None:
        """Click the Upload button."""
        self._page.locator(self._UPLOAD_BUTTON).click()

    def wait_for_upload_in_flight(self, timeout: float = 5_000) -> None:
        """Wait until the upload button shows 'Uploading…' (in-flight state)."""
        self._page.wait_for_function(
            """() => {
                return Array.from(document.querySelectorAll('button[type="button"]'))
                    .some(b => b.textContent && b.textContent.includes('Uploading'));
            }""",
            timeout=timeout,
        )

    def is_uploading_text_visible(self) -> bool:
        """Return True if the upload button currently shows 'Uploading…'."""
        return bool(self._page.evaluate(
            """() => {
                return Array.from(document.querySelectorAll('button[type="button"]'))
                    .some(b => b.textContent && b.textContent.includes('Uploading'));
            }"""
        ))

    def get_upload_button_label(self) -> str:
        """Return the current text content of the upload button."""
        return self._page.locator(self._UPLOAD_BUTTON).text_content() or ""

    def wait_for_upload_button_idle(self, timeout: float = 15_000) -> None:
        """Wait until the upload button shows 'Upload' (upload has completed or not started)."""
        self._page.wait_for_function(
            r"""() => {
                const btns = [...document.querySelectorAll('button[type="button"]')];
                const btn = btns.find(b => /^Upload$/.test(b.textContent.trim()));
                return btn !== undefined;
            }""",
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Avatar upload — observer-based in-flight state capture (MYTUBE-634)
    #
    # Because Playwright's sync route handlers block the Python event loop,
    # wait_for_function / locator.wait_for cannot observe the brief
    # "Uploading…" window from Python.  A browser-side MutationObserver is
    # set up BEFORE the click and fires independently of Python's event loop,
    # recording whether the in-flight states were ever reached.
    # ------------------------------------------------------------------

    def arm_uploading_observer(self) -> None:
        """Arm a DOM MutationObserver that captures the 'Uploading…' button state.

        Resets the observation flags each time it is called.  Must be called
        before ``click_upload_button()`` for the results to be meaningful.
        """
        self._page.evaluate(
            """() => {
                window._uploadingTextObserved   = false;
                window._uploadingDisabledObserved = false;
                if (window._uploadingObserver) {
                    window._uploadingObserver.disconnect();
                }
                window._uploadingObserver = new MutationObserver(() => {
                    const btns = Array.from(
                        document.querySelectorAll('button[type="button"]')
                    );
                    const uploading = btns.find(
                        b => b.textContent && b.textContent.includes('Uploading')
                    );
                    if (uploading) {
                        window._uploadingTextObserved = true;
                        if (uploading.disabled) {
                            window._uploadingDisabledObserved = true;
                        }
                    }
                });
                window._uploadingObserver.observe(document.body, {
                    childList: true, subtree: true,
                    characterData: true, attributes: true
                });
            }"""
        )

    def was_uploading_text_observed(self) -> bool:
        """Return True if the observer captured 'Uploading…' button text since arm_uploading_observer()."""
        return bool(self._page.evaluate("() => window._uploadingTextObserved || false"))

    def was_upload_disabled_observed(self) -> bool:
        """Return True if the observer captured the button as both 'Uploading…' and disabled."""
        return bool(self._page.evaluate("() => window._uploadingDisabledObserved || false"))

    # ------------------------------------------------------------------
    # File upload actions and queries (MYTUBE-636)
    # ------------------------------------------------------------------

    _FILE_INPUT_SELECTOR = 'input[id="avatar_file"]'

    def simulate_large_avatar_file(
        self,
        size_bytes: int = 6 * 1024 * 1024,
        filename: str = "large_avatar.jpg",
    ) -> None:
        """Inject a synthetic File object with *size_bytes* into the avatar file input.

        Uses JavaScript to create a File with an overridden ``size`` property and
        dispatches a ``change`` event so React's ``onChange`` handler runs.  This
        avoids transferring a real multi-MB file over the CDP socket.

        Parameters
        ----------
        size_bytes:
            Apparent file size to report (default: 6 MB, which exceeds the 5 MB limit).
        filename:
            Filename reported to the browser (must end with .jpg or .png so the
            MIME-type guard passes the ``accept`` check; size guard runs first).
        """
        self._page.evaluate(
            """([selector, sizeBytes, filename]) => {
                const input = document.querySelector(selector);
                if (!input) throw new Error('avatar_file input not found');

                const file = new File(['x'], filename, { type: 'image/jpeg' });
                Object.defineProperty(file, 'size', {
                    value: sizeBytes,
                    writable: false,
                    configurable: true,
                });

                const dt = new DataTransfer();
                dt.items.add(file);
                Object.defineProperty(input, 'files', {
                    value: dt.files,
                    writable: false,
                    configurable: true,
                });

                input.dispatchEvent(new Event('change', { bubbles: true }));
            }""",
            [self._FILE_INPUT_SELECTOR, size_bytes, filename],
        )

    def wait_for_upload_error(self, timeout: float = 5_000) -> None:
        """Wait until the upload error alert paragraph is visible."""
        self._page.wait_for_selector(
            'p[role="alert"]',
            state="visible",
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Avatar removal actions (MYTUBE-653, MYTUBE-656)
    # ------------------------------------------------------------------

    _REMOVE_AVATAR_BUTTON = 'button[type="button"]:has-text("Remove avatar")'
    _REMOVING_TEXT = "Removing…"
    _REMOVE_ERROR_ALERT = 'p[role="alert"]'

    def is_remove_avatar_button_visible(self, timeout: float = 10_000) -> bool:
        """Return True if the 'Remove avatar' button is present and visible."""
        try:
            locator = self._page.locator(self._REMOVE_AVATAR_BUTTON)
            locator.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def click_remove_avatar(self) -> None:
        """Click the 'Remove avatar' button."""
        self._page.locator(self._REMOVE_AVATAR_BUTTON).click()

    def wait_for_avatar_removed(self, timeout: float = 15_000) -> None:
        """Wait until the avatar removal completes.

        Waits for the 'Remove avatar' button or the avatar URL input to
        indicate the removal has completed (avatar URL field cleared).
        """
        self._page.wait_for_function(
            """() => {
                const input = document.querySelector('input[id="avatar_url"]');
                if (input && input.value === '') return true;
                // Also accept: button is back to idle (not "Removing…")
                const btns = Array.from(document.querySelectorAll('button[type="button"]'));
                const removing = btns.some(b => b.textContent && b.textContent.includes('Removing'));
                return !removing;
            }""",
            timeout=timeout,
        )

    def wait_for_remove_error(self, timeout: float = 10_000) -> None:
        """Wait until the remove-avatar error alert paragraph is visible."""
        self._page.wait_for_selector(
            self._REMOVE_ERROR_ALERT,
            state="visible",
            timeout=timeout,
        )

    def get_remove_error_text(self, timeout: float = 10_000) -> str | None:
        """Wait for and return the remove-error alert text, or None if not shown."""
        try:
            locator = self._page.locator(self._REMOVE_ERROR_ALERT)
            locator.wait_for(state="visible", timeout=timeout)
            return locator.first.text_content()
        except Exception:
            return None

    def is_remove_error_visible(self, timeout: float = 5_000) -> bool:
        """Return True if the remove-error alert paragraph is visible."""
        try:
            self._page.locator(self._REMOVE_ERROR_ALERT).first.wait_for(
                state="visible", timeout=timeout
            )
            return True
        except Exception:
            return False

    def get_avatar_url_field_value(self) -> str:
        """Return the current value of the Avatar URL input field."""
        return self._page.input_value(self._AVATAR_URL_INPUT)
