"""
MYTUBE-336: CI service account missing roles/eventarc.viewer —
            PERMISSION_DENIED on project IAM policy retrieval.

Objective
---------
Verify that ``infra/setup.sh`` includes a project-level IAM binding that grants
``roles/eventarc.viewer`` to the CI service account within a **single command
block** — i.e. all three required elements appear together:

  * ``gcloud projects add-iam-policy-binding``
  * ``${CI_SA_EMAIL}``  (or the literal SA email)
  * ``roles/eventarc.viewer``

This is a static analysis (unit) test — it does not require live GCP credentials.
It guards against regressions where the provisioning script is modified and the
critical IAM binding is accidentally removed or split across unrelated statements.

Test Steps
----------
1. Read ``infra/setup.sh`` from the repository root.
2. Split the script into logical command blocks (statements separated by blank
   lines or comment lines).
3. Assert that at least one block simultaneously contains all three required
   strings.

Expected Result
---------------
The script contains the required binding so that running ``infra/setup.sh``
grants the CI SA the necessary project-level permission to read IAM policies
and inspect Eventarc triggers.
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

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
SETUP_SCRIPT = os.path.join(REPO_ROOT, "infra", "setup.sh")

CI_SA_VAR = "CI_SA_EMAIL"        # variable name used in the script for the CI SA
EXPECTED_ROLE = "roles/eventarc.viewer"
EXPECTED_COMMAND = "add-iam-policy-binding"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_setup_script() -> str:
    if not os.path.exists(SETUP_SCRIPT):
        pytest.fail(f"infra/setup.sh not found at {SETUP_SCRIPT}")
    with open(SETUP_SCRIPT, "r") as fh:
        return fh.read()


def _split_into_command_blocks(content: str) -> list[str]:
    """Split the shell script into contiguous logical blocks.

    A new block begins after any blank line or a line that starts with '#'
    followed by dashes (section separator).  Continuation lines (ending with
    ``\\``) are kept together with the preceding line so that a single
    multi-line ``gcloud`` call is treated as one block.
    """
    blocks: list[str] = []
    current_lines: list[str] = []

    for line in content.splitlines():
        # Section separator or blank line ends the current block.
        is_separator = re.match(r"^#\s*─+", line) or line.strip() == ""
        if is_separator and current_lines:
            blocks.append("\n".join(current_lines))
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        blocks.append("\n".join(current_lines))

    return blocks


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSetupShEventarcViewerBinding:
    """MYTUBE-336: infra/setup.sh must grant roles/eventarc.viewer to the CI SA."""

    def test_setup_script_grants_eventarc_viewer_to_ci_sa(self) -> None:
        """Assert that a single contiguous command block in infra/setup.sh contains
        all three required elements:
          - 'add-iam-policy-binding'
          - '${CI_SA_EMAIL}' (or literal SA email)
          - 'roles/eventarc.viewer'

        Failure means the provisioning script is missing the project-level IAM
        grant.  Running setup.sh without this binding will leave the CI SA unable
        to read the project IAM policy, causing PERMISSION_DENIED errors in any
        pipeline step that inspects Eventarc trigger configurations.
        """
        content = _load_setup_script()
        blocks = _split_into_command_blocks(content)

        def _block_has_all(block: str) -> bool:
            return (
                EXPECTED_COMMAND in block
                and EXPECTED_ROLE in block
                and (CI_SA_VAR in block or "ai-teammate-gcloud" in block)
            )

        matching_blocks = [b for b in blocks if _block_has_all(b)]

        assert matching_blocks, (
            f"infra/setup.sh does NOT contain a single contiguous command block "
            f"that grants '{EXPECTED_ROLE}' to the CI service account via "
            f"'gcloud projects {EXPECTED_COMMAND}'.\n\n"
            "All three elements must appear within the same command block:\n"
            f"  1. '{EXPECTED_COMMAND}'\n"
            f"  2. '${{{CI_SA_VAR}}}' (or literal CI SA email)\n"
            f"  3. '{EXPECTED_ROLE}'\n\n"
            "Add the following to infra/setup.sh:\n\n"
            '  gcloud projects add-iam-policy-binding "${PROJECT}" \\\n'
            '    --member="serviceAccount:${CI_SA_EMAIL}" \\\n'
            f'    --role="{EXPECTED_ROLE}" \\\n'
            "    --condition=None\n\n"
            "And apply the change to the live project:\n"
            "  gcloud projects add-iam-policy-binding ai-native-478811 \\\n"
            "    --member=serviceAccount:ai-teammate-gcloud@ai-native-478811.iam.gserviceaccount.com \\\n"
            f"    --role={EXPECTED_ROLE} \\\n"
            "    --condition=None"
        )

    def test_setup_script_uses_ci_sa_variable_not_hardcoded_email(self) -> None:
        """Assert that the binding uses the ${CI_SA_EMAIL} variable, not a
        hardcoded email address, so the script remains reusable across projects.
        """
        content = _load_setup_script()

        # Find the add-iam-policy-binding block that contains roles/eventarc.viewer.
        # Check that it references the variable, not a raw email.
        pattern = re.compile(
            r"add-iam-policy-binding.*?roles/eventarc\.viewer",
            re.DOTALL,
        )
        match = pattern.search(content)
        assert match is not None, (
            "No 'add-iam-policy-binding ... roles/eventarc.viewer' block found. "
            "Run test_setup_script_grants_eventarc_viewer_to_ci_sa first."
        )

        binding_block = match.group(0)
        assert CI_SA_VAR in binding_block, (
            f"The roles/eventarc.viewer binding should reference '${{{CI_SA_VAR}}}' "
            "rather than a hardcoded email address to keep the script portable."
        )
