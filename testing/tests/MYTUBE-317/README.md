# MYTUBE-317 — Validate Eventarc trigger configuration

## What this test verifies

Confirms that the Eventarc trigger `mytube-gcs-finalize` is correctly wired to the
correct destination service (`mytube-transcoder-trigger`) and filtered for the
correct GCS bucket (`mytube-raw-uploads`) and event type
(`google.cloud.storage.object.v1.finalized`).

The test covers three steps:

1. **Trigger exists** — `gcloud eventarc triggers describe mytube-gcs-finalize` succeeds.
2. **Destination service** — `destination.cloudRunService.service` (or the legacy `cloudRun.service` path) resolves to `mytube-transcoder-trigger`.
3. **Event filters** — `eventFilters` include `bucket=mytube-raw-uploads` and `type=google.cloud.storage.object.v1.finalized`.

## Requirements

- `gcloud` CLI authenticated as a principal with `roles/eventarc.viewer` on project `ai-native-478811`
- Python 3.10+
- `pytest`

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `GCP_PROJECT_ID` | `ai-native-478811` | GCP project ID |
| `GCP_REGION` | `us-central1` | GCP region |
| `EVENTARC_TRIGGER_NAME` | `mytube-gcs-finalize` | Trigger name to inspect |
| `EXPECTED_DESTINATION_SERVICE` | `mytube-transcoder-trigger` | Expected Cloud Run service short name |
| `EXPECTED_BUCKET` | `mytube-raw-uploads` | Expected GCS bucket in event filters |
| `EXPECTED_EVENT_TYPE` | `google.cloud.storage.object.v1.finalized` | Expected event type in event filters |
| `GOOGLE_APPLICATION_CREDENTIALS` | *(must be set)* | Path to CI service account JSON key |

## Running locally

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
GCP_PROJECT_ID=ai-native-478811 GCP_REGION=us-central1 \
  pytest testing/tests/MYTUBE-317/test_mytube_317.py -v
```

## IAM requirements

The service account used for test execution must have at minimum:

```bash
gcloud projects add-iam-policy-binding ai-native-478811 \
  --member="serviceAccount:<SA_EMAIL>" \
  --role="roles/eventarc.viewer"
```
