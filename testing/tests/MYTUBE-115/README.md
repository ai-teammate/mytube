# MYTUBE-115: View public user profile — page displays user info and ready videos

## Objective

Verify that a visitor can navigate to `/u/tester` and see the user's avatar,
the username heading, and a grid of video thumbnails that each link to the
correct `/v/<id>` URL.

## Prerequisites

- Python 3.10+
- `playwright` Python package and Chromium browser installed

```bash
pip install playwright pytest
python -m playwright install chromium
```

- A user with username `tester` must exist in the database and have at least one
  video with `ready` status.
- The web application must be deployed and reachable.

## Environment Variables

| Variable              | Default                                | Description                              |
|-----------------------|----------------------------------------|------------------------------------------|
| `WEB_BASE_URL`        | `https://ai-teammate.github.io/mytube` | Base URL of the deployed web application |
| `PLAYWRIGHT_HEADLESS` | `true`                                 | Set to `false` to watch the browser      |
| `PLAYWRIGHT_SLOW_MO`  | `0`                                    | Slow-motion delay in ms for debugging    |

## How to Run

```bash
# From the repo root:
pytest testing/tests/MYTUBE-115/test_mytube_115.py -v
```

With a custom base URL:

```bash
WEB_BASE_URL="https://your-deployment.example.com" \
  pytest testing/tests/MYTUBE-115/test_mytube_115.py -v
```

## Expected Output (passing)

```
testing/tests/MYTUBE-115/test_mytube_115.py::TestPublicUserProfile::test_avatar_is_visible PASSED
testing/tests/MYTUBE-115/test_mytube_115.py::TestPublicUserProfile::test_username_heading_displays_tester PASSED
testing/tests/MYTUBE-115/test_mytube_115.py::TestPublicUserProfile::test_video_grid_has_at_least_one_card PASSED
testing/tests/MYTUBE-115/test_mytube_115.py::TestPublicUserProfile::test_video_cards_link_to_video_pages PASSED

4 passed
```

## Architecture

```
testing/tests/MYTUBE-115/
├── test_mytube_115.py          ← Test logic
├── config.yaml                 ← Test metadata
└── README.md                   ← This file

testing/components/pages/profile_page/
└── profile_page.py             ← ProfilePage Page Object (reusable)

testing/core/config/
└── web_config.py               ← WebConfig (env var reader)
```
