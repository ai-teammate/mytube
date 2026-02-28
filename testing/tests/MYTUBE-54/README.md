# MYTUBE-54: Delete object from raw bucket — transcoding job is not triggered by deletion

## Objective

Verify that the Eventarc trigger is specific to file creation (`object.v1.finalized`) and does not react to other storage events such as object deletion.

## Test Type

Infrastructure configuration + trigger handler behaviour (static analysis)

## Approach

Since the Eventarc trigger is a GCP infrastructure component that filters events before they reach the trigger service, this suite tests correctness at two complementary layers:

**1. Infrastructure Configuration (`infra/setup.sh`)**
- Confirms the Eventarc trigger is provisioned with `--event-filters=type=google.cloud.storage.object.v1.finalized`
- Confirms `object.v1.deleted` and `object.v1.archived` event types are NOT registered
- Confirms the trigger is scoped to `mytube-raw-uploads` bucket only

**2. Trigger Handler Behaviour (`infra/transcoder-trigger/internal/handler/trigger.go`)**
- Confirms the handler calls `event.Parse` to validate the incoming payload
- Confirms the handler returns `StatusBadRequest` on parse failure (rejecting invalid/deletion-like payloads)
- Confirms `executor.Execute` is only called after both `event.Parse` and `obj.VideoID()` succeed
- Confirms the handler contains no logic that references deletion or archival event types

## Test Classes

| Class | Tests |
|-------|-------|
| `TestEventarcTriggerConfiguration` | 6 tests — verifies `setup.sh` Eventarc provisioning |
| `TestTriggerHandlerRejectsDeletionLikePayloads` | 6 tests — verifies handler rejects invalid payloads |

## Running

```bash
python3 -m pytest testing/tests/MYTUBE-54/test_mytube_54.py -v
```

## Result

**PASSED** — 12/12 tests pass
