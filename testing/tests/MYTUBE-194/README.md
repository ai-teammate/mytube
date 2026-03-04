# MYTUBE-194 — Confirm video deletion via dashboard UI

Automates the video-deletion workflow on `/dashboard`: verifies the inline
confirmation prompt and that the video row disappears after confirming deletion.

## Dependencies

Install Python dependencies from the repo root:

```bash
pip install playwright psycopg2-binary pytest
playwright install chromium
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `FIREBASE_TEST_EMAIL` | yes | — | CI test user email |
| `FIREBASE_TEST_PASSWORD` | yes | — | CI test user password |
| `FIREBASE_TEST_UID` | no | `ci-test-user-001` | Firebase UID of the test user |
| `APP_URL` / `WEB_BASE_URL` | no | `https://ai-teammate.github.io/mytube` | Frontend base URL |
| `DB_HOST` | no | `localhost` | PostgreSQL host |
| `DB_PORT` | no | `5432` | PostgreSQL port |
| `DB_USER` | no | `testuser` | PostgreSQL user |
| `DB_PASSWORD` | no | `testpass` | PostgreSQL password |
| `DB_NAME` | no | `mytube_test` | PostgreSQL database name |
| `PLAYWRIGHT_HEADLESS` | no | `true` | Set to `false` to watch the browser |
| `PLAYWRIGHT_SLOW_MO` | no | `0` | Slow-motion delay in ms |

## How to run

From the repository root:

```bash
cd /path/to/repo
python -m pytest testing/tests/MYTUBE-194/test_mytube_194.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-194/test_mytube_194.py::TestVideoDeletionViaUI::test_dashboard_shows_test_video PASSED
testing/tests/MYTUBE-194/test_mytube_194.py::TestVideoDeletionViaUI::test_delete_button_initially_visible PASSED
testing/tests/MYTUBE-194/test_mytube_194.py::TestVideoDeletionViaUI::test_confirmation_prompt_appears_after_delete_click PASSED
testing/tests/MYTUBE-194/test_mytube_194.py::TestVideoDeletionViaUI::test_delete_button_hidden_during_confirmation PASSED
testing/tests/MYTUBE-194/test_mytube_194.py::TestVideoDeletionViaUI::test_cancel_restores_delete_button PASSED
testing/tests/MYTUBE-194/test_mytube_194.py::TestVideoDeletionViaUI::test_video_removed_from_listing_after_confirm PASSED
6 passed in Xs
```

## Skip conditions

The entire module is skipped (not failed) when:
- `FIREBASE_TEST_EMAIL` or `FIREBASE_TEST_PASSWORD` is not set.
- The database is not reachable at the configured `DB_HOST:DB_PORT`.
- The CI test user cannot be found or created in the DB.
