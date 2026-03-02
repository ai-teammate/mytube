# MYTUBE-142: Access /upload page while unauthenticated — user redirected to login

Verifies that the video upload page (`/upload`) is inaccessible to unauthenticated users.
When a user who is not logged in navigates directly to `/upload`, the application must
automatically redirect them to the `/login` page.

## Dependencies

```
pip install playwright pytest
playwright install chromium
```

## Environment Variables

| Variable             | Required | Default                                  | Description                          |
|----------------------|----------|------------------------------------------|--------------------------------------|
| `WEB_BASE_URL`       | No       | `https://ai-teammate.github.io/mytube`   | Base URL of the deployed web app     |
| `APP_URL`            | No       | (falls back to WEB_BASE_URL)             | Alternative base URL (takes priority)|
| `PLAYWRIGHT_HEADLESS`| No       | `true`                                   | Run browser in headless mode         |
| `PLAYWRIGHT_SLOW_MO` | No       | `0`                                      | Slow-motion delay in ms (debugging)  |

## How to Run

```bash
pytest testing/tests/MYTUBE-142/test_mytube_142.py -v
```

## Expected Output (passing)

```
testing/tests/MYTUBE-142/test_mytube_142.py::TestUploadPageUnauthenticated::test_redirected_to_login_page PASSED
testing/tests/MYTUBE-142/test_mytube_142.py::TestUploadPageUnauthenticated::test_not_remaining_on_upload_page PASSED
```

## Architecture

```
test_mytube_142.py
    └── UploadPage  (testing/components/pages/upload_page/upload_page.py)
    └── WebConfig   (testing/core/config/web_config.py)
```

The test opens a **fresh browser context** with no stored authentication state,
navigates directly to `/upload`, and asserts that the application redirects to `/login`.
