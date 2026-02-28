"""GCS configuration loaded from environment variables."""
import os


class GCSConfig:
    project_id: str
    raw_uploads_bucket: str
    credentials_path: str

    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT_ID", "")
        self.raw_uploads_bucket = os.getenv(
            "GCS_RAW_UPLOADS_BUCKET", "mytube-raw-uploads"
        )
        self.credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

    def has_credentials(self) -> bool:
        """Return True if explicit credentials file is configured."""
        return bool(self.credentials_path and os.path.isfile(self.credentials_path))

    def raw_bucket_public_url(self, object_name: str = "probe.txt") -> str:
        """Return the public GCS URL for an object in the raw-uploads bucket."""
        return (
            f"https://storage.googleapis.com/"
            f"{self.raw_uploads_bucket}/{object_name}"
        )
