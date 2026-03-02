# MYTUBE-140 — Upload file with unsupported MIME type

## Objective

Verify that the upload page rejects files with unsupported MIME types (e.g. PDF, PNG)
by displaying a validation error message, and that the file input `accept` attribute
restricts the OS file picker to supported video formats only.

Supported formats: **MP4, MOV, AVI, WebM**

---

## Prerequisites

- Python 3.10+
- [Playwright](https://playwright.dev/python/) with Chromium
- The web application deployed and reachable (default: `https://ai-teammate.github.io/mytube`)

### Install dependencies

```bash
pip install pytest playwright
playwright install chromium
```

---

## Environment variables

| Variable              | Required | Default                                    | Description                          |
|-----------------------|----------|--------------------------------------------|--------------------------------------|
| `FIREBASE_TEST_EMAIL`    | **Yes**  | —                                       | Email of the registered Firebase test user |
| `FIREBASE_TEST_PASSWORD` | **Yes**  | —                                       | Password of the registered Firebase test user |
| `WEB_BASE_URL`           | No       | `https://ai-teammate.github.io/mytube`  | Base URL of the deployed web app     |
| `PLAYWRIGHT_HEADLESS`    | No       | `true`                                  | Run browser headless (`true`/`false`)|
| `PLAYWRIGHT_SLOW_MO`     | No       | `0`                                     | Slow-motion delay in ms              |

---

## How to run

From the repository root:

```bash
pytest testing/tests/MYTUBE-140/test_mytube_140.py -v
```

To run against a different deployment:

```bash
WEB_BASE_URL=http://localhost:3000 pytest testing/tests/MYTUBE-140/test_mytube_140.py -v
```

---

## Expected output (passing)

```
testing/tests/MYTUBE-140/test_mytube_140.py::TestUploadUnsupportedMimeType::test_pdf_file_triggers_mime_error PASSED
testing/tests/MYTUBE-140/test_mytube_140.py::TestUploadUnsupportedMimeType::test_png_file_triggers_mime_error PASSED
testing/tests/MYTUBE-140/test_mytube_140.py::TestUploadUnsupportedMimeType::test_file_input_accept_attribute_restricts_types PASSED
```

---

## Test cases covered

| # | Scenario                          | Expected behaviour                                      |
|---|-----------------------------------|---------------------------------------------------------|
| 1 | Select `document.pdf` (PDF)       | Error alert shown, mentions MP4/MOV/AVI/WebM            |
| 2 | Select `image.png` (PNG)          | Error alert shown                                       |
| 3 | Inspect file input `accept` attr  | Only `video/mp4,video/quicktime,video/x-msvideo,video/webm` |

---

## Architecture

- **Page Object**: `testing/components/pages/upload_page/upload_page.py`
- **Config**: `testing/core/config/web_config.py`
- **Framework**: Playwright (sync API) + pytest
