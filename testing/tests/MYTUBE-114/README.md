# MYTUBE-114 — GCS tests with insufficient IAM permissions: 403 Forbidden error handled

## Objective

Verify that when a service account lacks the required GCS IAM roles
(`storage.buckets.getIamPolicy` or `storage.objects.create`), the test suite
surfaces a `google.api_core.exceptions.Forbidden` (403) error rather than a
`DefaultCredentialsError`, correctly distinguishing authorization failure from
authentication failure.

## Dependencies

- Python 3.10+
- `google-cloud-storage`
- `google-api-core`
- `pytest`
- `httpx`

## Install dependencies

```bash
pip install google-cloud-storage google-api-core pytest httpx
```

## How to run

```bash
pytest testing/tests/MYTUBE-114/test_mytube_114.py -v
```

## Environment variables

No real GCP credentials are required for this test. The test uses a mock GCS
client that simulates 403 Forbidden responses, so it runs entirely offline.

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_APPLICATION_CREDENTIALS` | No | Not required; mock client is injected |

## Expected output when the test passes

```
testing/tests/MYTUBE-114/test_mytube_114.py::TestGCSForbiddenErrorHandling::test_bucket_exists_raises_forbidden_not_credentials_error PASSED
testing/tests/MYTUBE-114/test_mytube_114.py::TestGCSForbiddenErrorHandling::test_has_public_read_iam_raises_forbidden_not_credentials_error PASSED
testing/tests/MYTUBE-114/test_mytube_114.py::TestGCSForbiddenErrorHandling::test_upload_test_object_raises_forbidden_not_credentials_error PASSED
testing/tests/MYTUBE-114/test_mytube_114.py::TestGCSForbiddenErrorHandling::test_forbidden_error_is_http_403 PASSED

4 passed in ...s
```

## What is tested

1. `bucket_exists()` propagates `Forbidden` (not `DefaultCredentialsError`) when the SA lacks `storage.buckets.get`.
2. `has_public_read_iam()` propagates `Forbidden` when the SA lacks `storage.buckets.getIamPolicy`.
3. `upload_test_object()` propagates `Forbidden` when the SA lacks `storage.objects.create`.
4. The raised exception is an instance of `google.api_core.exceptions.Forbidden` (HTTP 403).
