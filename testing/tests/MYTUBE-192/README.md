# MYTUBE-192: View video list on dashboard — grid displays correct metadata and status badges

Verifies that the video management dashboard (`/dashboard`) correctly renders the list of user videos with all required visual elements: thumbnail, title, status badge, view count, and formatted creation date.

## Dependencies

```
pip install playwright pytest psycopg2-binary
playwright install chromium
```

## Environment Variables

| Variable                | Required | Default                                | Description                                        |
|-------------------------|----------|----------------------------------------|----------------------------------------------------|
| `FIREBASE_TEST_EMAIL`   | Yes      | —                                      | Email of the registered Firebase test user         |
| `FIREBASE_TEST_PASSWORD`| Yes      | —                                      | Password for the Firebase test user                |
| `FIREBASE_TEST_UID`     | No       | `ci-test-user-001`                     | Firebase UID of the test user (must match login)   |
| `WEB_BASE_URL`          | No       | `https://ai-teammate.github.io/mytube` | Base URL of the deployed web app                   |
| `APP_URL`               | No       | (falls back to WEB_BASE_URL)           | Alternative base URL (takes priority)              |
| `DB_HOST`               | No       | `localhost`                            | PostgreSQL host                                    |
| `DB_PORT`               | No       | `5432`                                 | PostgreSQL port                                    |
| `DB_USER`               | No       | `postgres`                             | PostgreSQL user                                    |
| `DB_PASSWORD`           | No       | `postgres`                             | PostgreSQL password                                |
| `DB_NAME`               | No       | `mytube`                               | PostgreSQL database name                           |
| `PLAYWRIGHT_HEADLESS`   | No       | `true`                                 | Run browser in headless mode                       |
| `PLAYWRIGHT_SLOW_MO`    | No       | `0`                                    | Slow-motion delay in ms (debugging)                |

## How to Run

```bash
pytest testing/tests/MYTUBE-192/test_mytube_192.py -v
```

## Expected Output (passing)

```
testing/tests/MYTUBE-192/test_mytube_192.py::TestDashboardVideoList::test_video_table_is_visible PASSED
testing/tests/MYTUBE-192/test_mytube_192.py::TestDashboardVideoList::test_ready_video_title_is_displayed PASSED
testing/tests/MYTUBE-192/test_mytube_192.py::TestDashboardVideoList::test_ready_video_status_badge_shows_ready PASSED
testing/tests/MYTUBE-192/test_mytube_192.py::TestDashboardVideoList::test_processing_video_status_badge_shows_processing PASSED
testing/tests/MYTUBE-192/test_mytube_192.py::TestDashboardVideoList::test_ready_video_has_thumbnail_element PASSED
testing/tests/MYTUBE-192/test_mytube_192.py::TestDashboardVideoList::test_ready_video_view_count_is_visible PASSED
testing/tests/MYTUBE-192/test_mytube_192.py::TestDashboardVideoList::test_ready_video_creation_date_is_visible PASSED
```

## Architecture

```
test_mytube_192.py
    └── DashboardPage      (testing/components/pages/dashboard_page/dashboard_page.py)
    └── LoginPage          (testing/components/pages/login_page/login_page.py)
    └── UserService        (testing/components/services/user_service.py)
    └── VideoService       (testing/components/services/video_service.py)
    └── WebConfig          (testing/core/config/web_config.py)
    └── DBConfig           (testing/core/config/db_config.py)
```

The test seeds a CI test user (matched by `FIREBASE_TEST_UID`) and two videos (one `ready`, one `processing`) directly in the database, then logs in via the login page, navigates to `/dashboard`, and asserts that the video table renders all required elements: thumbnail column, title, status badges, view count, and creation date.
