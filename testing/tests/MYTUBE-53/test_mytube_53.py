"""
MYTUBE-53: Verify infrastructure as code — setup scripts or Terraform files
present in repository.

Ensures that GCS, CDN, and Eventarc infrastructure is documented and
version-controlled in the infra/ directory.

The test checks that at least one of the following is present:
  1. infra/cloudjobs.yaml     — Cloud Run Job definition
  2. infra/*.tf               — Terraform configuration files
  3. infra/setup.sh           — Shell script containing documented gcloud commands

Expected: infrastructure setup files or documentation are present so the
environment can be reproduced.
"""
import os
import glob
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Path to the repository root (three levels up from this file).
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
INFRA_DIR = os.path.join(REPO_ROOT, "infra")


class TestInfrastructureAsCode:
    """Verify that infrastructure setup files exist and are version-controlled."""

    def test_infra_directory_exists(self):
        """The infra/ directory must exist at the repository root."""
        assert os.path.isdir(INFRA_DIR), (
            f"Expected infra/ directory at {INFRA_DIR} but it was not found."
        )

    def test_cloudjobs_yaml_exists(self):
        """infra/cloudjobs.yaml must be present (Cloud Run Job definition)."""
        path = os.path.join(INFRA_DIR, "cloudjobs.yaml")
        assert os.path.isfile(path), (
            f"Expected infra/cloudjobs.yaml at {path} but it was not found."
        )

    def test_cloudjobs_yaml_is_not_empty(self):
        """infra/cloudjobs.yaml must contain content (not a blank placeholder)."""
        path = os.path.join(INFRA_DIR, "cloudjobs.yaml")
        assert os.path.isfile(path), f"infra/cloudjobs.yaml not found at {path}"
        size = os.path.getsize(path)
        assert size > 0, "infra/cloudjobs.yaml is empty"

    def test_setup_script_exists(self):
        """infra/setup.sh must be present with documented gcloud setup commands."""
        path = os.path.join(INFRA_DIR, "setup.sh")
        assert os.path.isfile(path), (
            f"Expected infra/setup.sh at {path} but it was not found."
        )

    def test_setup_script_contains_gcloud_commands(self):
        """infra/setup.sh must document gcloud commands for reproducing the environment."""
        path = os.path.join(INFRA_DIR, "setup.sh")
        assert os.path.isfile(path), f"infra/setup.sh not found at {path}"
        with open(path, "r") as fh:
            content = fh.read()
        assert "gcloud" in content, (
            "infra/setup.sh exists but contains no 'gcloud' commands. "
            "Expected at least one gcloud command documenting GCS/CDN/Eventarc setup."
        )

    def test_infrastructure_covers_gcs(self):
        """setup.sh must document GCS bucket creation (storage infrastructure)."""
        path = os.path.join(INFRA_DIR, "setup.sh")
        assert os.path.isfile(path), f"infra/setup.sh not found at {path}"
        with open(path, "r") as fh:
            content = fh.read()
        assert "storage" in content.lower() or "gcs" in content.lower(), (
            "infra/setup.sh does not appear to document any GCS/storage setup."
        )

    def test_infrastructure_covers_eventarc(self):
        """setup.sh must document Eventarc trigger creation."""
        path = os.path.join(INFRA_DIR, "setup.sh")
        assert os.path.isfile(path), f"infra/setup.sh not found at {path}"
        with open(path, "r") as fh:
            content = fh.read()
        assert "eventarc" in content.lower(), (
            "infra/setup.sh does not appear to document any Eventarc trigger setup."
        )

    def test_infrastructure_covers_cloud_run(self):
        """setup.sh or cloudjobs.yaml must document Cloud Run Job configuration."""
        setup_path = os.path.join(INFRA_DIR, "setup.sh")
        cloudjobs_path = os.path.join(INFRA_DIR, "cloudjobs.yaml")

        content = ""
        for p in (setup_path, cloudjobs_path):
            if os.path.isfile(p):
                with open(p, "r") as fh:
                    content += fh.read()

        assert "run" in content.lower(), (
            "Neither infra/setup.sh nor infra/cloudjobs.yaml documents Cloud Run configuration."
        )
