# MYTUBE-190: Soft-delete video via API — status changed to deleted

## Objective

Verify that `DELETE /api/videos/:id` performs a soft-delete by setting the
video's `status` column to `'deleted'` in the database.

## Test structure

| Layer | Description | Requirements |
|-------|-------------|--------------|
| A — Go unit tests | Runs existing `TestDeleteVideo_*` handler tests | Go toolchain only |
| B — HTTP integration | Starts local API, seeds data, calls DELETE, queries DB | `FIREBASE_TEST_TOKEN`, DB access |

## Dependencies

Install Python dependencies (psycopg2 and pytest):

```bash
pip install pytest psycopg2-binary
```

Go toolchain must be available for building the API binary.

## How to run

```bash
# From the repo root
pytest testing/tests/MYTUBE-190/test_mytube_190.py -v
```

### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FIREBASE_TEST_TOKEN` | Layer B only | — | Valid Firebase ID token for the test user |
| `FIREBASE_TEST_UID` | Layer B only | `ci-test-user-001` | Firebase UID of the test user |
| `FIREBASE_PROJECT_ID` | Layer B only | `ai-native-478811` | Firebase project ID |
| `API_BINARY` | optional | `api/mytube-api` | Path to pre-built Go binary |
| `DB_HOST` | Layer B only | `localhost` | PostgreSQL host |
| `DB_PORT` | Layer B only | `5432` | PostgreSQL port |
| `DB_USER` | Layer B only | `testuser` | PostgreSQL user |
| `DB_PASSWORD` | Layer B only | `testpass` | PostgreSQL password |
| `DB_NAME` | Layer B only | `mytube_test` | PostgreSQL database name |
| `GOOGLE_APPLICATION_CREDENTIALS` | Layer B only | `testing/fixtures/mock_service_account.json` | GCP credentials path |

## Expected output when passing

```
testing/tests/MYTUBE-190/test_mytube_190.py::TestSoftDeleteVideo_GoUnit::test_success_returns_204 PASSED
testing/tests/MYTUBE-190/test_mytube_190.py::TestSoftDeleteVideo_GoUnit::test_no_claims_returns_401 PASSED
testing/tests/MYTUBE-190/test_mytube_190.py::TestSoftDeleteVideo_GoUnit::test_invalid_video_id_returns_400 PASSED
testing/tests/MYTUBE-190/test_mytube_190.py::TestSoftDeleteVideo_GoUnit::test_video_not_found_or_not_owner_returns_404 PASSED
testing/tests/MYTUBE-190/test_mytube_190.py::TestSoftDeleteVideo_GoUnit::test_full_delete_suite_passes PASSED
testing/tests/MYTUBE-190/test_mytube_190.py::TestSoftDeleteVideo_Integration::test_delete_returns_204 PASSED
testing/tests/MYTUBE-190/test_mytube_190.py::TestSoftDeleteVideo_Integration::test_delete_response_body_is_empty PASSED
testing/tests/MYTUBE-190/test_mytube_190.py::TestSoftDeleteVideo_Integration::test_video_status_is_deleted_in_db PASSED
testing/tests/MYTUBE-190/test_mytube_190.py::TestSoftDeleteVideo_Integration::test_video_absent_from_me_videos PASSED
```

Layer B tests are skipped (not failed) when `FIREBASE_TEST_TOKEN` is absent.

## Notes

The test case description states the API should return 200 OK. The actual
implementation returns **204 No Content**, which is the correct RESTful
behaviour for a DELETE operation. The test asserts 204.
