# MYTUBE-309 — CI service account IAM policy audit: both objectCreator and objectViewer roles present on raw bucket

Verifies that the CI service account
`serviceAccount:ai-teammate-gcloud@ai-native-478811.iam.gserviceaccount.com`
holds both `roles/storage.objectCreator` and `roles/storage.objectViewer` on
`gs://mytube-raw-uploads`, ensuring it can upload test fixtures (MYTUBE-79) and
that the transcoder can read them (MYTUBE-307).

## Dependencies

```bash
pip install pytest
# gcloud CLI must be installed and authenticated
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GCP_PROJECT_ID` | `ai-native-478811` | GCP project ID |
| `GCP_REGION` | `us-central1` | GCP region |
| `GOOGLE_APPLICATION_CREDENTIALS` | — | Path to service account key JSON (or use ADC) |

## Running the test

From the repository root:

```bash
cd /path/to/mytube
GCP_PROJECT_ID=ai-native-478811 \
  pytest testing/tests/MYTUBE-309/test_mytube_309.py -v
```

## Expected output (passing)

```
PASSED TestCIServiceAccountIAMPolicyAudit::test_ci_sa_has_object_creator_role
PASSED TestCIServiceAccountIAMPolicyAudit::test_ci_sa_has_object_viewer_role
PASSED TestCIServiceAccountIAMPolicyAudit::test_both_roles_present
```
