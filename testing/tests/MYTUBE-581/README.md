# MYTUBE-581: Recommendation API result limit — response contains no more than 8 videos

## Objective

Verify that `GET /api/videos/{id}/recommendations` enforces a maximum limit of 8 results,
even when more than 8 eligible videos share the same category as the target video.

## Preconditions

- PostgreSQL database is running and accessible.
- The Go API binary is compiled or available at `api/mytube-api`.
- `FIREBASE_PROJECT_ID` is set — the test module is skipped when absent.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `FIREBASE_PROJECT_ID` | ✅ Yes | — | Firebase project ID used by the Go API server. |
| `GOOGLE_APPLICATION_CREDENTIALS` | No | `testing/fixtures/mock_service_account.json` | Path to service-account JSON. |
| `API_BINARY` | No | `api/mytube-api` | Path to the pre-built Go binary. |
| `RAW_UPLOADS_BUCKET` | No | `mytube-raw-uploads` | GCS bucket name passed to the API server. |
| `DB_HOST` | No | `localhost` | PostgreSQL host. |
| `DB_PORT` | No | `5432` | PostgreSQL port. |
| `DB_USER` | No | `testuser` | PostgreSQL user. |
| `DB_PASSWORD` | No | `testpass` | PostgreSQL password. |
| `DB_NAME` | No | `mytube_test` | PostgreSQL database name. |
| `SSL_MODE` | No | `disable` | PostgreSQL SSL mode. |

## Test Steps

1. Seed 1 target video and 11 candidate videos (all `status='ready'`, `hls_manifest_path` set, same `category_id`) into the database.
2. Start the Go API binary on port 18581 via `ApiProcessService`.
3. Call `GET /api/videos/{target_id}/recommendations` via `VideoApiService.get_recommendations()`.
4. Assert the response contains exactly 8 items.
5. Assert each item contains the required fields: `id`, `title`, `view_count`, `uploader_username`, `created_at`.
6. Assert the target video is not included in its own recommendations.

## Expected Result

- Exactly 8 video objects are returned (the configured hard limit).
- All required fields are present in each item.
- The target video is excluded from the recommendations list.

## How to Run

```bash
# From the repository root
FIREBASE_PROJECT_ID=<your-project-id> \
  pytest testing/tests/MYTUBE-581/test_mytube_581.py -v
```

## Test Files

| File | Purpose |
|---|---|
| `test_mytube_581.py` | API integration test implementation |
| `config.yaml` | Test metadata (type, framework, dependencies) |
