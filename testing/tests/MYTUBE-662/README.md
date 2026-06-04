# MYTUBE-662: Legacy copy removal — 'personal video portal' is no longer present

## Purpose

Verify that the old positioning text "personal video portal" has been completely
removed from the homepage UI.

## Dependencies

Install Python dependencies from the testing folder:

```bash
pip install -r testing/requirements.txt
playwright install chromium
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Base URL of the deployed web app |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms |

## Run command

```bash
pytest testing/tests/MYTUBE-662/test_mytube_662.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-662/test_mytube_662.py::test_personal_video_portal_text_removed PASSED
```
