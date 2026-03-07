# MYTUBE-301 — Update bucket IAM policy with public member: rejected by PAP

## What this test verifies

Ensures that Public Access Prevention (PAP) actively blocks any attempt to grant
`allUsers` public IAM permissions on the `mytube-raw-uploads` GCS bucket.

## Prerequisites

| Requirement | Details |
|---|---|
| `gcloud` CLI | Must be installed and in `$PATH` |
| GCP credentials | ADC or `GOOGLE_APPLICATION_CREDENTIALS` with `storage.buckets.setIamPolicy` |
| `GCP_PROJECT_ID` | Set to `ai-native-478811` (or override) |

## Install dependencies

```bash
pip install pytest
# google-cloud-storage is used by GcpIamService internally (already in requirements.txt)
pip install -r testing/requirements.txt
```

## Run the test

From the repository root:

```bash
GCP_PROJECT_ID=ai-native-478811 \
  pytest testing/tests/MYTUBE-301/test_mytube_301.py -v
```

## Expected output when passing

```
testing/tests/MYTUBE-301/test_mytube_301.py::TestPublicAccessPreventionBlocksIAMBinding::test_add_public_member_is_rejected PASSED
testing/tests/MYTUBE-301/test_mytube_301.py::TestPublicAccessPreventionBlocksIAMBinding::test_allUsers_not_in_existing_bindings PASSED
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GCP_PROJECT_ID` | Yes | _(none)_ | GCP project hosting the bucket |
| `GOOGLE_APPLICATION_CREDENTIALS` | Yes (in CI) | ADC | Path to service account key JSON |
