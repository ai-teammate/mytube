# MYTUBE-141: Select video file larger than 4 GB — client-side size limit warning

Automated Playwright test that verifies the `/upload` page displays a warning
when the user selects a video file exceeding 4 GB in size.

## How it works

The test simulates selecting a large file by injecting a JavaScript `File`
object with an overridden `size` property into the file input and dispatching
a `change` event. This avoids needing a real 4 GB file on disk.

## Prerequisites

- Python 3.9+
- `pytest`, `playwright` packages installed

## Install dependencies

```bash
pip install pytest playwright
playwright install chromium
```

## Environment variables

| Variable               | Required | Description                                    | Default                                  |
|------------------------|----------|------------------------------------------------|------------------------------------------|
| `FIREBASE_TEST_EMAIL`  | Yes      | Email of a registered Firebase test user       | —                                        |
| `FIREBASE_TEST_PASSWORD` | Yes    | Password for the Firebase test user            | —                                        |
| `WEB_BASE_URL`         | No       | Base URL of the deployed web application       | `https://ai-teammate.github.io/mytube`   |
| `PLAYWRIGHT_HEADLESS`  | No       | Run browser in headless mode (`true`/`false`)  | `true`                                   |
| `PLAYWRIGHT_SLOW_MO`   | No       | Slow-motion delay in ms for debugging          | `0`                                      |

## Run the test

From the repository root:

```bash
FIREBASE_TEST_EMAIL=user@example.com \
FIREBASE_TEST_PASSWORD=yourpassword \
WEB_BASE_URL=https://ai-teammate.github.io/mytube \
pytest testing/tests/MYTUBE-141/test_mytube_141.py -v
```

## Expected output when passing

```
testing/tests/MYTUBE-141/test_mytube_141.py::TestFileSizeLimitWarning::test_warning_is_displayed_for_file_over_4gb PASSED
testing/tests/MYTUBE-141/test_mytube_141.py::TestFileSizeLimitWarning::test_warning_message_contains_expected_text PASSED
testing/tests/MYTUBE-141/test_mytube_141.py::TestFileSizeLimitWarning::test_no_warning_for_file_under_4gb PASSED
```
