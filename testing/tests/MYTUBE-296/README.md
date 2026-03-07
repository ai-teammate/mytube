# MYTUBE-296 — Infrastructure setup script grants object creator role

## Overview
Static file-content verification test for `infra/setup.sh`.

Ensures the script grants `roles/storage.objectCreator` to the CI service account
(`ai-teammate-gcloud`) on the `gs://mytube-raw-uploads` bucket, preventing regression
of the IAM permission issue.

## Test type
Static (no GCP credentials required)

## Steps verified
1. `infra/setup.sh` exists in the repository.
2. `RAW_BUCKET`, `CI_SA`, and `CI_SA_EMAIL` variables are correctly defined.
3. A `gcloud storage buckets add-iam-policy-binding` call grants
   `roles/storage.objectCreator` to `CI_SA_EMAIL` on `RAW_BUCKET`.

## How to run
```bash
pytest testing/tests/MYTUBE-296/
```
