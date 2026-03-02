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

## Environment variables

| Variable             | Default                               | Description                          |
|----------------------|---------------------------------------|--------------------------------------|
| `WEB_BASE_URL`       | `https://ai-teammate.github.io/mytube`| Base URL of the deployed web app     |
| `APP_URL`            | —                                     | Alternative base URL (takes priority)|
| `PLAYWRIGHT_HEADLESS`| `true`                                | Run headless (`true`/`false`)        |
| `PLAYWRIGHT_SLOW_MO` | `0`                                   | Slow-motion delay in ms (debug)      |

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-151/test_mytube_151.py -v
```

With a custom base URL:

```bash
WEB_BASE_URL=https://ai-teammate.github.io/mytube pytest testing/tests/MYTUBE-151/test_mytube_151.py -v
```

## Expected output when the test passes

```
testing/tests/MYTUBE-151/test_mytube_151.py::TestOGMetaTags::test_og_title_is_present PASSED
testing/tests/MYTUBE-151/test_mytube_151.py::TestOGMetaTags::test_og_title_matches_video_title PASSED
testing/tests/MYTUBE-151/test_mytube_151.py::TestOGMetaTags::test_og_image_is_present PASSED
testing/tests/MYTUBE-151/test_mytube_151.py::TestOGMetaTags::test_og_image_is_absolute_url PASSED
```

## Preconditions

A user with username `tester` must exist with at least one video in `ready` status (has a thumbnail).
