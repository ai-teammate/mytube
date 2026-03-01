# MYTUBE-66 — Search Index Migration Test

Verifies that migration `0003_search_indexes.up.sql` correctly creates all
required full-text search, tag, and performance indexes on the `videos` and
`video_tags` tables.

## What is tested

1. Migration 0001 applied as precondition (clean schema).
2. Migration `0003_search_indexes.up.sql` applied.
3. All four indexes are present in `pg_indexes`:
   - `videos_title_fts` — GIN index for full-text search on `videos.title`
   - `video_tags_tag_idx` — B-tree index on `video_tags.tag`
   - `videos_status_created` — composite B-tree on `videos(status, created_at DESC)`
   - `videos_status_views` — composite B-tree on `videos(status, view_count DESC)`
4. Each index uses the correct access method (GIN or B-tree).
5. Down migration removes all four indexes cleanly.

## Note on migration numbering

The test ticket refers to this migration as `0002_search_indexes`. In the
repository it is `0003_search_indexes.up.sql`. The test targets the actual
file on disk.

## Prerequisites

- Python 3.10+
- PostgreSQL 14+ running (or accessible via `DB_HOST`)
- `psycopg2-binary` and `pytest` installed

## Install dependencies

```bash
pip install psycopg2-binary pytest
```

## Environment variables

| Variable    | Default        | Description              |
|-------------|----------------|--------------------------|
| `DB_HOST`   | `localhost`    | PostgreSQL host          |
| `DB_PORT`   | `5432`         | PostgreSQL port          |
| `DB_USER`   | `testuser`     | Database user            |
| `DB_PASSWORD` | `testpass`   | Database password        |
| `DB_NAME`   | `mytube_test`  | Target database          |
| `SSL_MODE`  | `disable`      | SSL mode                 |

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-66/test_mytube_66.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-66/test_mytube_66.py::TestSearchIndexesCreated::test_index_exists[videos_title_fts-videos-gin] PASSED
testing/tests/MYTUBE-66/test_mytube_66.py::TestSearchIndexesCreated::test_index_exists[video_tags_tag_idx-video_tags-btree] PASSED
testing/tests/MYTUBE-66/test_mytube_66.py::TestSearchIndexesCreated::test_index_exists[videos_status_created-videos-btree] PASSED
testing/tests/MYTUBE-66/test_mytube_66.py::TestSearchIndexesCreated::test_index_exists[videos_status_views-videos-btree] PASSED
testing/tests/MYTUBE-66/test_mytube_66.py::TestSearchIndexesCreated::test_index_access_method[videos_title_fts-videos-gin] PASSED
testing/tests/MYTUBE-66/test_mytube_66.py::TestSearchIndexesCreated::test_index_access_method[video_tags_tag_idx-video_tags-btree] PASSED
testing/tests/MYTUBE-66/test_mytube_66.py::TestSearchIndexesCreated::test_index_access_method[videos_status_created-videos-btree] PASSED
testing/tests/MYTUBE-66/test_mytube_66.py::TestSearchIndexesCreated::test_index_access_method[videos_status_views-videos-btree] PASSED
testing/tests/MYTUBE-66/test_mytube_66.py::TestSearchIndexesCount::test_all_four_indexes_present PASSED
testing/tests/MYTUBE-66/test_mytube_66.py::TestDownMigration::test_down_migration_removes_indexes PASSED
================================================= 10 passed in X.XXs =================================================
```
