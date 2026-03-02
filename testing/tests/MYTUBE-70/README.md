# MYTUBE-70 — Rollback search index migration

Verifies that running the `0003_search_indexes` **down** migration drops all four
search-specific indexes while leaving the `videos` and `video_tags` tables and
their data records completely intact.

## Dependencies

- Python 3.11+
- `psycopg2-binary`
- `pytest`
- A running PostgreSQL instance reachable with the env vars below

Install:

```bash
pip install psycopg2-binary pytest
```

## Environment variables

| Variable      | Default       | Description                     |
|---------------|---------------|---------------------------------|
| `DB_HOST`     | `localhost`   | PostgreSQL host                 |
| `DB_PORT`     | `5432`        | PostgreSQL port                 |
| `DB_USER`     | `testuser`    | Database user                   |
| `DB_PASSWORD` | `testpass`    | Database password               |
| `DB_NAME`     | `mytube_test` | Database name                   |
| `SSL_MODE`    | `disable`     | SSL mode (`disable` / `require`)|

## How to run

From the repository root:

```bash
pytest testing/tests/MYTUBE-70/test_mytube_70.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-70/test_mytube_70.py::TestSearchIndexesDropped::test_index_is_dropped[videos_title_fts] PASSED
testing/tests/MYTUBE-70/test_mytube_70.py::TestSearchIndexesDropped::test_index_is_dropped[video_tags_tag_idx] PASSED
testing/tests/MYTUBE-70/test_mytube_70.py::TestSearchIndexesDropped::test_index_is_dropped[videos_status_created] PASSED
testing/tests/MYTUBE-70/test_mytube_70.py::TestSearchIndexesDropped::test_index_is_dropped[videos_status_views] PASSED
testing/tests/MYTUBE-70/test_mytube_70.py::TestTableDataPreserved::test_videos_table_still_exists PASSED
testing/tests/MYTUBE-70/test_mytube_70.py::TestTableDataPreserved::test_video_tags_table_still_exists PASSED
testing/tests/MYTUBE-70/test_mytube_70.py::TestTableDataPreserved::test_videos_row_count_unchanged PASSED
testing/tests/MYTUBE-70/test_mytube_70.py::TestTableDataPreserved::test_video_tags_row_count_unchanged PASSED

8 passed
```
