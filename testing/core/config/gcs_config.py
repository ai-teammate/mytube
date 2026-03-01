"""GCS and CDN configuration loaded from environment variables."""
import os


class GCSConfig:
    hls_bucket: str
    raw_bucket: str
    gcs_public_base_url: str
    cdn_base_url: str

    def __init__(self):
        self.hls_bucket = os.getenv("HLS_BUCKET", "mytube-hls-output")
        self.raw_bucket = os.getenv("RAW_BUCKET", "mytube-raw-uploads")
        self.gcs_public_base_url = os.getenv(
            "GCS_PUBLIC_BASE_URL", "https://storage.googleapis.com"
        )
        self.cdn_base_url = os.getenv("CDN_BASE_URL", "")

    def public_object_url(self, bucket: str, object_name: str) -> str:
        """Returns the direct public GCS URL for an object."""
        return f"{self.gcs_public_base_url}/{bucket}/{object_name}"

    def cdn_object_url(self, object_name: str) -> str:
        """Returns the Cloud CDN frontend URL for an object in the HLS bucket.

        CDN_BASE_URL must be set to the Cloud CDN frontend IP or CNAME
        (e.g. https://34.x.x.x or https://cdn.example.com).
        """
        base = self.cdn_base_url.rstrip("/")
        return f"{base}/{object_name}"
