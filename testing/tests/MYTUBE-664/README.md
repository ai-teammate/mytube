# MYTUBE-664 — Avatar visible on Home page for authenticated user

## Objective
Verify that the authenticated user's avatar is correctly displayed in the SiteHeader when the user is on the Home page (`/`).

## Test type
Web UI — Playwright (Chromium)

## Prerequisites
- `FIREBASE_TEST_EMAIL` — email for a test Firebase account
- `FIREBASE_TEST_PASSWORD` — password for the test Firebase account
- `APP_URL` or `WEB_BASE_URL` — deployed app URL (default: `https://ai-teammate.github.io/mytube`)

## Install dependencies
```bash
pip install -r testing/requirements.txt
playwright install chromium
```

## Run the test
```bash
pytest testing/tests/MYTUBE-664/test_mytube_664.py -v
```

## Expected output (passing)
```
PASSED testing/tests/MYTUBE-664/test_mytube_664.py::TestAvatarVisibleOnHomePage::test_avatar_image_visible_on_home_page
```

## Notes
- The test mocks `GET /api/me` to return a user profile with a valid `avatar_url`, so no real avatar image is required in the database.
- Avatar CDN requests are intercepted and served with a valid 1×1 GIF so the `<img>` element renders without an `onError`.
- The fix for MYTUBE-663 ensures that the `avatarUrl` is correctly propagated from `AuthContext` to `SiteHeader` on the Home page route.
