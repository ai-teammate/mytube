"""GCS bucket service — queries bucket existence, IAM policy, and public access.

Provides a typed interface for interacting with the GCS bucket under test.
All GCP API interactions are encapsulated here; tests access only high-level
methods and never call the GCS SDK directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import urllib.request
import urllib.error

from testing.core.config.gcs_config import GCSConfig


@dataclass
class BucketIAMInfo:
    """Holds the relevant IAM/access configuration of a GCS bucket."""

    exists: bool
    public_access_prevention: Optional[str]  # e.g. "enforced", "inherited", None
    uniform_bucket_level_access: Optional[bool]
    raw_iam_bindings: list = field(default_factory=list)  # list of (role, members)


@dataclass
class PublicAccessResult:
    """Result of attempting to fetch an object via its public GCS URL."""

    url: str
    http_status: int
    error_message: str = ""


class GCSBucketService:
    """Service for inspecting a GCS bucket's configuration and access controls.

    Parameters
    ----------
    config:
        GCSConfig instance carrying project and bucket names.
    storage_client:
        An authenticated ``google.cloud.storage.Client`` instance.
        Must be injected by the caller — never instantiated internally.
    """

    def __init__(self, config: GCSConfig, storage_client) -> None:
        self._config = config
        self._client = storage_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def bucket_exists(self) -> bool:
        """Return True if the raw-uploads bucket exists in the project."""
        bucket = self._client.bucket(self._config.raw_uploads_bucket)
        return bucket.exists()

    def get_iam_info(self) -> BucketIAMInfo:
        """Fetch the bucket's IAM policy and return a structured summary."""
        bucket_name = self._config.raw_uploads_bucket
        bucket = self._client.get_bucket(bucket_name)

        # Public Access Prevention — bucket.iam_configuration is a nested object
        iam_cfg = bucket.iam_configuration
        pap = getattr(iam_cfg, "public_access_prevention", None)
        uble = getattr(iam_cfg, "uniform_bucket_level_access_enabled", None)

        # Retrieve the bucket-level IAM policy bindings
        policy = bucket.get_iam_policy(requested_policy_version=1)
        bindings = [(b["role"], list(b["members"])) for b in policy.bindings]

        return BucketIAMInfo(
            exists=True,
            public_access_prevention=pap,
            uniform_bucket_level_access=uble,
            raw_iam_bindings=bindings,
        )

    def attempt_public_access(self, object_name: str = "probe.txt") -> PublicAccessResult:
        """Attempt to fetch *object_name* from the bucket using its public URL.

        No authentication is used.  The GCS storage XML API endpoint is used so
        the response code reflects the bucket's public-access configuration
        rather than being blocked by a firewall or proxy.
        """
        url = self._config.raw_bucket_public_url(object_name)
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                return PublicAccessResult(url=url, http_status=resp.status)
        except urllib.error.HTTPError as exc:
            return PublicAccessResult(
                url=url,
                http_status=exc.code,
                error_message=str(exc.reason),
            )
        except urllib.error.URLError as exc:
            # Network-level error — treat as inconclusive, return 0 status
            return PublicAccessResult(
                url=url,
                http_status=0,
                error_message=str(exc.reason),
            )
