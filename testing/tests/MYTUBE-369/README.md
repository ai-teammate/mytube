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
This test reads required configuration from environment variables:
- TEST_GCP_PROJECT: GCP project id to use for invocations
- TEST_OUTPUT_BUCKET: GCS bucket used to inspect HLS output

Example ffmpeg snippet used to generate the silent MP4 (CI-safe):

```bash
# Minimal silent MP4 (1s, 1x1 pixel)
ffmpeg -y -f lavfi -i color=c=black:s=1x1:d=1 -c:v libx264 -t 1 -pix_fmt yuv420p /tmp/silent.mp4
```

Notes
-----
- Do not hardcode GCP project or bucket names in the test. Use env vars documented above.
- CI images should include ffmpeg and required Python packages, or declare them in test metadata.
