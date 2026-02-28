# MYTUBE-53 — Verify infrastructure as code: setup scripts present in repository

## What this test verifies

Confirms that GCS, CDN, and Eventarc infrastructure is documented and
version-controlled in the `infra/` directory by checking for:

1. `infra/` directory exists at the repository root.
2. `infra/cloudjobs.yaml` — Cloud Run Job definition is present and non-empty.
3. `infra/setup.sh` — Shell script is present and contains documented `gcloud` commands.
4. `setup.sh` covers GCS storage provisioning.
5. `setup.sh` covers Eventarc trigger creation.
6. `setup.sh` or `cloudjobs.yaml` covers Cloud Run Job configuration.

## Requirements

- Python 3.10+
- `pytest`

No database or network access is required. The test only inspects the local filesystem.

## Environment variables

None required.

## Install dependencies

```bash
pip install pytest
```

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-53/test_mytube_53.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-53/test_mytube_53.py::TestInfrastructureAsCode::test_infra_directory_exists PASSED
testing/tests/MYTUBE-53/test_mytube_53.py::TestInfrastructureAsCode::test_cloudjobs_yaml_exists PASSED
testing/tests/MYTUBE-53/test_mytube_53.py::TestInfrastructureAsCode::test_cloudjobs_yaml_is_not_empty PASSED
testing/tests/MYTUBE-53/test_mytube_53.py::TestInfrastructureAsCode::test_setup_script_exists PASSED
testing/tests/MYTUBE-53/test_mytube_53.py::TestInfrastructureAsCode::test_setup_script_contains_gcloud_commands PASSED
testing/tests/MYTUBE-53/test_mytube_53.py::TestInfrastructureAsCode::test_infrastructure_covers_gcs PASSED
testing/tests/MYTUBE-53/test_mytube_53.py::TestInfrastructureAsCode::test_infrastructure_covers_eventarc PASSED
testing/tests/MYTUBE-53/test_mytube_53.py::TestInfrastructureAsCode::test_infrastructure_covers_cloud_run PASSED
8 passed
```
