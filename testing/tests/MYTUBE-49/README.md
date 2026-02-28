# MYTUBE-49 — Provision HLS output bucket with CDN: bucket is public and served via Cloud CDN

## What this test verifies

1. The `mytube-hls-output` GCS bucket exists.
2. The bucket grants `allUsers` the `roles/storage.objectViewer` IAM role, enabling public read access for CDN delivery.
3. A test file uploaded to the bucket is accessible via the public GCS URL (CDN endpoint), confirming correct HLS delivery configuration.

## Requirements

- Python 3.10+
- GCP credentials with at least `storage.buckets.getIamPolicy` and `storage.objects.create`/`storage.objects.delete` permissions on the HLS bucket
- `google-cloud-storage`, `httpx`, and `pytest`

## Environment variables

| Variable              | Default                              | Description                          |
|-----------------------|--------------------------------------|--------------------------------------|
| `HLS_BUCKET`          | `mytube-hls-output`                  | HLS output GCS bucket name           |
| `RAW_BUCKET`          | `mytube-raw-uploads`                 | Raw uploads GCS bucket name          |
| `GCS_PUBLIC_BASE_URL` | `https://storage.googleapis.com`     | Public GCS base URL (CDN endpoint)   |
| `GOOGLE_APPLICATION_CREDENTIALS` | _(ADC)_                | Path to service account key (if not using ADC) |

## Install dependencies

```bash
pip install google-cloud-storage httpx pytest
```

## Run the test

```bash
pytest testing/tests/MYTUBE-49/test_mytube_49.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-49/test_mytube_49.py::TestHLSBucketProvisionedWithPublicAccess::test_hls_bucket_exists PASSED
testing/tests/MYTUBE-49/test_mytube_49.py::TestHLSBucketProvisionedWithPublicAccess::test_hls_bucket_has_public_read_iam PASSED
testing/tests/MYTUBE-49/test_mytube_49.py::TestHLSBucketProvisionedWithPublicAccess::test_object_served_via_public_url PASSED
3 passed
```
