"""GCP infrastructure configuration loaded from environment variables."""
import os


class GcpConfig:
    def __init__(self) -> None:
        self.project_id: str = os.environ.get("GCP_PROJECT_ID", "")
        self.region: str = os.environ.get("GCP_REGION", "us-central1")
        self.raw_bucket: str = os.environ.get("GCP_RAW_BUCKET", "mytube-raw-uploads")
        self.hls_bucket: str = os.environ.get("GCP_HLS_BUCKET", "mytube-hls-output")
        self.transcoder_job: str = os.environ.get("GCP_TRANSCODER_JOB", "mytube-transcoder")
        self.transcoder_sa: str = os.environ.get("GCP_TRANSCODER_SA", "mytube-transcoder")
