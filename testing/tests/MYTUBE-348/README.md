# MYTUBE-348: Authenticate after redirect — original URL and query parameters preserved

## Test Objective

Verify that after a successful login, the user is redirected back to the URL they originally attempted to access, including all query parameters (`category=gaming&priority=high`).

## Requirements

- **Ticket**: MYTUBE-348
- **Type**: Web UI (Playwright)
- **Framework**: Playwright (sync API)
- **Browser**: Chromium

## Dependencies

```bash
pip install -r testing/requirements.txt
python -m playwright install chromium
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FIREBASE_TEST_EMAIL` | Yes | Email of the Firebase test user |
| `FIREBASE_TEST_PASSWORD` | Yes | Password for the test user |
| `APP_URL` / `WEB_BASE_URL` | No | Defaults to `https://ai-teammate.github.io/mytube` |
| `PLAYWRIGHT_HEADLESS` | No | Defaults to `true` |

## How to Run

```bash
cd /home/runner/work/mytube/mytube

pytest testing/tests/MYTUBE-348/test_mytube_348.py -v
```

## Test Cases

### 1. test_unauthenticated_access_redirects_to_login
Navigating to `/upload?category=gaming&priority=high` while unauthenticated must redirect to `/login`.

### 2. test_login_page_shows_sign_in_form
The login form is visible after redirect.

### 3. test_after_login_redirects_back_with_query_params
After login, browser must land on `/upload?category=gaming&priority=high` — both path and query params preserved.

## Expected Output (when passing)

```
3 passed in X.XXs
```
