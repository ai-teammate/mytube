# MYTUBE-148: Retrieve video metadata — manifest URL uses configured CDN base

## Purpose

Verifies that `GET /api/videos/:id` returns an `hls_manifest_url` that:
- Starts with the configured `CDN_BASE_URL` (e.g. `https://cdn.mytube.com/videos/...`)
- Does **not** contain `gs://` or `storage.googleapis.com` internal GCS paths

## Prerequisites

- Python 3.11+
- Go toolchain (1.21+)
- PostgreSQL 14+ (test database running and accessible)

## Environment Variables

| Variable             | Required | Default                     | Description                                      |
|----------------------|----------|-----------------------------|--------------------------------------------------|
| `CDN_BASE_URL`       | Yes      | —                           | CDN base URL (test skipped if absent)            |
| `FIREBASE_PROJECT_ID`| Yes      | —                           | Firebase project ID (test skipped if absent)     |
| `API_BINARY`         | No       | `<repo_root>/api/mytube-api`| Path to pre-built Go binary                      |
| `DB_HOST`            | No       | `localhost`                 | PostgreSQL host                                  |
| `DB_PORT`            | No       | `5432`                      | PostgreSQL port                                  |
| `DB_USER`            | No       | `testuser`                  | PostgreSQL user                                  |
| `DB_PASSWORD`        | No       | `testpass`                  | PostgreSQL password                              |
| `DB_NAME`            | No       | `mytube_test`               | PostgreSQL database name                         |
| `SSL_MODE`           | No       | `disable`                   | PostgreSQL SSL mode                              |

## How to Run

```bash
CDN_BASE_URL=https://cdn.mytube.com \
FIREBASE_PROJECT_ID=my-firebase-project \
pytest testing/tests/MYTUBE-148/test_mytube_148.py -v
```

## Expected Output (passing)

```
testing/tests/MYTUBE-148/test_mytube_148.py::TestVideoMetadataCDNManifestURL::test_status_code_is_200 PASSED
testing/tests/MYTUBE-148/test_mytube_148.py::TestVideoMetadataCDNManifestURL::test_response_body_is_valid_json PASSED
testing/tests/MYTUBE-148/test_mytube_148.py::TestVideoMetadataCDNManifestURL::test_hls_manifest_url_is_present PASSED
testing/tests/MYTUBE-148/test_mytube_148.py::TestVideoMetadataCDNManifestURL::test_hls_manifest_url_is_not_null PASSED
testing/tests/MYTUBE-148/test_mytube_148.py::TestVideoMetadataCDNManifestURL::test_hls_manifest_url_starts_with_cdn_base_url PASSED
testing/tests/MYTUBE-148/test_mytube_148.py::TestVideoMetadataCDNManifestURL::test_hls_manifest_url_does_not_contain_gcs_scheme PASSED
testing/tests/MYTUBE-148/test_mytube_148.py::TestVideoMetadataCDNManifestURL::test_hls_manifest_url_does_not_contain_storage_googleapis PASSED
testing/tests/MYTUBE-148/test_mytube_148.py::TestVideoMetadataCDNManifestURL::test_hls_manifest_url_matches_expected_cdn_url PASSED

8 passed in Xs
```

## Skip Behaviour

The entire module is skipped (not failed) when:
- `CDN_BASE_URL` is not set
- `FIREBASE_PROJECT_ID` is not set
- PostgreSQL is not reachable at the configured host/port
