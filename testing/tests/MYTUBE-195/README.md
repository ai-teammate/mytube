# MYTUBE-195: Navigate to upload page via dashboard CTA — redirection successful

Verifies that the "Upload new video" call-to-action on the dashboard correctly navigates the browser to the `/upload` page.

## Dependencies

```
pip install playwright pytest
playwright install chromium
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Base URL of the deployed web application |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms |

## How to Run

```bash
cd <repo-root>
pytest testing/tests/MYTUBE-195/test_mytube_195.py -v
```

## Expected Output (pass)

```
testing/tests/MYTUBE-195/test_mytube_195.py::TestDashboardUploadCTA::test_upload_cta_is_visible_on_dashboard PASSED
testing/tests/MYTUBE-195/test_mytube_195.py::TestDashboardUploadCTA::test_clicking_upload_cta_navigates_to_upload_page PASSED
```

## Notes

The test registers a fresh temporary Firebase account per run so no pre-existing credentials are required. The account is disposable and never reused.
