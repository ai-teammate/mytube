# MYTUBE-306: Direct navigation to fallback URL without session data

Automates the test case that verifies navigating to `/u/_/` without any
`sessionStorage` data correctly shows "User not found." and does **not**
rewrite the URL.

## How to run

### Install dependencies

```bash
pip install -r testing/requirements.txt
python -m playwright install chromium
```

### Run the test

```bash
cd /path/to/mytube
python -m pytest testing/tests/MYTUBE-306/test_mytube_306.py -v
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Base URL of the deployed web app |
| `PLAYWRIGHT_HEADLESS` | `true` | Set to `false` to see the browser |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms (for debugging) |

No credentials or database access are required — this is a pure client-side UI test.

## Expected output when the test passes

```
testing/tests/MYTUBE-306/test_mytube_306.py::TestDirectFallbackURLWithoutSessionData::test_user_not_found_message_is_displayed PASSED
testing/tests/MYTUBE-306/test_mytube_306.py::TestDirectFallbackURLWithoutSessionData::test_url_is_not_corrected_to_real_username PASSED
```
