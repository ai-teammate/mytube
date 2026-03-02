# MYTUBE-150: Verify watch page metadata display — uploader link and tags are correct

Verifies that the video watch page (`/v/:id`) correctly renders all video metadata
(title, description, tags) and that the uploader name links to the correct user profile page (`/u/:username`).

## Dependencies

```
pip install playwright pytest psycopg2-binary
playwright install chromium
```

## Environment Variables

| Variable              | Required | Default                                | Description                                        |
|-----------------------|----------|----------------------------------------|----------------------------------------------------|
| `WEB_BASE_URL`        | No       | `https://ai-teammate.github.io/mytube` | Base URL of the deployed web app                   |
| `APP_URL`             | No       | (falls back to WEB_BASE_URL)           | Alternative base URL (takes priority)              |
| `API_BASE_URL`        | No       | `http://localhost:8081`                | Base URL of the backend API server                 |
| `DB_HOST`             | No       | `localhost`                            | PostgreSQL host                                    |
| `DB_PORT`             | No       | `5432`                                 | PostgreSQL port                                    |
| `DB_USER`             | No       | `postgres`                             | PostgreSQL user                                    |
| `DB_PASSWORD`         | No       | `postgres`                             | PostgreSQL password                                |
| `DB_NAME`             | No       | `mytube`                               | PostgreSQL database name                           |
| `PLAYWRIGHT_HEADLESS` | No       | `true`                                 | Run browser in headless mode                       |
| `PLAYWRIGHT_SLOW_MO`  | No       | `0`                                    | Slow-motion delay in ms (debugging)                |

## How to Run

```bash
pytest testing/tests/MYTUBE-150/test_mytube_150.py -v
```

## Expected Output (passing)

```
testing/tests/MYTUBE-150/test_mytube_150.py::TestWatchPageMetadata::test_title_matches_database_record PASSED
testing/tests/MYTUBE-150/test_mytube_150.py::TestWatchPageMetadata::test_description_matches_database_record PASSED
testing/tests/MYTUBE-150/test_mytube_150.py::TestWatchPageMetadata::test_tags_match_database_record PASSED
testing/tests/MYTUBE-150/test_mytube_150.py::TestWatchPageMetadata::test_uploader_link_text_matches_username PASSED
testing/tests/MYTUBE-150/test_mytube_150.py::TestWatchPageMetadata::test_uploader_link_href_points_to_profile PASSED
testing/tests/MYTUBE-150/test_mytube_150.py::TestWatchPageUploaderRedirect::test_clicking_uploader_navigates_to_user_profile PASSED
testing/tests/MYTUBE-150/test_mytube_150.py::TestWatchPageUploaderRedirect::test_user_profile_page_loads_without_error PASSED
```

## Architecture

```
test_mytube_150.py
    └── WatchPage          (testing/components/pages/watch_page/watch_page.py)
    └── UserProfilePage    (testing/components/pages/user_profile_page/user_profile_page.py)
    └── UserService        (testing/components/services/user_service.py)
    └── VideoService       (testing/components/services/video_service.py)
    └── WebConfig          (testing/core/config/web_config.py)
    └── DBConfig           (testing/core/config/db_config.py)
```

The test seeds a test user and a ready video (with description and tags) via the `UserService` and
`VideoService` component objects, navigates to the watch page in headless Chromium, and asserts that
all metadata rendered in the DOM matches the seeded database values. It also verifies that clicking
the uploader link redirects to `/u/<username>` and that the profile page loads without error.
