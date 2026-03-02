# MYTUBE-117 — Access profile of non-existent user: application returns 404

Automates the test case: *Access profile of non-existent user — application returns 404.*

## What is tested

1. **Part A (Jest — data layer)**: `ApiUserProfileRepository.getByUsername()` returns `null` when the backend API responds with HTTP 404 for an unknown username.
2. **Part B (Jest — component layer)**: The `UserProfilePage` React component renders `"User not found."` when the repository returns `null` (the null value produced by a 404 API response).
3. **Part C (Playwright E2E)**: Navigating the deployed web app to `/u/non_existent_user_999` shows the `"User not found."` message and produces no JavaScript errors. Skipped automatically when `APP_URL` is not reachable.

## Dependencies

```bash
# Python dependencies
pip install playwright pytest

# Install Playwright browser
playwright install chromium

# Node/web dependencies (for Parts A & B – Jest)
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
testing/tests/MYTUBE-117/test_mytube_117.py::TestUserProfileRepositoryReturnsNullOn404::test_repository_returns_null_when_api_returns_404 PASSED
testing/tests/MYTUBE-117/test_mytube_117.py::TestUserProfilePageShowsNotFoundMessage::test_component_shows_not_found_when_profile_is_null PASSED
testing/tests/MYTUBE-117/test_mytube_117.py::TestUserProfileNotFoundE2E::test_non_existent_user_profile_shows_not_found_message PASSED
testing/tests/MYTUBE-117/test_mytube_117.py::TestUserProfileNotFoundE2E::test_non_existent_user_profile_url_is_accessible PASSED
```
