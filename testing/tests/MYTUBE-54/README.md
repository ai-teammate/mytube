# MYTUBE-54: Delete object from raw bucket — transcoding job is not triggered by deletion

## Objective

Verify that the Eventarc trigger is specific to file creation (`object.v1.finalized`) and does not react to other storage events such as object deletion.

## ⚠️ Static Analysis Proxy Test — Not a Runtime Verification

This test suite performs **static analysis** of infrastructure source files only. It does **not**:
- Connect to GCP
- Delete any real GCS object
- Poll Cloud Run Job execution logs
- Verify live system behaviour

**Known limitation**: The `gcloud eventarc triggers create` command in `infra/setup.sh` is wrapped inside `echo "..."` operator instructions (lines 166–173) and is **not executed** by the script. The tests in `TestEventarcTriggerConfiguration` verify the *intended* provisioning instructions, not whether the Eventarc trigger was actually deployed or deployed with the correct configuration.

For full runtime confidence in the ticket scenario (delete object → no job execution), a live integration test should additionally run:
```
gcloud eventarc triggers describe mytube-gcs-finalize
```
and assert the returned `event-filter` fields match the expected values.

## Test Type

`type: infrastructure` / `platform: static` — local file inspection, no GCP connectivity required.

## Approach

Since the Eventarc trigger is a GCP infrastructure component that filters events before they reach the trigger service, this suite tests correctness at two complementary layers:

**1. Infrastructure Configuration (`infra/setup.sh`)**
- Confirms the `gcloud eventarc triggers create` operator instruction uses `--event-filters=type=google.cloud.storage.object.v1.finalized`
- Confirms `object.v1.deleted` and `object.v1.archived` event types are NOT present
- Confirms the trigger is scoped to `mytube-raw-uploads` bucket only
- Explicitly verifies the command is inside `echo` statements (documents the static-analysis scope)

**2. Trigger Handler Behaviour (`infra/transcoder-trigger/internal/handler/trigger.go`)**
- Confirms the handler calls `event.Parse` to validate the incoming payload
- Confirms the handler returns `StatusBadRequest` on parse failure (rejecting invalid/deletion-like payloads)
- Confirms `executor.Execute` is only called after both `event.Parse` and `obj.VideoID()` succeed
- Confirms the handler contains no logic that references deletion or archival event types

## Test Classes

| Class | Tests |
|-------|-------|
| `TestEventarcTriggerConfiguration` | 7 tests — verifies `setup.sh` Eventarc provisioning instructions |
| `TestTriggerHandlerRejectsDeletionLikePayloads` | 6 tests — verifies handler rejects invalid payloads |

## Dependencies

None — no GCP credentials, no network access, no external services required.

## Running

```bash
python3 -m pytest testing/tests/MYTUBE-54/test_mytube_54.py -v
```

Run from the repository root.

## Expected Output (passing)

```
testing/tests/MYTUBE-54/test_mytube_54.py::TestEventarcTriggerConfiguration::test_setup_sh_exists PASSED
testing/tests/MYTUBE-54/test_mytube_54.py::TestEventarcTriggerConfiguration::test_gcloud_eventarc_command_is_in_echo_operator_instructions PASSED
testing/tests/MYTUBE-54/test_mytube_54.py::TestEventarcTriggerConfiguration::test_eventarc_trigger_uses_finalized_event_type PASSED
testing/tests/MYTUBE-54/test_mytube_54.py::TestEventarcTriggerConfiguration::test_eventarc_trigger_does_not_register_deleted_event_type PASSED
testing/tests/MYTUBE-54/test_mytube_54.py::TestEventarcTriggerConfiguration::test_eventarc_trigger_does_not_register_archived_event_type PASSED
testing/tests/MYTUBE-54/test_mytube_54.py::TestEventarcTriggerConfiguration::test_eventarc_trigger_is_scoped_to_raw_uploads_bucket PASSED
testing/tests/MYTUBE-54/test_mytube_54.py::TestTriggerHandlerRejectsDeletionLikePayloads::test_trigger_go_exists PASSED
testing/tests/MYTUBE-54/test_mytube_54.py::TestTriggerHandlerRejectsDeletionLikePayloads::test_handler_rejects_missing_bucket_field PASSED
testing/tests/MYTUBE-54/test_mytube_54.py::TestTriggerHandlerRejectsDeletionLikePayloads::test_handler_returns_bad_request_on_parse_error PASSED
testing/tests/MYTUBE-54/test_mytube_54.py::TestTriggerHandlerRejectsDeletionLikePayloads::test_handler_does_not_execute_job_before_successful_parse PASSED
testing/tests/MYTUBE-54/test_mytube_54.py::TestTriggerHandlerRejectsDeletionLikePayloads::test_handler_extracts_video_id_before_executing_job PASSED
testing/tests/MYTUBE-54/test_mytube_54.py::TestTriggerHandlerRejectsDeletionLikePayloads::test_handler_only_accepts_finalized_event_structure PASSED

13 passed in Xs
```
