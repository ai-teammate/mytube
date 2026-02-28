# MYTUBE-51 — Cloud Run IAM Permissions Test

Verifies that the Service Account used by the `mytube-transcoder` Cloud Run Job
has the minimal required IAM permissions on GCS buckets:

- `roles/storage.objectViewer` on `gs://mytube-raw-uploads`
- `roles/storage.objectCreator` on `gs://mytube-hls-output`

Also verifies the SA has no overly broad administrative roles on either bucket.

## Prerequisites

- Python 3.10+
- `pytest` package
- `gcloud` CLI installed and authenticated with a principal that can:
  - Describe Cloud Run Jobs (`run.jobs.get`)
  - Read IAM policies on GCS buckets (`storage.buckets.getIamPolicy`)

## Install dependencies

```bash
pip install pytest
```

## Environment variables

| Variable        | Required | Default       | Description                   |
|-----------------|----------|---------------|-------------------------------|
| `GCP_PROJECT_ID`| Yes      | —             | GCP project ID                |
| `GCP_REGION`    | No       | `us-central1` | Region where Cloud Run Job lives |

## Run the test

From the repository root:

```bash
GCP_PROJECT_ID=your-project-id pytest testing/tests/MYTUBE-51/test_mytube_51.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-51/test_mytube_51.py::TestCloudRunJobServiceAccount::test_service_account_is_mytube_transcoder PASSED
testing/tests/MYTUBE-51/test_mytube_51.py::TestRawBucketPermissions::test_sa_has_object_viewer_on_raw_bucket PASSED
testing/tests/MYTUBE-51/test_mytube_51.py::TestRawBucketPermissions::test_sa_has_no_overly_broad_roles_on_raw_bucket PASSED
testing/tests/MYTUBE-51/test_mytube_51.py::TestHlsBucketPermissions::test_sa_has_object_creator_on_hls_bucket PASSED
testing/tests/MYTUBE-51/test_mytube_51.py::TestHlsBucketPermissions::test_sa_has_no_overly_broad_roles_on_hls_bucket PASSED
================================================== 5 passed in X.XXs ==================================================
```

## What the test checks

1. **Service Account identity** — The `mytube-transcoder` Cloud Run Job uses the
   `mytube-transcoder@<project>.iam.gserviceaccount.com` service account.
2. **Read permission on raw bucket** — SA has `roles/storage.objectViewer` on
   `gs://mytube-raw-uploads`, enabling it to read uploaded video files.
3. **No broad roles on raw bucket** — SA does not have `roles/storage.admin`,
   `roles/storage.objectAdmin`, or other overly permissive roles on the raw bucket.
4. **Write permission on HLS bucket** — SA has `roles/storage.objectCreator` on
   `gs://mytube-hls-output`, enabling it to write transcoded HLS output.
5. **No broad roles on HLS bucket** — SA does not have administrative roles on the
   HLS output bucket beyond what is required.
