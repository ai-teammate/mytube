"""
MYTUBE-52: Validate Cloud Run Job environment variables — Job configuration
contains required metadata.

Verifies that the `mytube-transcoder` Cloud Run Job definition in
`infra/cloudjobs.yaml` includes all mandatory environment variables required
for the transcoding process:
  - RAW_OBJECT_PATH
  - VIDEO_ID
  - HLS_BUCKET

The test inspects the YAML file directly (no deployment needed).
"""
import os
import pytest
import yaml

CLOUDJOBS_YAML = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "infra",
    "cloudjobs.yaml",
)

REQUIRED_ENV_VARS = ["RAW_OBJECT_PATH", "VIDEO_ID", "HLS_BUCKET"]


def _load_env_var_names(yaml_path: str) -> list[str]:
    """Parse cloudjobs.yaml and return the names of all defined env vars."""
    with open(yaml_path, "r") as f:
        doc = yaml.safe_load(f)

    # Navigate the Cloud Run Job spec structure
    # spec.template.spec.template.spec.containers[].env
    containers = (
        doc.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("containers", [])
    )

    names: list[str] = []
    for container in containers:
        for env_entry in container.get("env", []):
            if "name" in env_entry:
                names.append(env_entry["name"])
    return names


class TestCloudJobEnvVars:
    """mytube-transcoder job definition must declare all required env vars."""

    @pytest.fixture(scope="class")
    def defined_env_vars(self) -> list[str]:
        assert os.path.isfile(CLOUDJOBS_YAML), (
            f"cloudjobs.yaml not found at: {CLOUDJOBS_YAML}"
        )
        return _load_env_var_names(CLOUDJOBS_YAML)

    @pytest.mark.parametrize("env_var", REQUIRED_ENV_VARS)
    def test_required_env_var_present(self, defined_env_vars: list[str], env_var: str):
        """Each required env var must be declared in the job's container env list."""
        assert env_var in defined_env_vars, (
            f"Required env var '{env_var}' is missing from infra/cloudjobs.yaml. "
            f"Defined vars: {defined_env_vars}"
        )
