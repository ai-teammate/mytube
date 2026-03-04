# MYTUBE-233 — Save to playlist on watch page

## Objective

Verify the "Save to playlist" feature on the video watch page for authenticated
users.  A dropdown must appear with the user's playlist titles, and selecting a
playlist must successfully add the video to that collection.

---

## Prerequisites

- Python 3.10+
- [Playwright](https://playwright.dev/python/) with Chromium

### Install dependencies

```bash
pip install pytest playwright
playwright install chromium
```

---

## Environment variables

| Variable               | Required | Default                                             | Description                                   |
|------------------------|----------|-----------------------------------------------------|-----------------------------------------------|
| `FIREBASE_TEST_EMAIL`  | **Yes**  | —                                                   | Email of the Firebase test user               |
| `FIREBASE_TEST_PASSWORD` | **Yes** | —                                                  | Password of the Firebase test user            |
| `FIREBASE_API_KEY`     | **Yes*** | —                                                   | Firebase web API key (for token generation). Not needed if `FIREBASE_TEST_TOKEN` is set. |
| `FIREBASE_TEST_TOKEN`  | No       | —                                                   | Pre-generated Firebase ID token (CI provides this) |
| `API_BASE_URL`         | No       | `https://mytube-api-80693608388.us-central1.run.app` | Backend API base URL                         |
| `APP_URL`              | No       | `https://ai-teammate.github.io/mytube`              | Base URL of the deployed web app              |
| `PLAYWRIGHT_HEADLESS`  | No       | `true`                                              | Run browser headless (`true`/`false`)         |
| `PLAYWRIGHT_SLOW_MO`   | No       | `0`                                                 | Slow-motion delay in ms (for debugging)       |

---

## How to run

From the repository root:

```bash
pytest testing/tests/MYTUBE-233/test_mytube_233.py -v
```

With explicit credentials:

```bash
FIREBASE_TEST_EMAIL=ci-test@mytube.test \
FIREBASE_TEST_PASSWORD=secret \
FIREBASE_API_KEY=AIza... \
pytest testing/tests/MYTUBE-233/test_mytube_233.py -v
```

---

## Expected output (passing)

```
testing/tests/MYTUBE-233/test_mytube_233.py::TestSaveToPlaylistDropdown::test_save_button_is_visible_for_authenticated_user PASSED
testing/tests/MYTUBE-233/test_mytube_233.py::TestSaveToPlaylistDropdown::test_dropdown_opens_on_button_click PASSED
testing/tests/MYTUBE-233/test_mytube_233.py::TestSaveToPlaylistDropdown::test_dropdown_contains_user_playlist_titles PASSED
testing/tests/MYTUBE-233/test_mytube_233.py::TestSaveToPlaylistDropdown::test_selecting_playlist_shows_success_indicator PASSED
```

---

## Test cases covered

| # | Scenario                                         | Expected behaviour                                              |
|---|--------------------------------------------------|-----------------------------------------------------------------|
| 1 | Navigate to watch page while authenticated       | "Save to playlist" button is visible                            |
| 2 | Click "Save to playlist" button                  | Dropdown (div[role="menu"]) opens                               |
| 3 | Dropdown renders after playlists load            | Both test playlists appear as menu items                        |
| 4 | Click a playlist item                            | ✓ saved indicator (span[aria-label="Saved"]) appears, no error |

---

## Architecture

- **New component**: `testing/components/pages/watch_page/save_to_playlist_widget.py`
- **Reused components**: `WatchPage`, `LoginPage`, `VideoApiService`, `AuthService`
- **Config**: `testing/core/config/web_config.py`, `testing/core/config/api_config.py`
- **Framework**: Playwright (sync API) + pytest

## Test setup / teardown

The fixture creates two playlists via `POST /api/playlists` before the tests run
and deletes them via `DELETE /api/playlists/:id` after the module completes.
No database access required — all setup is done through the deployed API.
