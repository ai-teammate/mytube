# MYTUBE-205 — Rating Widget UI Test

Verifies that the star rating widget on the video watch page correctly renders
the average rating/count from the API and allows an authenticated user to click
a star and see the display update.

## What is tested

1. The star rating widget is present on the watch page.
2. The widget displays `4.2 / 5 (10 ratings)` (from a mocked GET response).
3. No "Log in to rate" prompt is shown for a logged-in user.
4. After clicking the 5th star, the widget updates to `4.3 / 5 (11 ratings)`
   (from a mocked POST response) and star 5 has `aria-pressed="true"`.

The rating API (`GET /api/videos/{id}/rating` and `POST /api/videos/{id}/rating`)
is mocked via Playwright route interception so tests are deterministic and do
not depend on real DB data.

## Dependencies

```
playwright
pytest
```

Install:

```bash
pip install pytest playwright
playwright install chromium
```

## Required environment variables

| Variable | Description |
|---|---|
| `FIREBASE_TEST_EMAIL` | E-mail of the Firebase CI test user |
| `FIREBASE_TEST_PASSWORD` | Password for the Firebase CI test user |
| `APP_URL` or `WEB_BASE_URL` | Deployed frontend URL (default: `https://ai-teammate.github.io/mytube`) |
| `API_BASE_URL` | Backend API URL for video discovery (default: `https://mytube-api-80693608388.us-central1.run.app`) |
| `PLAYWRIGHT_HEADLESS` | `true` (default) or `false` for headed mode |

## Running the test

From the repository root:

```bash
export FIREBASE_TEST_EMAIL="ci-test@mytube.test"
export FIREBASE_TEST_PASSWORD="<secret>"

cd /path/to/mytube
python -m pytest testing/tests/MYTUBE-205/test_mytube_205.py -v
```

## Expected output when passing

```
testing/tests/MYTUBE-205/test_mytube_205.py::TestRatingWidgetDisplay::test_rating_widget_is_visible PASSED
testing/tests/MYTUBE-205/test_mytube_205.py::TestRatingWidgetDisplay::test_rating_summary_shows_average PASSED
testing/tests/MYTUBE-205/test_mytube_205.py::TestRatingWidgetDisplay::test_rating_summary_shows_count PASSED
testing/tests/MYTUBE-205/test_mytube_205.py::TestRatingWidgetDisplay::test_login_to_rate_prompt_not_shown_for_logged_in_user PASSED
testing/tests/MYTUBE-205/test_mytube_205.py::TestRatingWidgetInteraction::test_summary_updates_after_star_click PASSED
testing/tests/MYTUBE-205/test_mytube_205.py::TestRatingWidgetInteraction::test_count_updates_after_star_click PASSED
testing/tests/MYTUBE-205/test_mytube_205.py::TestRatingWidgetInteraction::test_fifth_star_is_pressed_after_click PASSED
```

## When credentials are missing

The test skips cleanly via `pytest.skip()` with a descriptive message.
No test failure is reported.
