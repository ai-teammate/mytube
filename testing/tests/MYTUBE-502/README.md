# MYTUBE-502 — Authenticated user avatar: gradient styling and letter rendering

## Objective

Verify the visual representation of the authenticated user's avatar matches the design spec:
a circular element with a green-to-purple gradient background that displays the first letter
of the user's display name.

## Preconditions

- User is logged into the application (Firebase test credentials must be set).

## Steps

1. Log in with Firebase test credentials and navigate to the home page.
2. Observe the user avatar in the header utility area.
3. Inspect the CSS properties of the avatar circle:
   - `border-radius` must resolve to a circle value (50% or 9999px).
   - `background-image` must be a `linear-gradient` containing green (`#62c235`) and purple colour stops.
4. Inspect the text content of the avatar span — must be exactly one uppercase alphanumeric character.

## Expected Result

The avatar is a circle with a gradient (`--gradient-hero`) containing both green (`#62c235`) and
purple (`#6d40cb` or `#9370db`) colour stops, and displays the user's initial letter (first
character of display name, uppercased).

## Test Cases

| Test | Description |
|------|-------------|
| `test_avatar_is_present_in_header` | Avatar span is present and visible in the header utility area |
| `test_avatar_is_circular` | Computed `border-radius` resolves to a circle value (50% or 9999px) |
| `test_avatar_has_gradient_background` | Background is a linear-gradient with green + purple colour stops |
| `test_avatar_displays_initial_letter` | Text content is exactly one uppercase alphanumeric character |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_URL` / `WEB_BASE_URL` | Base URL of the deployed web app | `https://ai-teammate.github.io/mytube` |
| `FIREBASE_TEST_EMAIL` | Email of the registered Firebase test user | *(required)* |
| `FIREBASE_TEST_PASSWORD` | Password of the registered Firebase test user | *(required)* |
| `PLAYWRIGHT_HEADLESS` | Run browser headless | `true` |
| `PLAYWRIGHT_SLOW_MO` | Slow-motion delay in ms | `0` |

## Environment

- **URL**: https://ai-teammate.github.io/mytube
- **Browser**: Chromium (headless)
- **Framework**: Playwright (sync API) + pytest
- **Test file**: `testing/tests/MYTUBE-502/test_mytube_502.py`
