# MYTUBE-174: Search videos by keyword — matching ready videos returned

## Objective

Verify that `GET /api/search?q=<keyword>` correctly performs:
- Full-text search on video titles (PostgreSQL `plainto_tsquery` over `to_tsvector`)
- Exact match on video tags (`video_tags.tag`)
- Returns **only** videos with `status = 'ready'`

## Preconditions

- A running Go API binary connected to a live PostgreSQL database.
- The database schema is applied via migrations 0001–0004 (includes search indexes).
- Test data is seeded directly via psycopg2:
  - A ready video whose title contains the keyword `"dragon"`.
  - A ready video that has the tag `"sunset"`.
  - A processing video whose title contains `"dragon"` (must NOT appear in results).

## Test Steps

1. `GET /api/search?q=dragon` → title match on a ready video.
2. `GET /api/search?q=sunset` → exact tag match on a ready video.
3. `GET /api/search?q=dragon` confirming the processing video is excluded.

## Expected Results

- Requests 1 and 2 return HTTP 200 with a non-empty JSON array containing the expected video.
- The processing video is absent from the results of request 1.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `API_BINARY` | `<repo_root>/api/mytube-api` | Path to pre-built Go API binary |
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_USER` | `testuser` | PostgreSQL user |
| `DB_PASSWORD` | `testpass` | PostgreSQL password |
| `DB_NAME` | `mytube_test` | PostgreSQL database name |
| `SSL_MODE` | `disable` | PostgreSQL SSL mode |
| `FIREBASE_PROJECT_ID` | `dummy-project` | Placeholder (search is public) |
| `RAW_UPLOADS_BUCKET` | `dummy-bucket` | Placeholder (not used by search) |

## Run

```bash
pytest testing/tests/MYTUBE-174/test_mytube_174.py -v
```
