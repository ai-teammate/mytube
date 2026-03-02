# MYTUBE-109 — Register new account via UI

Automates the test case: *Register new account via UI — account created and upsert API triggered.*

## What is tested

1. The `/register` page renders the registration form.
2. Submitting a valid new email + password creates a Firebase account and redirects away from `/register`.
3. After registration, the app calls `GET /api/me` (captured via network interception) to trigger the backend database upsert.

## Dependencies

```bash
pip install playwright pytest
playwright install chromium
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` | `https://ai-teammate.github.io/mytube` | Deployed frontend base URL |

## How to run

```bash
# From the repository root:
APP_URL=https://ai-teammate.github.io/mytube \
  pytest testing/tests/MYTUBE-109/test_mytube_109.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-109/test_mytube_109.py::TestRegisterPageLoads::test_register_page_heading_is_visible PASSED
testing/tests/MYTUBE-109/test_mytube_109.py::TestRegistrationFlow::test_successful_registration_redirects_away PASSED
testing/tests/MYTUBE-109/test_mytube_109.py::TestRegistrationFlow::test_successful_registration_calls_api_me PASSED
testing/tests/MYTUBE-109/test_mytube_109.py::TestRegistrationFlow::test_no_error_shown_on_successful_registration PASSED
```
