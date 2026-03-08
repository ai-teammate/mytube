# MYTUBE-378 — GCS Deletion Safety Check

Verifies that the GCS deletion logic in `api/internal/handler/manage_video.go`
is restricted to video-specific prefixes and never targets arbitrary paths.

## What is tested

- **Step 1 — Static inspection** of `manage_video.go` for safety constraints:
  - `parseGCSPrefix` constructs the deletion prefix as `videos/<videoID>/` (not from the manifest URL)
  - Raw paths starting with `videos/` are rejected (HLS-path contamination guard)
  - Raw-file deletion uses `paths.RawPath` directly from the DB
  - HLS deletion routes through `parseGCSPrefix()` before calling `DeletePrefix`
  - `DeletePrefix` is never called with the raw `HLSManifestPath` value
  - Non-`gs://` manifest URLs are rejected (`parseGCSPrefix` returns `ok=false`)
  - Empty bucket names are rejected

- **Step 2 — Go unit tests** with a stub `ObjectDeleter`:
  - `TestDeleteVideo_GCSCleanup_DeletesRawAndHLS` — validates exact paths passed to `DeleteObject`/`DeletePrefix`
  - `TestDeleteVideo_GCSCleanupDisabled_DoesNotDelete` — no GCS calls when `DELETE_ON_VIDEO_DELETE=false`

## Running

```bash
REPO_ROOT=/path/to/repo pytest testing/tests/MYTUBE-378/test_mytube_378.py -v
```

## Environment variables

- `REPO_ROOT` — path to repository root (auto-detected relative to this file if not set)
