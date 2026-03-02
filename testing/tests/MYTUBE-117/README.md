# MYTUBE-117 — Access profile of non-existent user: application returns 404

Automates the test case: *Access profile of non-existent user — application returns 404.*

## What is tested

1. **Part A (Jest)**: The `UserProfilePage` React component renders `"User not found."` when the repository returns `null` (simulating a `GET /api/users/<username>` HTTP 404 response).
2. **Part B (Playwright E2E)**: Navigating the deployed web app to `/u/non_existent_user_999` shows the `"User not found."` message and produces no JavaScript errors.

## Dependencies

```bash
# Python dependencies
pip install playwright pytest

# Install Playwright browser
playwright install chromium

# Node/web dependencies (for Part A – Jest)
cd web && npm install
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` | `https://ai-teammate.github.io/mytube` | Deployed frontend base URL |

## How to run

```bash
# From the repository root:
APP_URL=https://ai-teammate.github.io/mytube \
  pytest testing/tests/MYTUBE-117/test_mytube_117.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-117/test_mytube_117.py::TestUserProfileNotFoundUnit::test_component_shows_not_found_when_profile_is_null PASSED
testing/tests/MYTUBE-117/test_mytube_117.py::TestUserProfileNotFoundE2E::test_non_existent_user_profile_shows_not_found_message PASSED
testing/tests/MYTUBE-117/test_mytube_117.py::TestUserProfileNotFoundE2E::test_non_existent_user_profile_url_is_accessible PASSED
```
