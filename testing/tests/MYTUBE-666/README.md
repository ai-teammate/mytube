# MYTUBE-666 — Default Avatar Placeholder on Home Page

## Objective

Verify that the default avatar placeholder (gradient background with the user's
initial) is correctly displayed on the Home page for authenticated users who have
not uploaded a custom avatar image.  This is a regression check for the
MYTUBE-663 bug fix ("Avatar is not applied on the home page").

## Preconditions

- The user is authenticated via Firebase test credentials.
- The user has **no** custom avatar (`avatar_url` is empty).  
  The test mocks `GET /api/me` to return `{"username": "testuser666", "avatar_url": ""}`.

## Steps

1. Navigate to the Home page of the deployed web application.
2. Inspect the user avatar area in the `SiteHeader` (top-right account button).

## Expected Result

- The avatar placeholder `span` (`header button span.rounded-full`) is visible.
- No `<img>` avatar element is present inside the account button.
- The placeholder span contains a single initial letter (first character of the
  email / display name).
- The placeholder has a gradient background (MyTube brand purple-to-green
  gradient: `linear-gradient(135deg, #6d40cb, #62c235)`).

## Dependencies

```
pytest==8.4.2
playwright==1.58.0
```

## Install

```bash
cd /path/to/repo
pip install -r testing/requirements.txt
playwright install chromium
```

## Run

```bash
pytest testing/tests/MYTUBE-666/test_mytube_666.py -v
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | No | `https://ai-teammate.github.io/mytube` | Base URL of the web app |
| `FIREBASE_TEST_EMAIL` | Yes | — | Test user email |
| `FIREBASE_TEST_PASSWORD` | Yes | — | Test user password |
| `PLAYWRIGHT_HEADLESS` | No | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | No | `0` | Slow-motion delay in ms |

## Expected output when tests pass

```
testing/tests/MYTUBE-666/test_mytube_666.py::TestDefaultAvatarPlaceholderOnHomePage::test_avatar_placeholder_span_is_visible PASSED
testing/tests/MYTUBE-666/test_mytube_666.py::TestDefaultAvatarPlaceholderOnHomePage::test_no_custom_avatar_image_shown PASSED
testing/tests/MYTUBE-666/test_mytube_666.py::TestDefaultAvatarPlaceholderOnHomePage::test_avatar_placeholder_displays_initial PASSED
testing/tests/MYTUBE-666/test_mytube_666.py::TestDefaultAvatarPlaceholderOnHomePage::test_avatar_placeholder_has_gradient_background PASSED
```
