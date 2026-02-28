# MYTUBE-52 — Validate Cloud Run Job environment variables

## What this test verifies

Inspects `infra/cloudjobs.yaml` and asserts that the `mytube-transcoder` Cloud Run Job
definition declares all three mandatory environment variables:

| Variable | Purpose |
|---|---|
| `RAW_OBJECT_PATH` | GCS path to the raw uploaded video |
| `VIDEO_ID` | Identifier of the video being transcoded |
| `HLS_BUCKET` | Destination GCS bucket for HLS output |

## Dependencies

- Python 3.10+
- `pytest`
- `PyYAML`

Install:

```bash
pip install pytest pyyaml
```

## How to run

From the repository root:

```bash
pytest testing/tests/MYTUBE-52/test_mytube_52.py -v
```

## Expected output when passing

```
testing/tests/MYTUBE-52/test_mytube_52.py::TestCloudJobEnvVars::test_required_env_var_present[RAW_OBJECT_PATH] PASSED
testing/tests/MYTUBE-52/test_mytube_52.py::TestCloudJobEnvVars::test_required_env_var_present[VIDEO_ID] PASSED
testing/tests/MYTUBE-52/test_mytube_52.py::TestCloudJobEnvVars::test_required_env_var_present[HLS_BUCKET] PASSED
```

## Environment variables required

None — this test only reads a local YAML file.
