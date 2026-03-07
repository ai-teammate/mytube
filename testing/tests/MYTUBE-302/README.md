# MYTUBE-302 — Access to bucket via Signed URL — access granted despite PAP

## What this test verifies

Confirms that GCS Signed URLs successfully bypass Public Access Prevention (PAP)
as designed. PAP blocks anonymous/ACL-based public access but must **not** block
time-limited signed-URL access. The test generates a V4 signed URL, performs an
unauthenticated HTTP GET, and asserts HTTP 200 OK and correct response body.

## Prerequisites

| Requirement | Details |
|---|---|
| Service account key | JSON key file with `storage.objects.get` on `mytube-raw-uploads` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to the service account key (see below) |
| `GCP_PROJECT_ID` | Set to `ai-native-478811` (or override) |
| Python packages | `google-cloud-storage`, `google-auth`, `requests` (see `requirements.txt`) |

## Install dependencies

```bash
pip install -r testing/requirements.txt
```

## Run the test

From the repository root:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json \
  GCS_RAW_UPLOADS_BUCKET=mytube-raw-uploads \
  GCP_PROJECT_ID=ai-native-478811 \
  pytest testing/tests/MYTUBE-302/test_mytube_302.py -v
```

## Expected output when passing

```
testing/tests/MYTUBE-302/test_mytube_302.py::TestSignedUrlBypassesPAP::test_signed_url_returns_200 PASSED
testing/tests/MYTUBE-302/test_mytube_302.py::TestSignedUrlBypassesPAP::test_signed_url_response_body_contains_probe_content PASSED
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Yes | `gha-creds-c230da37cfc4bcbe.json` | Path to SA key JSON with `storage.objects.get` |
| `GCS_RAW_UPLOADS_BUCKET` | No | `mytube-raw-uploads` | GCS bucket name |
| `GCP_PROJECT_ID` | No | `ai-native-478811` | GCP project ID |

## Notes

The test self-manages its test object: it uploads a unique probe file before the
test run and deletes it on teardown. No pre-existing objects are required in the bucket.

If the test fails with HTTP 403, the most likely cause is that the signing service
account is missing `roles/storage.objectViewer` (or `storage.objects.get`) on the bucket.
