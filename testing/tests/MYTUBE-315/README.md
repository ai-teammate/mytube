# MYTUBE-315 — Verify Eventarc API status: eventarc.googleapis.com is enabled

## What this test verifies

The `eventarc.googleapis.com` API is enabled for the GCP project `ai-native-478811`,
which is required for the event-driven transcoding pipeline to function.

## Test Steps

1. Execute `gcloud services list --enabled --filter="name:eventarc.googleapis.com" --project=<project>`.
2. Assert that `eventarc.googleapis.com` appears in the output.

## Requirements

- `gcloud` CLI authenticated with sufficient permissions (or `GOOGLE_APPLICATION_CREDENTIALS` set).
- `GCP_PROJECT_ID` environment variable (default: `ai-native-478811`).

## Running

```bash
pytest testing/tests/MYTUBE-315/test_mytube_315.py -v
```
