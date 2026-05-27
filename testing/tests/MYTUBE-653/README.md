# MYTUBE-653: SiteHeader avatar refresh — reverts to placeholder after deletion

## What this test verifies

Automates the scenario: after a user removes their profile picture on the Account
Settings page, the SiteHeader avatar immediately reverts to the default gradient
placeholder (user's initial letter) **without a page reload**.

## Dependencies

```
pytest>=8.4.2
playwright>=1.58.0
```

Install playwright browsers once:
```bash
playwright install chromium
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `FIREBASE_TEST_EMAIL` | Yes | Email for the CI test Firebase account |
| `FIREBASE_TEST_PASSWORD` | Yes | Password for the CI test Firebase account |
| `APP_URL` / `WEB_BASE_URL` | No | Base URL (default: `https://ai-teammate.github.io/mytube`) |
| `PLAYWRIGHT_HEADLESS` | No | `true` (default) or `false` for visible browser |

## How to run

From the repository root:

```bash
pytest testing/tests/MYTUBE-653/test_mytube_653.py -v
```

## Route mocking

The test uses Playwright route interception to avoid real network calls:
- `GET /api/me` → returns a profile JSON with a pre-set avatar URL
- `DELETE /api/me/avatar` → returns HTTP 200 (successful removal)
- Avatar CDN URL → serves a valid 1×1 GIF (prevents `onError` fallback)

## Expected output (passing)

```
PASSED testing/tests/MYTUBE-653/test_mytube_653.py::TestSiteHeaderAvatarRevertsAfterDeletion::test_initial_avatar_url_field_shows_existing_url
PASSED testing/tests/MYTUBE-653/test_mytube_653.py::TestSiteHeaderAvatarRevertsAfterDeletion::test_site_header_shows_avatar_image_before_removal
PASSED testing/tests/MYTUBE-653/test_mytube_653.py::TestSiteHeaderAvatarRevertsAfterDeletion::test_remove_avatar_button_is_visible
PASSED testing/tests/MYTUBE-653/test_mytube_653.py::TestSiteHeaderAvatarRevertsAfterDeletion::test_click_remove_avatar_and_site_header_reverts_to_placeholder
PASSED testing/tests/MYTUBE-653/test_mytube_653.py::TestSiteHeaderAvatarRevertsAfterDeletion::test_site_header_no_avatar_image_after_removal
PASSED testing/tests/MYTUBE-653/test_mytube_653.py::TestSiteHeaderAvatarRevertsAfterDeletion::test_avatar_url_field_cleared_after_removal
```
