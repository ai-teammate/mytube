# MYTUBE-307 — CI SA missing roles/storage.objectViewer on mytube-raw-uploads

## What this test verifies

Ensures that both provisioning scripts grant `roles/storage.objectViewer` to
the CI service account (`ai-teammate-gcloud`) on `gs://mytube-raw-uploads`,
so that `storage.objects.get` operations (`blob.exists()` /
`download_as_bytes()`) succeed instead of returning HTTP 403.

## Tests

| Test class | Type | Description |
|---|---|---|
| `TestSetupShGrantsCiSaObjectViewer` | Static analysis | `infra/setup.sh` contains `objectViewer` grant for CI SA |
| `TestProvisionWorkflowGrantsCiSaObjectViewer` | Static analysis | `provision-gcs-buckets.yml` contains `objectViewer` grant for CI SA |
| `TestCiSaObjectViewerLiveIam` | GCP integration | Live IAM policy has the binding (skipped if `GCP_PROJECT_ID` not set) |

## Prerequisites

| Requirement | Details |
|---|---|
| `GCP_PROJECT_ID` | Required only for the live IAM test (auto-skipped when absent) |
| `gcloud` CLI | Required only for the live IAM test |
| GCP credentials | ADC or `GOOGLE_APPLICATION_CREDENTIALS` with `storage.buckets.getIamPolicy` |

## Install dependencies

```bash
pip install pytest
```

## Run static-analysis tests only (no GCP needed)

```bash
pytest testing/tests/MYTUBE-307/ -k "not LiveIam" -v
```

## Run all tests (including live GCP check)

```bash
export GCP_PROJECT_ID=ai-native-478811
pytest testing/tests/MYTUBE-307/ -v
```
