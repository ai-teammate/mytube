# MYTUBE-338 — Video metadata API: 'ready' status videos must contain a non-null hls_manifest_url

## Objective

Verify the data integrity of the video metadata API: every video with status `ready` must return a non-null, non-empty, absolute HTTPS `hls_manifest_url`. The test covers both the single-video detail endpoint and the recent-videos list endpoint.

## Test Type

`api` — REST API integration tests against the deployed backend.

## Test Structure

| Test class | Description |
|---|---|
| `TestReadyVideoHlsManifestUrl` | Validates the `hls_manifest_url` contract for `ready` videos |

### Single-video assertions (`GET /api/videos/:id`)

1. `test_ready_video_status_field_is_ready` — discovered video has status `ready`
2. `test_ready_video_has_hls_manifest_url_key` — `hls_manifest_url` key is present in the response
3. `test_ready_video_hls_manifest_url_is_not_null` — value is not null
4. `test_ready_video_hls_manifest_url_is_non_empty_string` — value is a non-empty string
5. `test_ready_video_hls_manifest_url_looks_like_url` — value starts with `http://` or `https://`

### List-level assertions (`GET /api/videos/recent`)

6. `test_all_recent_ready_videos_have_non_null_hls_manifest_url` — no `ready` video in the list has a null/empty URL
7. `test_all_recent_ready_videos_hls_url_starts_with_http` — all URLs are absolute HTTP/HTTPS

## Prerequisites

- Python 3.10+
- `pytest`, `httpx` (or `requests`)
- At least one video with status `ready` in the target environment

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `API_BASE_URL` | No | Base URL of the deployed backend API. Default: `http://localhost:8080` |

## Install dependencies

```bash
pip install pytest httpx
```

## Run the tests

```bash
# Against the default local server:
pytest testing/tests/MYTUBE-338/test_mytube_338.py -v

# Against the deployed API:
API_BASE_URL=https://mytube-api-jxl6bnwdaa-uc.a.run.app pytest testing/tests/MYTUBE-338/test_mytube_338.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-338/test_mytube_338.py::TestReadyVideoHlsManifestUrl::test_ready_video_status_field_is_ready PASSED
testing/tests/MYTUBE-338/test_mytube_338.py::TestReadyVideoHlsManifestUrl::test_ready_video_has_hls_manifest_url_key PASSED
testing/tests/MYTUBE-338/test_mytube_338.py::TestReadyVideoHlsManifestUrl::test_ready_video_hls_manifest_url_is_not_null PASSED
testing/tests/MYTUBE-338/test_mytube_338.py::TestReadyVideoHlsManifestUrl::test_ready_video_hls_manifest_url_is_non_empty_string PASSED
testing/tests/MYTUBE-338/test_mytube_338.py::TestReadyVideoHlsManifestUrl::test_ready_video_hls_manifest_url_looks_like_url PASSED
testing/tests/MYTUBE-338/test_mytube_338.py::TestReadyVideoHlsManifestUrl::test_all_recent_ready_videos_have_non_null_hls_manifest_url PASSED
testing/tests/MYTUBE-338/test_mytube_338.py::TestReadyVideoHlsManifestUrl::test_all_recent_ready_videos_hls_url_starts_with_http PASSED
7 passed
```
