# MYTUBE-300 — Authorized service account request: access to bucket objects granted

Verifies that an authorized service account can successfully access (download) objects
from the `mytube-raw-uploads` bucket while Public Access Prevention is enabled.

## What the test verifies

- **Step 1:** A test file is uploaded to `mytube-raw-uploads` using the configured service account credentials.
- **Step 2:** `GOOGLE_APPLICATION_CREDENTIALS` points to a valid service account JSON key file.
- **Step 3:** The same service account can download the uploaded object via the GCS API (HTTP 200 OK equivalent — no exception, correct bytes returned).

## Preconditions

The service account identified by `GOOGLE_APPLICATION_CREDENTIALS` must have **`roles/storage.objectViewer`** bound on the `mytube-raw-uploads` bucket:

```bash
gcloud storage buckets add-iam-policy-binding gs://mytube-raw-uploads \
  --member="serviceAccount:<SA_EMAIL>" \
  --role="roles/storage.objectViewer"
```

## Required environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | **yes** | — | Path to the service account JSON key file. The SA must have at least `storage.objects.create` (upload) and `storage.objects.get` (download) on `mytube-raw-uploads`. |
| `GCP_PROJECT_ID` | **yes** | — | GCP project ID (e.g. `ai-native-478811`). |
| `GCS_RAW_UPLOADS_BUCKET` | no | `mytube-raw-uploads` | Override the target bucket name. |

## How to run locally

```bash
cd /path/to/repo
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json
export GCP_PROJECT_ID=ai-native-478811

pytest testing/tests/MYTUBE-300/test_mytube_300.py -v
```

## Expected output (when preconditions are met)

```
testing/tests/MYTUBE-300/test_mytube_300.py::TestAuthorizedServiceAccountAccess::test_step1_upload_succeeds PASSED
testing/tests/MYTUBE-300/test_mytube_300.py::TestAuthorizedServiceAccountAccess::test_step2_authorized_sa_authenticated PASSED
testing/tests/MYTUBE-300/test_mytube_300.py::TestAuthorizedServiceAccountAccess::test_step3_download_succeeds_http200 PASSED
3 passed in ...s
```

When `GCP_PROJECT_ID` is absent or credentials cannot be loaded, the entire module is skipped.
