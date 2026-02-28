"""GCS and CDN configuration loaded from environment variables."""
import os


class GCSConfig:
    hls_bucket: str
    raw_bucket: str
    gcs_public_base_url: str

    def __init__(self):
        self.hls_bucket = os.getenv("HLS_BUCKET", "mytube-hls-output")
        self.raw_bucket = os.getenv("RAW_BUCKET", "mytube-raw-uploads")
        self.gcs_public_base_url = os.getenv(
            "GCS_PUBLIC_BASE_URL", "https://storage.googleapis.com"
        )

    def public_object_url(self, bucket: str, object_name: str) -> str:
        """Returns the public GCS URL for an object."""
        return f"{self.gcs_public_base_url}/{bucket}/{object_name}"
