# MYTUBE-647 — Re-upload avatar with same file extension: unique URL generated and image visually updates

## Objective

Verify that re-uploading an avatar using the same file extension (e.g., PNG → PNG) generates
a new, unique URL containing a version component (timestamp or UUID) to bypass browser/CDN
caching, and that the avatar preview image visually updates immediately without a page reload.

Related bug: **MYTUBE-642** — Avatar still shows old image after re-upload due to cached GCS URL.
Fix: GCS object key now includes a UUID/timestamp component (`avatars/{uid}/{version}.{ext}`),
making every upload URL unique.

## Test Type

`web` — Playwright (Chromium headless) end-to-end UI test.

## Test Structure

Five ordered tests run in a single shared module-scoped browser session:

1. **test_existing_avatar_url_is_shown_on_load** — Settings page loads with the pre-existing
   PNG avatar URL in the Avatar URL field (precondition verification).
2. **test_existing_avatar_preview_is_visible** — Avatar preview container is visible before
   the re-upload action.
3. **test_reupload_same_extension_returns_new_unique_url** — Selecting a PNG file and clicking
   Upload returns a URL that differs from the original (core cache-bust assertion).
4. **test_new_url_contains_version_component** — The new avatar URL path matches the
   `avatars/{uid}/{version}.{ext}` pattern required by the MYTUBE-642 fix.
5. **test_avatar_preview_updates_to_new_url_after_reupload** — The `<img>` src inside
   `AvatarPreview` updates to the new URL without a page reload.

### Route Interception

- `GET /api/me` → returns a profile JSON with the pre-existing PNG avatar URL.
- `POST /api/me/avatar` → returns HTTP 200 with a new versioned avatar URL.
- CDN avatar image requests → served with a valid 1×1 GIF to prevent `onError`.

## Prerequisites

- Python 3.10+
- `pytest`
- `playwright` Python package with Chromium browser installed

## Environment Variables

| Variable                | Required | Description                                              |
|-------------------------|----------|----------------------------------------------------------|
| `FIREBASE_TEST_EMAIL`   | Yes      | Test user email. Module is skipped when absent.          |
| `FIREBASE_TEST_PASSWORD`| Yes      | Test user password. Module is skipped when absent.       |
| `APP_URL` / `WEB_BASE_URL` | No    | Base URL of the deployed web app (default: `https://ai-teammate.github.io/mytube`). |
| `PLAYWRIGHT_HEADLESS`   | No       | Run browser headless (default: `true`).                  |
| `PLAYWRIGHT_SLOW_MO`    | No       | Slow-motion delay in ms (default: `0`).                  |

## Running the Tests

```bash
# From the repository root:
FIREBASE_TEST_EMAIL=user@example.com \
FIREBASE_TEST_PASSWORD=secret \
pytest testing/tests/MYTUBE-647/test_mytube_647.py -v
```

## Expected Output

```
PASSED  TestAvatarReUploadUniqueUrl::test_existing_avatar_url_is_shown_on_load
PASSED  TestAvatarReUploadUniqueUrl::test_existing_avatar_preview_is_visible
PASSED  TestAvatarReUploadUniqueUrl::test_reupload_same_extension_returns_new_unique_url
PASSED  TestAvatarReUploadUniqueUrl::test_new_url_contains_version_component
PASSED  TestAvatarReUploadUniqueUrl::test_avatar_preview_updates_to_new_url_after_reupload
```
