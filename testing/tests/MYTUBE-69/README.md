# MYTUBE-69 — Search Migration Idempotency Test

Verifies that `0003_search_indexes.up.sql` can be applied twice without raising
"index already exists" errors, confirming that every `CREATE INDEX IF NOT EXISTS`
statement is genuinely idempotent.

## What is tested

1. Applying the migration SQL once succeeds (indexes created).
2. Applying the same migration SQL a second time also succeeds — no exception.
3. All four indexes are present and intact after both applications:
   - `videos_title_fts` (GIN, full-text search on video titles)
   - `video_tags_tag_idx` (B-tree, tag filtering)
   - `videos_status_created` (B-tree composite, recency queries)
   - `videos_status_views` (B-tree composite, popularity queries)

## Prerequisites

- Python 3.10+
- PostgreSQL 14+ running locally (or via `DB_HOST`)
- `psycopg2-binary` and `pytest` packages

## Install dependencies

```bash
pip install psycopg2-binary pytest
```

## Environment variables

| Variable      | Default        | Description                              |
|---------------|----------------|------------------------------------------|
| `DB_HOST`     | `localhost`    | PostgreSQL host                          |
| `DB_PORT`     | `5432`         | PostgreSQL port                          |
| `DB_USER`     | `testuser`     | Database user                            |
| `DB_PASSWORD` | `testpass`     | Database password                        |
| `DB_NAME`     | `mytube_test`  | Target database (must exist and be empty)|
| `SSL_MODE`    | `disable`      | SSL mode                                 |

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-69/test_mytube_69.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-69/test_mytube_69.py::TestSearchMigrationIdempotency::test_first_and_second_application_raise_no_exception PASSED
testing/tests/MYTUBE-69/test_mytube_69.py::TestSearchIndexesExistAfterDoubleApplication::test_index_exists[videos_title_fts] PASSED
testing/tests/MYTUBE-69/test_mytube_69.py::TestSearchIndexesExistAfterDoubleApplication::test_index_exists[video_tags_tag_idx] PASSED
testing/tests/MYTUBE-69/test_mytube_69.py::TestSearchIndexesExistAfterDoubleApplication::test_index_exists[videos_status_created] PASSED
testing/tests/MYTUBE-69/test_mytube_69.py::TestSearchIndexesExistAfterDoubleApplication::test_index_exists[videos_status_views] PASSED
testing/tests/MYTUBE-69/test_mytube_69.py::TestSearchIndexProperties::test_videos_title_fts_is_gin PASSED
testing/tests/MYTUBE-69/test_mytube_69.py::TestSearchIndexProperties::test_video_tags_tag_idx_is_btree PASSED
testing/tests/MYTUBE-69/test_mytube_69.py::TestSearchIndexProperties::test_videos_status_created_is_btree PASSED
testing/tests/MYTUBE-69/test_mytube_69.py::TestSearchIndexProperties::test_videos_status_views_is_btree PASSED
================================================== 9 passed in X.XXs ==================================================
```
