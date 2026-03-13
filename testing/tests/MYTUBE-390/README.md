MYTUBE-390 — Thumbnail extraction failure (test)

Objective
---------
Verify that thumbnail extraction failure (error path or silent FFmpeg no-output) does NOT trigger the cleanup routine that deletes HLS manifests and segment files.

Test layers
-----------
- Layer 1: Go unit tests (no GCP required) — runs targeted regression tests in api/cmd/transcoder.
- Layer 2: GCS live state check (requires GOOGLE_APPLICATION_CREDENTIALS) — inspects gs://<GCP_HLS_BUCKET>/videos for runs that have no thumbnail.jpg but retain index.m3u8 and .ts segments.

Environment variables
---------------------
- GOOGLE_APPLICATION_CREDENTIALS: path to service account key for GCS access (optional; tests gracefully skip if absent).
- GCP_PROJECT_ID: project id used by tests (optional, read by testing.core.config.gcp_config).
- GCP_HLS_BUCKET: HLS output bucket name (default: mytube-hls-output).

Running locally
---------------
- Without GCP credentials: python -m pytest testing/tests/MYTUBE-390/test_mytube_390.py -q
- With GCP credentials set: export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json; pytest testing/tests/MYTUBE-390/test_mytube_390.py -q

Notes
-----
This README satisfies the repository architecture requirement: every test directory contains README.md and config.yaml.