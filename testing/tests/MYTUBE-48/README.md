# MYTUBE-48 — Provision raw uploads bucket (private access)

Verifies that the `mytube-raw-uploads` GCS bucket is correctly provisioned with
private access settings:

1. The bucket exists in the configured GCP project.
2. Public Access Prevention is set to `enforced` on the bucket.
3. An unauthenticated HTTP GET to the bucket's public URL returns HTTP 403 Forbidden.

## Prerequisites

- Python 3.10+
- `google-cloud-storage` and `pytest` packages

## Install dependencies

```bash
pip install google-cloud-storage pytest
```

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GCP_PROJECT_ID` | For steps 1 & 2 | — | GCP project containing the bucket |
| `GOOGLE_APPLICATION_CREDENTIALS` | For steps 1 & 2 | ADC | Path to service account JSON (needs `storage.buckets.get` + `storage.buckets.getIamPolicy`) |
| `GCS_RAW_UPLOADS_BUCKET` | No | `mytube-raw-uploads` | Override the bucket name |

Steps 1 and 2 are skipped automatically when `GCP_PROJECT_ID` / credentials are absent.
Step 3 (public URL probe) runs without any credentials.

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-48/test_mytube_48.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-48/test_mytube_48.py::TestRawUploadsBucketProvisioning::test_bucket_exists PASSED
testing/tests/MYTUBE-48/test_mytube_48.py::TestRawUploadsBucketProvisioning::test_public_access_prevention_enforced PASSED
testing/tests/MYTUBE-48/test_mytube_48.py::TestRawUploadsBucketProvisioning::test_unauthorized_access_returns_403 PASSED
================================================== 3 passed in X.XXs ==================================================
```
