# MYTUBE-310 — MP4 upload to raw bucket: transcoding Cloud Run job triggered automatically

Verifies the end-to-end Eventarc pipeline: uploading an MP4 file to
`gs://mytube-raw-uploads` must automatically trigger a new execution of the
`mytube-transcoder` Cloud Run Job via the `mytube-transcoder-trigger` Cloud Run
Service and the `mytube-gcs-finalize` Eventarc trigger.

## Dependencies

```bash
pip install pytest google-auth google-cloud-storage
# gcloud CLI must be installed and authenticated (or GOOGLE_APPLICATION_CREDENTIALS set)
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_APPLICATION_CREDENTIALS` | — | **Required.** Path to CI service account key JSON with `roles/storage.objectCreator` on `gs://mytube-raw-uploads` |
| `GCP_PROJECT_ID` | `ai-native-478811` | GCP project ID |
| `GCP_REGION` | `us-central1` | GCP region |
| `GCS_RAW_UPLOADS_BUCKET` | `mytube-raw-uploads` | Target raw-uploads bucket |
| `GCP_TRANSCODER_JOB` | `mytube-transcoder` | Cloud Run Job name to watch for new executions |
| `CLOUD_RUN_TRIGGER_WAIT_SECONDS` | `120` | Seconds to poll for a new Cloud Run Job execution |

## Infrastructure preconditions

The following GCP infrastructure must be in place before this test can pass:

1. **Eventarc API enabled**: `gcloud services enable eventarc.googleapis.com --project=ai-native-478811`
2. **`mytube-transcoder-trigger` Cloud Run Service deployed** (see `infra/transcoder-trigger/`) — this service receives GCS finalize events from Eventarc and triggers the `mytube-transcoder` Cloud Run Job.
3. **`mytube-gcs-finalize` Eventarc trigger configured** to route `google.cloud.storage.object.v1.finalized` events from `mytube-raw-uploads` to `mytube-transcoder-trigger`.

## Expected failure scenarios

| Scenario | Symptom |
|----------|---------|
| Eventarc API not enabled | `gcloud eventarc triggers list` fails; no trigger fires |
| `mytube-transcoder-trigger` service not deployed | Eventarc has no destination; events are dropped |
| Eventarc trigger not created | GCS events never leave the bucket |
| IAM role `roles/storage.objectCreator` not granted | Upload fails; no GCS event fires |
| Eventarc delivery delayed > `CLOUD_RUN_TRIGGER_WAIT_SECONDS` | Test times out (increase `CLOUD_RUN_TRIGGER_WAIT_SECONDS`) |

## Running the test

From the repository root:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json \
  GCP_PROJECT_ID=ai-native-478811 \
  pytest testing/tests/MYTUBE-310/test_mytube_310.py -v
```

## Expected output (passing)

```
PASSED TestMP4UploadTriggersCloudRunJob::test_ci_sa_has_object_creator_role
PASSED TestMP4UploadTriggersCloudRunJob::test_upload_mp4_triggers_cloud_run_execution
```

## Architecture

```
test_mytube_310.py
  └── GcpIamService          (testing/components/gcp/)      — IAM policy checks
  └── GCSBucketService       (testing/components/services/) — upload & delete objects
  └── EventarcService        (testing/components/services/) — list Cloud Run executions
  └── poll_until             (testing/core/utils/polling)   — polling loop utility
```
