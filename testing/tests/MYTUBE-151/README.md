# MYTUBE-151: Verify social media meta tags — OG title and thumbnail are present

## What this test verifies

Navigates to the video watch page and confirms that:
- `<meta property="og:title">` is present and matches the video's `<h1>` title.
- `<meta property="og:image">` is present and contains an absolute HTTPS URL (CDN thumbnail).

## Dependencies

- Python 3.11+
- `playwright` (with Chromium browser)
- `pytest`

## Install dependencies

```bash
pip install pytest playwright
playwright install chromium
```

## Test modes

The test runs in **live mode** when `API_BASE_URL` is set and a ready video with a thumbnail is reachable. It falls back to **fixture mode** (local mock API + standalone HTML) otherwise.

| Mode    | When                              | What is tested                                              |
|---------|-----------------------------------|-------------------------------------------------------------|
| Live    | `API_BASE_URL` set, video found   | Real deployed Next.js app OG injection code                 |
| Fixture | No `API_BASE_URL` or no video     | Standalone HTML that replicates the OG injection logic      |

## Environment variables

| Variable             | Default                               | Description                                                |
|----------------------|---------------------------------------|------------------------------------------------------------|
| `WEB_BASE_URL`       | `https://ai-teammate.github.io/mytube`| Base URL of the deployed web app (live mode navigation)    |
| `APP_URL`            | —                                     | Alternative base URL for the web app (takes priority)      |
| `API_BASE_URL`       | —                                     | Backend API base URL; when set, enables live mode          |
| `PLAYWRIGHT_HEADLESS`| `true`                                | Run headless (`true`/`false`)                              |
| `PLAYWRIGHT_SLOW_MO` | `0`                                   | Slow-motion delay in ms (debug)                            |

## Run the test

From the repository root:

```bash
# Fixture mode (no backend required)
pytest testing/tests/MYTUBE-151/test_mytube_151.py -v

# Live mode (tests against real deployed app)
API_BASE_URL=https://your-api.run.app \
  WEB_BASE_URL=https://ai-teammate.github.io/mytube \
  pytest testing/tests/MYTUBE-151/test_mytube_151.py -v
```

## Expected output when the test passes

```
testing/tests/MYTUBE-151/test_mytube_151.py::TestOGMetaTags::test_og_title_is_present PASSED
testing/tests/MYTUBE-151/test_mytube_151.py::TestOGMetaTags::test_og_title_matches_video_title PASSED
testing/tests/MYTUBE-151/test_mytube_151.py::TestOGMetaTags::test_og_title_matches_known_video_title PASSED
testing/tests/MYTUBE-151/test_mytube_151.py::TestOGMetaTags::test_og_image_is_present PASSED
testing/tests/MYTUBE-151/test_mytube_151.py::TestOGMetaTags::test_og_image_is_absolute_url PASSED
testing/tests/MYTUBE-151/test_mytube_151.py::TestOGMetaTags::test_og_image_matches_thumbnail_url PASSED
```

## Preconditions

**Live mode**: A user with username `tester` must exist and have at least one video in `ready` status with a `thumbnail_url` set in the backend database.

**Fixture mode**: No external services required.
