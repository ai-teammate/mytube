# MYTUBE-648 — SiteHeader Avatar Refresh After Upload

## Ticket

**MYTUBE-648**: Verify that the avatar image in the global SiteHeader is updated immediately after a successful upload in the same session.

## Objective

Ensure that when a user uploads a new avatar from the Account Settings page the SiteHeader avatar button continues to reflect an authenticated state (gradient circle remains visible) and the AvatarPreview in the settings form is updated to the new image URL without a page reload.

## Preconditions

- User is authenticated and viewing the Account Settings page.
- The application is running and accessible at the URL configured in `NEXT_PUBLIC_BASE_URL`.
- Firebase test credentials are available via environment variables.

## Test Cases

| # | Test Method | What it checks |
|---|-------------|----------------|
| 1 | `test_initial_avatar_in_settings_shows_old_url` | Avatar URL field shows the existing URL before upload |
| 2 | `test_site_header_avatar_visible_before_upload` | SiteHeader avatar button is visible before upload |
| 3 | `test_avatar_preview_shows_old_image_before_upload` | AvatarPreview img src matches the old URL before upload |
| 4 | `test_upload_new_avatar_shows_success_message` | Upload flow shows success toast |
| 5 | `test_avatar_url_field_updated_to_new_unique_url` | Avatar URL field updated with new UUID-bearing URL (MYTUBE-642 regression) |
| 6 | `test_avatar_preview_updated_to_new_image_after_upload` | AvatarPreview img src updated to new URL without page reload |
| 7 | `test_site_header_avatar_still_visible_after_upload` | SiteHeader avatar button remains visible after upload |

## Related Bug

**MYTUBE-642** (Done): GCS object key changed from `avatars/{uid}.{ext}` to `avatars/{uid}/{uuid}.{ext}` to produce a unique, cache-busting URL on each upload.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `FIREBASE_TEST_EMAIL` | Email address of the test Firebase account |
| `FIREBASE_TEST_PASSWORD` | Password of the test Firebase account |

## How to Run

```bash
# From the repository root:
pytest testing/tests/MYTUBE-648/test_mytube_648.py -v
```

## Framework

- **Type**: Web UI
- **Framework**: Playwright (Chromium, headless)
- **Architecture**: Page Objects (`LoginPage`, `SettingsPage`, `SiteHeader`) with `WebConfig` injection
- **Route interception**: `GET /api/me` and `POST /api/me/avatar` are mocked; CDN image requests are served a 1×1 GIF to prevent `onError` fallback.
