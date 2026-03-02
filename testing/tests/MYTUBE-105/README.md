# MYTUBE-105 — Execute GCS integration tests on CI: tests pass without DefaultCredentialsError

## What this test verifies

1. `GOOGLE_APPLICATION_CREDENTIALS` is set and points to an existing service account JSON file.
2. The JSON file is valid and has `type: service_account`.
3. `storage.Client()` initializes without raising `DefaultCredentialsError`.
4. `GCSService` can be fully constructed using the CI credentials (mirrors the `gcs_service` fixture chain in `test_mytube_49.py`).

## Requirements

- Python 3.10+
- `google-cloud-storage`, `httpx`, and `pytest`
- `GOOGLE_APPLICATION_CREDENTIALS` set to a valid service account JSON with at minimum Storage Object Viewer and Storage IAM permissions

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | **Yes** | Absolute path to a GCP service account JSON key file |

## Install dependencies

```bash
pip install google-cloud-storage httpx pytest
```

## Run the test

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
pytest testing/tests/MYTUBE-105/test_mytube_105.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-105/test_mytube_105.py::TestGCSCredentialsConfiguredOnCI::test_google_application_credentials_env_var_is_set PASSED
testing/tests/MYTUBE-105/test_mytube_105.py::TestGCSCredentialsConfiguredOnCI::test_google_application_credentials_file_exists PASSED
testing/tests/MYTUBE-105/test_mytube_105.py::TestGCSCredentialsConfiguredOnCI::test_google_application_credentials_file_is_valid_json PASSED
testing/tests/MYTUBE-105/test_mytube_105.py::TestGCSCredentialsConfiguredOnCI::test_storage_client_initializes_without_default_credentials_error PASSED
testing/tests/MYTUBE-105/test_mytube_105.py::TestGCSCredentialsConfiguredOnCI::test_gcs_service_fixture_constructed_with_ci_credentials PASSED
5 passed
```
