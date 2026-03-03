# MYTUBE-206 — Comment section for guest: login message shown instead of input

Verifies that unauthenticated users see "Login to comment" instead of the
comment textarea and submit button on the video watch page.

## How to run

```bash
# From the repository root
cd testing
pip install playwright pytest
playwright install chromium

# Against the deployed app (live mode):
API_BASE_URL=https://mytube-api-80693608388.us-central1.run.app \
APP_URL=https://ai-teammate.github.io/mytube \
python -m pytest tests/MYTUBE-206/test_mytube_206.py -v

# Offline / fixture mode (no external dependencies):
python -m pytest tests/MYTUBE-206/test_mytube_206.py -v
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Frontend base URL |
| `API_BASE_URL` | *(unset)* | Backend API base URL; enables live mode when set |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms |

## Modes

- **Live mode** — `API_BASE_URL` is set and a ready video is discoverable.
  Navigates to the real deployed app as an unauthenticated user.
- **Fixture mode** — fallback when the API is unavailable.
  Starts a local HTTP server at port `19206` serving
  `testing/fixtures/watch_page/guest_comment_section.html`.

## Expected output when the test passes

```
tests/MYTUBE-206/test_mytube_206.py::TestGuestCommentSection::test_comment_section_heading_visible PASSED
tests/MYTUBE-206/test_mytube_206.py::TestGuestCommentSection::test_login_to_comment_prompt_visible PASSED
tests/MYTUBE-206/test_mytube_206.py::TestGuestCommentSection::test_login_link_points_to_login_page PASSED
tests/MYTUBE-206/test_mytube_206.py::TestGuestCommentSection::test_comment_textarea_not_present PASSED
tests/MYTUBE-206/test_mytube_206.py::TestGuestCommentSection::test_comment_submit_button_not_present PASSED
```
