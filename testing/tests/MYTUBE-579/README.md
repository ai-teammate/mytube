# MYTUBE-579 — Retrieve Video Recommendations

## Objective

Verify that `GET /api/videos/{id}/recommendations` returns videos sharing the same
category or at least one tag with the target video, sorted by `view_count` descending.

## Preconditions

| Video | Category   | Tags                  | view_count | Role        |
|-------|------------|-----------------------|------------|-------------|
| A     | Gaming     | rpg, open-world       | 10         | Target      |
| B     | Gaming     | —                     | 100        | Included (same category) |
| C     | Music      | rpg                   | 50         | Included (shared tag)    |
| D     | Education  | —                     | 200        | Excluded (no match)      |

## Test Layers

### Layer A — Go unit tests (always run; no DB or running API required)

Exercises the handler in-process with a stub repository.  
Tests cover: success path, empty results, repository error (HTTP 500),
unsupported HTTP method (405), invalid video ID (400), Content-Type header,
and correct field mapping for all response fields.

### Layer B — HTTP integration tests (skipped when DB is unreachable)

Seeds the four prescribed videos into a real PostgreSQL instance, starts the
compiled Go API binary, and issues the live HTTP request.  
Tests cover: HTTP 200 OK, `recommendations` array key and type, presence of
Videos B and C, absence of Video D and Video A (self-exclusion), ordering by
`view_count` DESC, and presence of all required fields in every item.

## How to Run Locally

```bash
# From repository root

# Layer A + Layer B (DB required)
pytest testing/tests/MYTUBE-579/test_mytube_579.py -v

# Layer A only (no DB needed)
pytest testing/tests/MYTUBE-579/test_mytube_579.py -v -k "GoUnit"
```

### Environment Variables

| Variable                        | Default                                         | Description                     |
|---------------------------------|-------------------------------------------------|---------------------------------|
| `API_BINARY`                    | `api/mytube-api`                                | Path to pre-built Go binary     |
| `DB_HOST`                       | `localhost`                                     | PostgreSQL host                 |
| `DB_PORT`                       | `5432`                                          | PostgreSQL port                 |
| `DB_USER`                       | `postgres`                                      | PostgreSQL user                 |
| `DB_PASSWORD`                   | *(empty)*                                       | PostgreSQL password             |
| `DB_NAME`                       | `mytube`                                        | PostgreSQL database name        |
| `SSL_MODE`                      | `disable`                                       | SSL mode for PostgreSQL         |
| `FIREBASE_PROJECT_ID`           | `ai-native-478811`                              | Firebase project ID             |
| `GOOGLE_APPLICATION_CREDENTIALS`| `testing/fixtures/mock_service_account.json`   | GCS service-account JSON path   |
| `RAW_UPLOADS_BUCKET`            | `mytube-raw-uploads`                            | GCS bucket name                 |
