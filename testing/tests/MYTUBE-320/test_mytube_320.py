"""
MYTUBE-320: Infrastructure setup script defines IAM role — roles/eventarc.viewer
granted to CI service account.

Objective
---------
Verify that the infrastructure automation script (infra/setup.sh) includes the
project-level IAM binding for the CI service account so that the fix is permanent
and regression is prevented.

Steps
-----
1. Open the script file ``infra/setup.sh``.
2. Search for the command that adds project IAM policy bindings.
3. Verify that ``gcloud projects add-iam-policy-binding`` is present and correctly
   grants ``roles/eventarc.viewer`` to the service account
   ``ai-teammate-gcloud@<project>.iam.gserviceaccount.com`` (where ``<project>``
   may be the literal variable ``${PROJECT}`` or the resolved project ID).

Expected Result
---------------
The setup script contains the automated command to grant the required Eventarc
permissions to the CI service account.

Architecture
------------
- Pure static-file analysis: no external services, no network I/O, no credentials.
- Uses only Python's built-in ``re`` and ``pathlib`` — no framework dependencies.
- ``_SETUP_SH`` is the only environment-sensitive value; override with the
  ``SETUP_SH_PATH`` env var to test a different copy.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]  # testing/tests/MYTUBE-320 → repo root

_DEFAULT_SETUP_SH = _REPO_ROOT / "infra" / "setup.sh"
_SETUP_SH = Path(os.getenv("SETUP_SH_PATH", str(_DEFAULT_SETUP_SH)))

# The CI service account name (without @<project>.iam.gserviceaccount.com).
# The script defines  CI_SA="ai-teammate-gcloud" and uses the variable
# ${CI_SA_EMAIL} in policy-binding commands.
_CI_SA_NAME = "ai-teammate-gcloud"
_REQUIRED_ROLE = "roles/eventarc.viewer"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_script() -> str:
    if not _SETUP_SH.is_file():
        pytest.fail(
            f"Setup script not found at {_SETUP_SH}. "
            "Set SETUP_SH_PATH to point to the correct location."
        )
    return _SETUP_SH.read_text(encoding="utf-8")


def _extract_project_iam_bindings(script: str) -> list[str]:
    """Return every ``gcloud projects add-iam-policy-binding`` invocation block.

    A binding block starts at the ``gcloud projects add-iam-policy-binding`` line
    and continues until a line that does NOT end with a backslash continuation.
    """
    blocks: list[str] = []
    lines = script.splitlines()
    in_block = False
    current: list[str] = []

    for line in lines:
        stripped = line.rstrip()
        if not in_block:
            if re.search(r"gcloud\s+projects\s+add-iam-policy-binding", stripped):
                in_block = True
                current = [stripped]
        else:
            current.append(stripped)

        if in_block and not stripped.endswith("\\"):
            blocks.append("\n".join(current))
            in_block = False
            current = []

    # Handle a block that ends at EOF without a non-continuation line.
    if in_block and current:
        blocks.append("\n".join(current))

    return blocks


def _binding_targets_ci_sa(block: str) -> bool:
    """Return True if the binding block references the CI service account."""
    # Accept either the resolved email or the shell variable.
    return bool(
        re.search(
            r"serviceAccount:[^\s]*" + re.escape(_CI_SA_NAME),
            block,
        )
        or re.search(r"\$\{CI_SA_EMAIL\}", block)
        or re.search(r"\$CI_SA_EMAIL\b", block)
    )


def _binding_grants_role(block: str, role: str) -> bool:
    """Return True if the binding block grants the specified IAM role."""
    return bool(re.search(re.escape(role), block))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSetupShEventarcViewerBinding:
    """MYTUBE-320: setup.sh grants roles/eventarc.viewer to the CI SA."""

    def test_gcloud_projects_add_iam_policy_binding_present(self) -> None:
        """At least one ``gcloud projects add-iam-policy-binding`` invocation exists."""
        script = _load_script()
        bindings = _extract_project_iam_bindings(script)
        assert bindings, (
            f"No ``gcloud projects add-iam-policy-binding`` invocation found in "
            f"{_SETUP_SH}. "
            "The setup script must automate IAM policy setup to prevent regression."
        )

    def test_eventarc_viewer_role_granted_to_ci_service_account(self) -> None:
        """setup.sh contains a project-level binding that grants
        roles/eventarc.viewer to the CI service account (ai-teammate-gcloud@...)."""
        script = _load_script()
        bindings = _extract_project_iam_bindings(script)

        matching = [
            b for b in bindings
            if _binding_targets_ci_sa(b) and _binding_grants_role(b, _REQUIRED_ROLE)
        ]

        assert matching, (
            f"No ``gcloud projects add-iam-policy-binding`` block in {_SETUP_SH} "
            f"grants {_REQUIRED_ROLE!r} to the CI service account "
            f"({_CI_SA_NAME!r}).\n\n"
            f"Found {len(bindings)} project-level binding(s):\n"
            + "\n---\n".join(bindings)
        )
