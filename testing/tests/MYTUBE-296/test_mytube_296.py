"""
MYTUBE-296: Infrastructure setup script grants object creator role —
CI service account permission verified in setup.sh.

Objective
---------
Ensure that the infra/setup.sh script correctly includes the IAM policy
binding for the CI service account to prevent regression of permission issues.

Steps
-----
1. Open the infra/setup.sh file from the repository.
2. Locate the section where IAM policy bindings for the RAW_BUCKET
   (gs://mytube-raw-uploads) are defined.
3. Verify that the CI service account (CI_SA_EMAIL) is granted the
   roles/storage.objectCreator role.

Expected Result
---------------
The script contains the command:
  gcloud storage buckets add-iam-policy-binding gs://mytube-raw-uploads
    --member="serviceAccount:ai-teammate-gcloud@ai-native-478811.iam.gserviceaccount.com"
    --role="roles/storage.objectCreator"

Test approach
-------------
This is a static file-content verification test. The script uses shell
variables (RAW_BUCKET, CI_SA_EMAIL, CI_SA) rather than hard-coded values, so
the test:
  1. Confirms the canonical variable assignments are present and correct.
  2. Confirms that a gcloud add-iam-policy-binding call for the RAW_BUCKET
     variable grants roles/storage.objectCreator to the CI_SA_EMAIL member.

No GCP credentials or network access are required.
"""
from __future__ import annotations

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SETUP_SH = os.path.join(REPO_ROOT, "infra", "setup.sh")

EXPECTED_RAW_BUCKET = "mytube-raw-uploads"
EXPECTED_CI_SA = "ai-teammate-gcloud"
EXPECTED_ROLE = "roles/storage.objectCreator"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_script() -> str:
    """Return the full text of infra/setup.sh."""
    with open(SETUP_SH, "r", encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSetupShCiSaObjectCreator:
    """Verify that infra/setup.sh grants roles/storage.objectCreator to the CI SA."""

    def test_setup_sh_exists(self):
        """Step 1 — infra/setup.sh must exist in the repository."""
        assert os.path.isfile(SETUP_SH), (
            f"infra/setup.sh was not found at {SETUP_SH}. "
            "The file must exist in the repository."
        )

    def test_raw_bucket_variable_defined(self):
        """Step 2a — RAW_BUCKET must be assigned to 'mytube-raw-uploads'."""
        content = _load_script()
        # Match: RAW_BUCKET="mytube-raw-uploads" or RAW_BUCKET='mytube-raw-uploads'
        pattern = re.compile(
            r'RAW_BUCKET\s*=\s*["\']?' + re.escape(EXPECTED_RAW_BUCKET) + r'["\']?'
        )
        assert pattern.search(content), (
            f"Expected RAW_BUCKET to be set to '{EXPECTED_RAW_BUCKET}' in "
            f"infra/setup.sh, but no matching assignment was found.\n"
            f"Looked for pattern: {pattern.pattern}"
        )

    def test_ci_sa_variable_defined(self):
        """Step 2b — CI_SA must be assigned to 'ai-teammate-gcloud'."""
        content = _load_script()
        pattern = re.compile(
            r'CI_SA\s*=\s*["\']?' + re.escape(EXPECTED_CI_SA) + r'["\']?'
        )
        assert pattern.search(content), (
            f"Expected CI_SA to be set to '{EXPECTED_CI_SA}' in infra/setup.sh, "
            f"but no matching assignment was found.\n"
            f"Looked for pattern: {pattern.pattern}"
        )

    def test_ci_sa_email_derived_from_ci_sa(self):
        """Step 2c — CI_SA_EMAIL must reference ${CI_SA} and the project variable."""
        content = _load_script()
        # Accept either: CI_SA_EMAIL="${CI_SA}@${PROJECT}.iam.gserviceaccount.com"
        pattern = re.compile(
            r'CI_SA_EMAIL\s*=.*\$\{?CI_SA\}?.*iam\.gserviceaccount\.com'
        )
        assert pattern.search(content), (
            "Expected CI_SA_EMAIL to be derived from CI_SA and the project variable "
            "(e.g. CI_SA_EMAIL=\"${CI_SA}@${PROJECT}.iam.gserviceaccount.com\"), "
            "but no such assignment was found in infra/setup.sh."
        )

    def test_objectcreator_binding_for_raw_bucket_and_ci_sa(self):
        """Step 3 — Script must grant roles/storage.objectCreator to CI_SA on RAW_BUCKET.

        This is the core assertion: verify that the script contains a
        gcloud storage buckets add-iam-policy-binding call targeting the raw
        uploads bucket, with the CI service account as the member and
        roles/storage.objectCreator as the role.
        """
        content = _load_script()

        # The script may span multiple lines (backslash continuation).
        # Normalise by collapsing backslash-newline pairs.
        normalised = content.replace("\\\n", " ")

        # Find all add-iam-policy-binding invocations that reference RAW_BUCKET.
        # We look for lines that bind something on gs://${RAW_BUCKET} (variable form)
        # or gs://mytube-raw-uploads (literal form).
        bucket_patterns = [
            r'gs://\$\{?RAW_BUCKET\}?',          # variable form
            re.escape("gs://mytube-raw-uploads"),  # literal form
        ]

        member_patterns = [
            r'\$\{?CI_SA_EMAIL\}?',                         # variable form
            re.escape("ai-teammate-gcloud@"),               # literal partial
        ]

        role_literal = re.escape(EXPECTED_ROLE)

        found_binding = False
        for line in normalised.splitlines():
            if "add-iam-policy-binding" not in line:
                continue
            bucket_ok = any(re.search(p, line) for p in bucket_patterns)
            member_ok = any(re.search(p, line) for p in member_patterns)
            role_ok = re.search(role_literal, line)
            if bucket_ok and member_ok and role_ok:
                found_binding = True
                break

        assert found_binding, (
            "infra/setup.sh does not contain a gcloud storage buckets "
            "add-iam-policy-binding call that grants "
            f"'{EXPECTED_ROLE}' to the CI service account "
            f"(CI_SA_EMAIL / {EXPECTED_CI_SA}@<project>.iam.gserviceaccount.com) "
            f"on bucket gs://{EXPECTED_RAW_BUCKET}.\n\n"
            "Expected to find something equivalent to:\n"
            "  gcloud storage buckets add-iam-policy-binding gs://mytube-raw-uploads \\\n"
            "    --member=\"serviceAccount:ai-teammate-gcloud@<project>.iam.gserviceaccount.com\" \\\n"
            f"    --role=\"{EXPECTED_ROLE}\""
        )
