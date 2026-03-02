# MYTUBE-106 — CDN_BASE_URL absence: CDN test is skipped with explanatory message

## What this test verifies

When `CDN_BASE_URL` is not set in the environment, `test_object_served_via_cdn_url` in
`testing/tests/MYTUBE-49/test_mytube_49.py` must be reported as **SKIPPED** (not FAILED
or ERROR), and the skip message must clearly instruct the user to set `CDN_BASE_URL`.

### Test layers

1. **Unit tests** (`TestCDNBaseURLAbsence`, 4 tests) — no real GCP credentials required:
   - `GCSConfig.cdn_base_url` is empty string when `CDN_BASE_URL` is unset.
   - `cdn_base_url` evaluates as falsy, confirming the skip guard fires.
   - The real `test_object_served_via_cdn_url` (imported from `test_mytube_49.py`)
     raises `pytest.skip.Exception` containing `CDN_BASE_URL` in the message.
   - The real skip message is descriptive and guides the user to configure the variable.

2. **Integration test** (`TestMytube49SubprocessSkipBehaviour`, 1 test):
   - Runs the MYTUBE-49 test file as a real subprocess with `CDN_BASE_URL` removed.
   - Asserts pytest output contains `SKIPPED` and `CDN_BASE_URL`, with no `FAILED` or `ERROR`.

## Requirements

- Python 3.10+
- `pytest`
- `GOOGLE_APPLICATION_CREDENTIALS` pointing to a valid (or mock) service account for the
  subprocess integration test (unit tests do not require GCP credentials)

## Environment variables

| Variable                         | Required for          | Description                                      |
|----------------------------------|-----------------------|--------------------------------------------------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Integration test only | Path to service account key or mock fixture      |
| `CDN_BASE_URL`                   | Must be **unset**     | The test verifies behaviour when this is absent  |

## Install dependencies

```bash
pip install pytest
```

## Run the test

```bash
pytest testing/tests/MYTUBE-106/test_mytube_106.py -v
```

To also satisfy the integration test's credential requirement using the mock fixture:

```bash
GOOGLE_APPLICATION_CREDENTIALS=testing/fixtures/mock_service_account.json \
  pytest testing/tests/MYTUBE-106/test_mytube_106.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-106/test_mytube_106.py::TestCDNBaseURLAbsence::test_gcs_config_cdn_base_url_empty_when_env_var_unset PASSED
testing/tests/MYTUBE-106/test_mytube_106.py::TestCDNBaseURLAbsence::test_gcs_config_cdn_base_url_falsy_triggers_skip_guard PASSED
testing/tests/MYTUBE-106/test_mytube_106.py::TestCDNBaseURLAbsence::test_skip_guard_raises_skipped_with_descriptive_message PASSED
testing/tests/MYTUBE-106/test_mytube_106.py::TestCDNBaseURLAbsence::test_skip_message_is_descriptive PASSED
testing/tests/MYTUBE-106/test_mytube_106.py::TestMytube49SubprocessSkipBehaviour::test_cdn_test_is_skipped_in_subprocess_run PASSED
5 passed
```
