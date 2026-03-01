"""GcpIamService — component for inspecting GCP IAM policies via gcloud CLI."""
import json
import subprocess

from testing.core.config.gcp_config import GcpConfig


class GcpIamService:
    """Encapsulates gcloud subprocess calls for IAM policy inspection."""

    def __init__(self, config: GcpConfig) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_bucket_bindings(self, bucket: str) -> list[dict]:
        """Return IAM bindings for a GCS bucket.

        Returns a list of dicts: [{"role": "...", "members": [...]}, ...]
        Raises RuntimeError if gcloud returns a non-zero exit code.
        """
        result = self._run_gcloud(
            "storage", "buckets", "get-iam-policy",
            f"gs://{bucket}",
            "--project", self._config.project_id,
            "--format", "json",
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to retrieve IAM policy for gs://{bucket}.\n"
                f"stderr: {result.stderr.strip()}"
            )
        policy = json.loads(result.stdout)
        return policy.get("bindings", [])

    def get_cloud_run_job_sa(self, job_name: str) -> str:
        """Return the full service account email attached to a Cloud Run Job.

        Falls back to constructing the email from the short name if no '@' is present.
        Raises RuntimeError if gcloud returns a non-zero exit code or the key is absent.
        """
        result = self._run_gcloud(
            "run", "jobs", "describe", job_name,
            "--region", self._config.region,
            "--project", self._config.project_id,
            "--format", "json",
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to describe Cloud Run Job '{job_name}'.\n"
                f"stderr: {result.stderr.strip()}"
            )
        job_config = json.loads(result.stdout)
        try:
            sa = job_config["spec"]["template"]["spec"]["serviceAccountName"]
        except KeyError:
            raise RuntimeError(
                f"Could not find serviceAccountName in Cloud Run Job spec.\n"
                f"Job config keys: {list(job_config.keys())}"
            )
        if "@" not in sa:
            sa = f"{sa}@{self._config.project_id}.iam.gserviceaccount.com"
        return sa

    def member_has_role(self, bindings: list[dict], member: str, role: str) -> bool:
        """Return True if *member* is bound to *role* in *bindings*."""
        for binding in bindings:
            if binding.get("role") == role:
                if member in binding.get("members", []):
                    return True
        return False

    def member_has_any_role(self, bindings: list[dict], member: str, roles: set[str]) -> list[str]:
        """Return the subset of *roles* that *member* is bound to."""
        found = []
        for binding in bindings:
            role = binding.get("role", "")
            if role in roles and member in binding.get("members", []):
                found.append(role)
        return found

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _run_gcloud(*args: str) -> subprocess.CompletedProcess:
        cmd = ["gcloud", *args]
        return subprocess.run(cmd, capture_output=True, text=True)
