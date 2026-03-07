# MYTUBE-319 — CI service account describes Eventarc trigger

## Objective

Verify that the CI service account `ai-teammate-gcloud@ai-native-478811.iam.gserviceaccount.com`
has the project-level `roles/eventarc.viewer` role, which grants the `eventarc.triggers.get`
permission required to describe Eventarc triggers without `PERMISSION_DENIED` errors.

## Test Type

`infrastructure` — GCP IAM policy validation via `gcloud`.

## Steps

1. Run `gcloud projects get-iam-policy ai-native-478811 --format="json"` to fetch the project-level IAM policy.
2. Filter the policy bindings for the CI service account `serviceAccount:ai-teammate-gcloud@ai-native-478811.iam.gserviceaccount.com`.
3. Verify that `roles/eventarc.viewer` is present in the bindings for that account.

## Expected Result

The IAM policy contains a binding for the CI service account with `roles/eventarc.viewer`
at the project level, allowing Eventarc trigger description commands to succeed.

## Prerequisites

- Python 3.10+
- `pytest`
- `gcloud` CLI authenticated as the CI service account
- The CI service account must have `resourcemanager.projects.getIamPolicy` permission

## Environment Variables

| Variable         | Default                                                     | Description                        |
|------------------|-------------------------------------------------------------|------------------------------------|
| `GCP_PROJECT_ID` | `ai-native-478811`                                          | GCP project ID                     |
| `CI_SA_EMAIL`    | `ai-teammate-gcloud@ai-native-478811.iam.gserviceaccount.com` | CI service account email           |
| `EXPECTED_ROLE`  | `roles/eventarc.viewer`                                     | IAM role expected at project level |

## Running the Test

```bash
pytest testing/tests/MYTUBE-319/test_mytube_319.py -v
```

## Fix (if failing)

Grant the CI service account the required project-level role:

```bash
gcloud projects add-iam-policy-binding ai-native-478811 \
  --member=serviceAccount:ai-teammate-gcloud@ai-native-478811.iam.gserviceaccount.com \
  --role=roles/eventarc.viewer
```
