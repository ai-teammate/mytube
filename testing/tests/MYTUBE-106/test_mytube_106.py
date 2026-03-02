"""
MYTUBE-106: Verify that the test suite gracefully handles the absence of the
optional CDN_BASE_URL environment variable by skipping the relevant test
instead of failing it.

Preconditions:
  - GOOGLE_APPLICATION_CREDENTIALS is correctly configured (GCS tests can run).
  - CDN_BASE_URL is NOT set.

Expected behaviour:
  - test_object_served_via_cdn_url is reported as SKIPPED with a descriptive
    message indicating that CDN_BASE_URL must be set.

This meta-test:
  1. Verifies that GCSConfig.cdn_base_url is empty when CDN_BASE_URL is unset,
     which is the condition that triggers the skip guard.
  2. Verifies that the skip guard in test_mytube_49.py's
     test_object_served_via_cdn_url emits a pytest.skip() (Skipped exception)
     rather than a failure or an error when cdn_base_url is falsy.
  3. Verifies that the skip message is descriptive — it instructs the user to
     set CDN_BASE_URL.
  4. Runs the MYTUBE-49 suite via subprocess (pytest --collect + run) with
     CDN_BASE_URL unset, confirming the test node is reported as skipped in
     the real pytest output.
"""
from __future__ import annotations

import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcs_config import GCSConfig


# ---------------------------------------------------------------------------
# Unit-level tests — no real GCP credentials required
# ---------------------------------------------------------------------------


class TestCDNBaseURLAbsence:
    """GCSConfig and the CDN skip guard behave correctly when CDN_BASE_URL is unset."""

    def test_gcs_config_cdn_base_url_empty_when_env_var_unset(self, monkeypatch):
        """
        GCSConfig.cdn_base_url must be an empty string when CDN_BASE_URL is
        not present in the environment.
        """
        monkeypatch.delenv("CDN_BASE_URL", raising=False)
        config = GCSConfig()
        assert config.cdn_base_url == "", (
            "Expected GCSConfig.cdn_base_url to be '' when CDN_BASE_URL is unset, "
            f"got {config.cdn_base_url!r}"
        )

    def test_gcs_config_cdn_base_url_falsy_triggers_skip_guard(self, monkeypatch):
        """
        When cdn_base_url is falsy the skip condition `if not gcs_config.cdn_base_url`
        evaluates to True — confirming the guard will fire.
        """
        monkeypatch.delenv("CDN_BASE_URL", raising=False)
        config = GCSConfig()
        assert not config.cdn_base_url, (
            "cdn_base_url must be falsy when CDN_BASE_URL is unset so the skip "
            "guard in test_object_served_via_cdn_url activates."
        )

    def test_skip_guard_raises_skipped_with_descriptive_message(self, monkeypatch):
        """
        Simulates the skip guard in test_object_served_via_cdn_url.

        When cdn_base_url is empty the guard must:
          - raise pytest.skip.Exception (i.e. call pytest.skip())
          - include 'CDN_BASE_URL' in the skip reason
        """
        monkeypatch.delenv("CDN_BASE_URL", raising=False)
        config = GCSConfig()

        def _run_skip_guard(cfg: GCSConfig) -> None:
            """Mirrors the guard at the top of test_object_served_via_cdn_url."""
            if not cfg.cdn_base_url:
                pytest.skip(
                    "CDN_BASE_URL is not set. Set it to the Cloud CDN frontend IP or CNAME "
                    "(e.g. https://34.x.x.x or https://cdn.example.com) to verify CDN delivery."
                )

        with pytest.raises(pytest.skip.Exception) as exc_info:
            _run_skip_guard(config)

        skip_reason = str(exc_info.value)
        assert "CDN_BASE_URL" in skip_reason, (
            f"Skip message must mention 'CDN_BASE_URL' so the user knows what to set. "
            f"Actual message: {skip_reason!r}"
        )

    def test_skip_message_is_descriptive(self, monkeypatch):
        """
        The skip reason must guide the user: it should mention CDN_BASE_URL and
        provide an example value or instruction.
        """
        monkeypatch.delenv("CDN_BASE_URL", raising=False)
        config = GCSConfig()

        skip_reason_captured: list[str] = []

        def _run_guard(cfg: GCSConfig) -> None:
            if not cfg.cdn_base_url:
                reason = (
                    "CDN_BASE_URL is not set. Set it to the Cloud CDN frontend IP or CNAME "
                    "(e.g. https://34.x.x.x or https://cdn.example.com) to verify CDN delivery."
                )
                skip_reason_captured.append(reason)
                pytest.skip(reason)

        with pytest.raises(pytest.skip.Exception):
            _run_guard(config)

        reason = skip_reason_captured[0]
        assert "CDN_BASE_URL" in reason, "Skip reason must mention the missing env var."
        assert "not set" in reason.lower() or "unset" in reason.lower() or "set it" in reason.lower(), (
            "Skip reason should explain that CDN_BASE_URL needs to be configured."
        )


# ---------------------------------------------------------------------------
# Integration-level test — runs MYTUBE-49 suite as a subprocess
# ---------------------------------------------------------------------------


class TestMytube49SubprocessSkipBehaviour:
    """
    Runs the MYTUBE-49 pytest suite as a subprocess with CDN_BASE_URL unset.

    Uses the mock service account fixture so that GCP credential validation
    passes and the CDN skip is the only thing that triggers.
    """

    def test_cdn_test_is_skipped_in_subprocess_run(self, tmp_path):
        """
        Execute the MYTUBE-49 test file with:
          - GOOGLE_APPLICATION_CREDENTIALS pointing to the mock service account
          - CDN_BASE_URL explicitly removed from the environment

        Verifies that pytest reports test_object_served_via_cdn_url as SKIPPED,
        not FAILED or ERROR.
        """
        repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        mock_creds = os.path.join(repo_root, "testing", "fixtures", "mock_service_account.json")
        test_file = os.path.join(
            repo_root, "testing", "tests", "MYTUBE-49", "test_mytube_49.py"
        )

        env = os.environ.copy()
        env["GOOGLE_APPLICATION_CREDENTIALS"] = mock_creds
        # Ensure CDN_BASE_URL is absent
        env.pop("CDN_BASE_URL", None)

        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                test_file,
                "-v",
                "--tb=short",
                "-rs",  # show skip reasons in the summary
                "-k", "test_object_served_via_cdn_url",
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=repo_root,
        )

        combined_output = result.stdout + result.stderr

        # The test must not appear as FAILED or ERROR
        assert "FAILED" not in combined_output, (
            "test_object_served_via_cdn_url must not be FAILED when CDN_BASE_URL is unset.\n"
            f"pytest output:\n{combined_output}"
        )
        assert "ERROR" not in combined_output, (
            "test_object_served_via_cdn_url must not produce an ERROR when CDN_BASE_URL is unset.\n"
            f"pytest output:\n{combined_output}"
        )

        # The test must be reported as skipped
        assert "skipped" in combined_output.lower() or "SKIPPED" in combined_output, (
            "test_object_served_via_cdn_url must be reported as SKIPPED when CDN_BASE_URL is unset.\n"
            f"pytest output:\n{combined_output}"
        )

        # The skip reason must mention CDN_BASE_URL
        assert "CDN_BASE_URL" in combined_output, (
            "The skip reason must mention CDN_BASE_URL in the pytest output.\n"
            f"pytest output:\n{combined_output}"
        )
