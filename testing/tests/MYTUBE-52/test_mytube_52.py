"""
MYTUBE-52: Validate Cloud Run Job environment variables — Job configuration
contains required metadata.

Verifies that the `mytube-transcoder` Cloud Run Job definition in
`infra/cloudjobs.yaml` includes all mandatory static environment variables.

Architecture note:
  - Static env vars (HLS_BUCKET, RAW_BUCKET, CDN_BASE_URL, etc.) are declared
    in the job definition and are present in cloudjobs.yaml.
  - Per-execution variables (VIDEO_ID, RAW_OBJECT_PATH) are injected at
    runtime via the Cloud Run Jobs API "overrides" field and are intentionally
    absent from the static YAML definition.

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

# Static env vars that must be declared in the job definition.
# VIDEO_ID and RAW_OBJECT_PATH are runtime overrides (injected per-execution
# via the Cloud Run Jobs API) and are not expected in the static YAML.
REQUIRED_STATIC_ENV_VARS = ["HLS_BUCKET", "RAW_BUCKET"]


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
    """mytube-transcoder job definition must declare all required static env vars."""

    @pytest.fixture(scope="class")
    def defined_env_vars(self) -> list[str]:
        assert os.path.isfile(CLOUDJOBS_YAML), (
            f"cloudjobs.yaml not found at: {CLOUDJOBS_YAML}"
        )
        return _load_env_var_names(CLOUDJOBS_YAML)

    @pytest.mark.parametrize("env_var", REQUIRED_STATIC_ENV_VARS)
    def test_required_env_var_present(self, defined_env_vars: list[str], env_var: str):
        """Each required static env var must be declared in the job's container env list."""
        assert env_var in defined_env_vars, (
            f"Required env var '{env_var}' is missing from infra/cloudjobs.yaml. "
            f"Defined vars: {defined_env_vars}"
        )

    def test_runtime_override_vars_documented_in_yaml(self):
        """VIDEO_ID and RAW_OBJECT_PATH are runtime overrides; verify the YAML
        documents this pattern via the expected comment."""
        with open(CLOUDJOBS_YAML, "r") as f:
            content = f.read()
        assert "overrides" in content, (
            "cloudjobs.yaml should document that per-execution variables "
            "(VIDEO_ID, RAW_OBJECT_PATH) are injected via the Cloud Run Jobs API overrides field."
        )
