# MYTUBE-50 — Configure Eventarc trigger: file upload to raw bucket invokes Cloud Run job

## What this test verifies

The Eventarc trigger `mytube-gcs-finalize` is correctly configured to invoke the `mytube-transcoder` Cloud Run Job when a file is uploaded to the `mytube-raw-uploads` GCS bucket.

The test is split into two parts:

**Part A — Local contract tests (always run, no GCP required)**
Runs the Go unit-test suite for `infra/transcoder-trigger` via `subprocess`:
- The trigger handler binary builds cleanly
- The handler parses `google.cloud.storage.object.v1.finalized` Eventarc event payloads
- The handler extracts `VIDEO_ID` from the object name (`raw/<uuid>.mp4`)
- The handler calls the Cloud Run Jobs executor with correct parameters
- The handler returns HTTP 204 on success and 400/500 on errors

**Part B — Infrastructure smoke tests (require live GCP credentials)**
Queries GCP via `gcloud` CLI to verify:
1. The `mytube-transcoder` Cloud Run Job exists in the project
2. The `mytube-gcs-finalize` Eventarc trigger exists
3. The trigger listens for `google.cloud.storage.object.v1.finalized` events
4. The trigger filters on the `mytube-raw-uploads` bucket
5. The trigger routes to the `mytube-transcoder-trigger` Cloud Run Service

## Requirements

- Python 3.10+
- Go 1.21+ (for Part A)
- `pytest`
- `gcloud` CLI with `Application Default Credentials` (for Part B only)

## Environment variables

| Variable         | Required | Description                                    |
|------------------|----------|------------------------------------------------|
| `GCP_PROJECT_ID` | Part B   | GCP project ID — omit to skip infrastructure tests |
| `GCP_REGION`     | Part B   | GCP region (e.g. `us-central1`)                |

## Install dependencies

```bash
pip install pytest
```

## Run the test

```bash
pytest testing/tests/MYTUBE-50/test_mytube_50.py -v
```

To also run Part B (infrastructure tests), set GCP credentials:

```bash
export GCP_PROJECT_ID=my-project
export GCP_REGION=us-central1
gcloud auth application-default login
pytest testing/tests/MYTUBE-50/test_mytube_50.py -v
```

## Expected output (passing — Part A only, no GCP credentials)

```
testing/tests/MYTUBE-50/test_mytube_50.py::TestTriggerServiceContract::test_trigger_service_builds PASSED
testing/tests/MYTUBE-50/test_mytube_50.py::TestTriggerServiceContract::test_trigger_service_unit_tests_pass PASSED
testing/tests/MYTUBE-50/test_mytube_50.py::TestTriggerServiceContract::test_handler_returns_204_for_valid_gcs_event PASSED
testing/tests/MYTUBE-50/test_mytube_50.py::TestTriggerServiceContract::test_handler_passes_correct_video_id_to_executor PASSED
testing/tests/MYTUBE-50/test_mytube_50.py::TestTriggerServiceContract::test_handler_returns_400_for_invalid_payload PASSED
5 passed, 5 skipped
```

## Expected output (passing — with GCP credentials)

```
testing/tests/MYTUBE-50/test_mytube_50.py::TestTriggerServiceContract::test_trigger_service_builds PASSED
testing/tests/MYTUBE-50/test_mytube_50.py::TestTriggerServiceContract::test_trigger_service_unit_tests_pass PASSED
testing/tests/MYTUBE-50/test_mytube_50.py::TestTriggerServiceContract::test_handler_returns_204_for_valid_gcs_event PASSED
testing/tests/MYTUBE-50/test_mytube_50.py::TestTriggerServiceContract::test_handler_passes_correct_video_id_to_executor PASSED
testing/tests/MYTUBE-50/test_mytube_50.py::TestTriggerServiceContract::test_handler_returns_400_for_invalid_payload PASSED
testing/tests/MYTUBE-50/test_mytube_50.py::TestEventarcInfrastructure::test_cloud_run_job_exists PASSED
testing/tests/MYTUBE-50/test_mytube_50.py::TestEventarcInfrastructure::test_eventarc_trigger_exists PASSED
testing/tests/MYTUBE-50/test_mytube_50.py::TestEventarcInfrastructure::test_trigger_listens_for_gcs_finalize_event PASSED
testing/tests/MYTUBE-50/test_mytube_50.py::TestEventarcInfrastructure::test_trigger_filters_on_raw_uploads_bucket PASSED
testing/tests/MYTUBE-50/test_mytube_50.py::TestEventarcInfrastructure::test_trigger_routes_to_correct_cloud_run_service PASSED
10 passed
```
