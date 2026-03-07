# MYTUBE-320 — Infrastructure setup script IAM binding

**Type:** Static file analysis
**File under test:** `infra/setup.sh`

## What this test verifies

Verifies that `infra/setup.sh` contains a `gcloud projects add-iam-policy-binding`
command that grants `roles/eventarc.viewer` to the CI service account
`ai-teammate-gcloud@<project>.iam.gserviceaccount.com`.

## How to run

```bash
cd testing
pytest tests/MYTUBE-320/
```

## Expected result

PASS once `infra/setup.sh` is updated to include the required IAM binding:

```bash
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${CI_SA_EMAIL}" \
  --role="roles/eventarc.viewer"
```

FAIL if the binding is missing — this means the fix has not yet been applied to the setup script.
