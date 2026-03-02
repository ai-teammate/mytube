# MYTUBE-116: Verify GCS bucket existence check — test fails if bucket is missing

## Objective

Ensures the test suite correctly identifies and reports when the target GCS bucket
`mytube-hls-output` has not been provisioned in the environment.

## Dependencies

- `google-cloud-storage` Python package
- `pytest`

## Install dependencies

```bash
pip install google-cloud-storage pytest
```

## How to run

From the repository root:

```bash
pytest testing/tests/MYTUBE-116/test_mytube_116.py -v
```

## Environment variables

No real GCP credentials are required — the tests use a mock GCS client that
simulates a missing bucket via `google.api_core.exceptions.NotFound`.

Optional override:

| Variable     | Default              | Description                     |
|--------------|----------------------|---------------------------------|
| `HLS_BUCKET` | `mytube-hls-output`  | Name of the HLS output bucket   |

## Expected output when tests pass

```
PASSED testing/tests/MYTUBE-116/test_mytube_116.py::TestBucketExistenceCheck::test_bucket_exists_returns_false_when_bucket_missing
PASSED testing/tests/MYTUBE-116/test_mytube_116.py::TestBucketExistenceCheck::test_hls_bucket_exists_assertion_fails_when_bucket_missing
PASSED testing/tests/MYTUBE-116/test_mytube_116.py::TestBucketExistenceCheck::test_not_found_exception_is_raised_by_storage_client
```

## Test structure

| Test | What it verifies |
|------|-----------------|
| `test_bucket_exists_returns_false_when_bucket_missing` | `GCSService.bucket_exists()` returns `False` (not raises) when `NotFound` |
| `test_hls_bucket_exists_assertion_fails_when_bucket_missing` | The assertion from MYTUBE-49 raises `AssertionError` with bucket name in message |
| `test_not_found_exception_is_raised_by_storage_client` | The underlying SDK raises `google.api_core.exceptions.NotFound` (HTTP 404) |
