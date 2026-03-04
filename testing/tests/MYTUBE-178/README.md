# MYTUBE-178: Homepage discovery sections — Recently Uploaded and Most Viewed displayed

Verifies the homepage correctly displays both discovery sections with video card components.

## What is tested

- The "Recently Uploaded" section is visible with the correct heading.
- The "Most Viewed" section is visible with the correct heading.
- Each section contains between 1 and 20 video cards.
- Every video card links to `/v/<id>`.
- Every video card shows an uploader username (link to `/u/<username>`).
- Every video card shows a view count.

## Dependencies

| Dependency | Description |
|---|---|
| `WEB_BASE_URL` | Base URL of the deployed web app (default: `https://ai-teammate.github.io/mytube`) |

## Install dependencies

```bash
pip install playwright pytest
playwright install chromium
```

## Run the test

```bash
cd /path/to/repo
pytest testing/tests/MYTUBE-178/test_mytube_178.py -v
```

With a custom base URL:

```bash
WEB_BASE_URL=https://your-deployment.example.com pytest testing/tests/MYTUBE-178/test_mytube_178.py -v
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Base URL of the deployed web app |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser in headless mode |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay (ms) for debugging |

## Expected output when passing

```
testing/tests/MYTUBE-178/test_mytube_178.py::TestHomepageDiscoverySections::test_recently_uploaded_section_is_visible PASSED
testing/tests/MYTUBE-178/test_mytube_178.py::TestHomepageDiscoverySections::test_most_viewed_section_is_visible PASSED
testing/tests/MYTUBE-178/test_mytube_178.py::TestHomepageDiscoverySections::test_recently_uploaded_heading_text PASSED
testing/tests/MYTUBE-178/test_mytube_178.py::TestHomepageDiscoverySections::test_most_viewed_heading_text PASSED
testing/tests/MYTUBE-178/test_mytube_178.py::TestHomepageDiscoverySections::test_recently_uploaded_has_cards PASSED
testing/tests/MYTUBE-178/test_mytube_178.py::TestHomepageDiscoverySections::test_recently_uploaded_card_count_at_most_20 PASSED
testing/tests/MYTUBE-178/test_mytube_178.py::TestHomepageDiscoverySections::test_most_viewed_has_cards PASSED
testing/tests/MYTUBE-178/test_mytube_178.py::TestHomepageDiscoverySections::test_most_viewed_card_count_at_most_20 PASSED
testing/tests/MYTUBE-178/test_mytube_178.py::TestHomepageDiscoverySections::test_recently_uploaded_cards_link_to_video_pages PASSED
testing/tests/MYTUBE-178/test_mytube_178.py::TestHomepageDiscoverySections::test_most_viewed_cards_link_to_video_pages PASSED
testing/tests/MYTUBE-178/test_mytube_178.py::TestHomepageDiscoverySections::test_recently_uploaded_cards_have_uploader_username PASSED
testing/tests/MYTUBE-178/test_mytube_178.py::TestHomepageDiscoverySections::test_most_viewed_cards_have_uploader_username PASSED
testing/tests/MYTUBE-178/test_mytube_178.py::TestHomepageDiscoverySections::test_recently_uploaded_cards_have_view_count PASSED
testing/tests/MYTUBE-178/test_mytube_178.py::TestHomepageDiscoverySections::test_most_viewed_cards_have_view_count PASSED
```

## Page Object

Uses `HomePage` from `testing/components/pages/home_page/home_page.py`.
