MYTUBE-369 — Transcode video with no audio

Purpose
-------
Integration test that generates a silent (no-audio) MP4, invokes the Cloud Run transcoder job, and verifies HLS output was produced in the configured GCS bucket.

Requirements
------------
- ffmpeg available on PATH (or provided by CI image)
- Python packages: google-cloud-storage (used only when running against real GCS)

Configuration
-------------
This test reads required configuration from environment variables (see testing/core/config/gcp_config.py):
- GCP_PROJECT_ID: GCP project id to use for invocations
- GCP_REGION: region of Cloud Run Job (default: us-central1)
- GCP_RAW_BUCKET: raw uploads bucket (default: mytube-raw-uploads)
- GCP_HLS_BUCKET: HLS output bucket (default: mytube-hls-output)
- GCP_TRANSCODER_JOB: Cloud Run Job name (default: mytube-transcoder)
- GOOGLE_APPLICATION_CREDENTIALS: path to service account JSON (or use ADC)

Example ffmpeg snippet used to generate the silent MP4 (CI-safe):

```bash
# Minimal silent MP4 (1s, 1x1 pixel)
ffmpeg -y -f lavfi -i color=c=black:s=1x1:d=1 -c:v libx264 -t 1 -pix_fmt yuv420p /tmp/silent.mp4
```

Notes
-----
- Do not hardcode GCP project or bucket names in the test. Use env vars documented above.
- Declare runtime dependencies (ffmpeg, google-cloud-storage) in the test metadata (config.yaml) or provide a CI image that includes them; avoid installing heavy packages ad-hoc at runtime.
