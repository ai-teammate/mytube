# MYTUBE-611: Enter broken avatar URL — fallback placeholder is displayed

## Objective

Verify that a fallback placeholder is shown when the provided avatar URL fails
to load due to a broken link or CORS block. When the `<img>` element fires
`onError`, the `AvatarPreview` component must replace it with a grey circular
SVG person-icon placeholder so the layout does not break.

## Test Steps

1. Log in with Firebase test credentials.
2. Navigate to `/settings/`.
3. Enter an invalid/unreachable image URL (e.g. `https://invalid-domain-that-does-not-exist.example.com/missing.jpg`) into the "Avatar URL" field.
4. Wait for the React `onError` handler to fire and switch to the SVG fallback.
5. Assert all four placeholder conditions.

## Expected Result

- `div[role="img"][aria-label="Avatar preview"]` container is visible.
- `<img>` element is absent from the DOM (removed after `onError`).
- SVG person-icon placeholder is visible inside the container.
- Container has the `bg-gray-200` Tailwind class.

## Architecture

- `SettingsPage` from `testing/components/pages/settings_page/` encapsulates all DOM interactions.
- `LoginPage` from `testing/components/pages/login_page/` handles authentication.
- `WebConfig` from `testing/core/config/web_config.py` centralises env var access.
- Playwright sync API via `pytest` module-scoped fixtures (login once, run all 4 tests).

## Prerequisites

- Python 3.9+
- `playwright` and `pytest-playwright` installed (`pip install -r testing/requirements.txt`)
- Playwright browsers installed (`playwright install chromium`)

## Environment Variables

| Variable | Description |
|---|---|
| `FIREBASE_TEST_EMAIL` | Email of the Firebase test account |
| `FIREBASE_TEST_PASSWORD` | Password of the Firebase test account |
| `APP_URL` | Base URL of the deployed app (default: `https://ai-teammate.github.io/mytube`) |

The test module is skipped automatically when `FIREBASE_TEST_EMAIL` or
`FIREBASE_TEST_PASSWORD` is not set.

## Run

```bash
pytest testing/tests/MYTUBE-611/test_mytube_611.py -v
```

## Expected Output

```
PASSED testing/tests/MYTUBE-611/test_mytube_611.py::TestAvatarFallbackOnBrokenUrl::test_avatar_preview_container_is_visible
PASSED testing/tests/MYTUBE-611/test_mytube_611.py::TestAvatarFallbackOnBrokenUrl::test_img_element_is_absent_after_error
PASSED testing/tests/MYTUBE-611/test_mytube_611.py::TestAvatarFallbackOnBrokenUrl::test_svg_placeholder_is_visible
PASSED testing/tests/MYTUBE-611/test_mytube_611.py::TestAvatarFallbackOnBrokenUrl::test_avatar_preview_has_grey_background
4 passed
```

## Skip Behaviour

The entire module is skipped (not failed) when Firebase credentials are absent,
allowing CI pipelines without live credentials to pass cleanly.
