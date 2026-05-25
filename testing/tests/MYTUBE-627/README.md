# MYTUBE-627 — Upload oversized file: API returns 413

Verifies that `POST /api/me/avatar` returns HTTP 413 Payload Too Large when
the uploaded image file exceeds the 5 MB limit.

## Dependencies

```
pip install pytest
```

No additional packages are needed — the test uses Python's stdlib `urllib`.

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `FIREBASE_TEST_TOKEN` | ✅ Yes | — | Firebase ID token for the CI test user |
| `API_BASE_URL` | No | `http://localhost:8080` | Deployed API base URL |

## Run

```bash
cd /path/to/repo
pytest testing/tests/MYTUBE-627/test_mytube_627.py -v
```

## Expected output (pass)

```
PASSED testing/tests/MYTUBE-627/test_mytube_627.py::TestAvatarOversizedUpload::test_status_is_413
PASSED testing/tests/MYTUBE-627/test_mytube_627.py::TestAvatarOversizedUpload::test_error_body_mentions_too_large
```

## Notes

The test generates a 5 242 881-byte PNG (valid magic header + null padding)
in memory and sends it as `multipart/form-data` to `/api/me/avatar`.  No
temporary files are written to disk.

The test is skipped automatically when `FIREBASE_TEST_TOKEN` is not set.
