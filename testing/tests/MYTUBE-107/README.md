# MYTUBE-107: Login with email and password — user authenticated and redirected to home

## Objective

Verify that a registered user can sign in on the `/login` page using a valid
email and password, and is subsequently redirected to the home page (`/`).

## Prerequisites

- Python 3.10+
- `playwright` Python package and Chromium browser installed
- A Firebase project with a registered test user account

```bash
pip install playwright pytest
python -m playwright install chromium
```

## Environment Variables

| Variable                | Default                                    | Description                                  |
|-------------------------|--------------------------------------------|----------------------------------------------|
| `FIREBASE_TEST_EMAIL`   | *(required)*                               | Email of the registered Firebase test user   |
| `FIREBASE_TEST_PASSWORD`| *(required)*                               | Password of the registered Firebase test user|
| `WEB_BASE_URL`          | `https://ai-teammate.github.io/mytube`     | Base URL of the deployed web application     |
| `PLAYWRIGHT_HEADLESS`   | `true`                                     | Set to `false` to watch the browser          |
| `PLAYWRIGHT_SLOW_MO`    | `0`                                        | Slow-motion delay in ms (useful for debugging)|

## How to Run

```bash
export FIREBASE_TEST_EMAIL="your-test-user@example.com"
export FIREBASE_TEST_PASSWORD="YourPassword123!"

pytest testing/tests/MYTUBE-107/test_mytube_107.py -v
```

Run from the repo root:
```bash
cd /path/to/mytube
pytest testing/tests/MYTUBE-107/test_mytube_107.py -v
```

## Expected Output (passing)

```
testing/tests/MYTUBE-107/test_mytube_107.py::TestLoginFlow::test_redirected_to_home_page PASSED
testing/tests/MYTUBE-107/test_mytube_107.py::TestLoginFlow::test_firebase_token_in_local_storage PASSED
testing/tests/MYTUBE-107/test_mytube_107.py::TestLoginFlow::test_no_error_message_displayed PASSED

3 passed
```

## Skip Behavior

When `FIREBASE_TEST_EMAIL` or `FIREBASE_TEST_PASSWORD` is not set, the entire
test module is skipped:

```
SKIPPED [3] testing/tests/MYTUBE-107/test_mytube_107.py: FIREBASE_TEST_EMAIL not set — ...
```

## Architecture

```
testing/tests/MYTUBE-107/
├── test_mytube_107.py          ← Test logic (this file)
├── config.yaml                 ← Test metadata
└── README.md                   ← This file

testing/components/pages/login_page/
└── login_page.py               ← LoginPage Page Object (reusable)

testing/core/config/
└── web_config.py               ← WebConfig (env var reader)
```
