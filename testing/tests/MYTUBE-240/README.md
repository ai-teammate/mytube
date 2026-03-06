# MYTUBE-240 — Navigate to registration page — page loads and "Create an account" heading is visible

## Objective

Verify that the registration page is correctly served by the deployment environment and displays the required UI elements.

## Test Type

`web` — Web UI testing using Playwright.

## Prerequisites

- Python 3.10+
- Playwright browser binaries (`playwright install chromium`)
- `pytest`
- `pytest-playwright` (optional, for CLI integration)
- Deployed application accessible at the configured base URL

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_URL` / `WEB_BASE_URL` | No | Base URL of the deployed web application. Default: `https://ai-teammate.github.io/mytube` |
| `PLAYWRIGHT_HEADLESS` | No | Run browser in headless mode (default: `true`). |
| `PLAYWRIGHT_SLOW_MO` | No | Slow-motion delay in ms for debugging (default: `0`). |

## Running the Tests

```bash
# Run against default deployment
pytest testing/tests/MYTUBE-240/test_mytube_240.py -v

# Run against local development server
APP_URL=http://localhost:3000 pytest testing/tests/MYTUBE-240/test_mytube_240.py -v

# Run with visible browser
PLAYWRIGHT_HEADLESS=false pytest testing/tests/MYTUBE-240/test_mytube_240.py -v
```

## Expected Output

```
PASSED  test_page_loads_successfully
PASSED  test_create_account_heading_is_visible
```

## Test Structure

- **Component**: `RegisterPage` (Page Object from `testing/components/pages/register_page/`)
- **Framework**: Playwright (sync API)
- **Fixture scope**: Module-scoped for performance (navigates once, reused across tests)

## Notes

The test uses the Playwright sync API with pytest fixtures. The `loaded_register_page` fixture navigates to the registration URL and waits for the page to be fully loaded before tests begin.
