# MYTUBE-336 — CI SA missing roles/eventarc.viewer

## Problem

The CI service account `ai-teammate-gcloud@<project>.iam.gserviceaccount.com`
was never granted `roles/eventarc.viewer` at the project level.  This caused
`PERMISSION_DENIED` whenever a pipeline step ran `gcloud projects get-iam-policy`
or `gcloud eventarc triggers describe`.

## Fix

Added the following block to `infra/setup.sh` (between section 4 and 5):

```bash
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${CI_SA_EMAIL}" \
  --role="roles/eventarc.viewer" \
  --condition=None
```

The live environment must also be updated manually:

```bash
gcloud projects add-iam-policy-binding ai-native-478811 \
  --member=serviceAccount:ai-teammate-gcloud@ai-native-478811.iam.gserviceaccount.com \
  --role=roles/eventarc.viewer \
  --condition=None
```

## Test

`test_mytube_336.py` is a **static analysis** test — no GCP credentials needed.

It verifies that all three required elements (`add-iam-policy-binding`,
`${CI_SA_EMAIL}`, `roles/eventarc.viewer`) appear together in a **single
contiguous command block** inside `infra/setup.sh`, guarding against
regressions where a future refactor removes the binding.
