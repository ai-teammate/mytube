# MYTUBE-68 — Verify sorting and tag indexes

## Objective

Verify that the composite indexes `videos_status_created`, `videos_status_views`, and
`video_tags_tag_idx` are selected by the PostgreSQL query planner for their respective
discovery queries.

## Prerequisites

- PostgreSQL accessible (see environment variables below).
- Python 3.11+ with `psycopg2` installed.

## Install dependencies

```bash
pip install psycopg2-binary pytest
```

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `DB_HOST` | PostgreSQL host | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | _(empty)_ |
| `DB_NAME` | Database name | `postgres` |
| `SSL_MODE` | SSL mode | `disable` |

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-68/test_mytube_68.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-68/test_mytube_68.py::TestSortingAndTagIndexes::test_status_created_index_used_for_recency_query PASSED
testing/tests/MYTUBE-68/test_mytube_68.py::TestSortingAndTagIndexes::test_status_views_index_used_for_popularity_query PASSED
testing/tests/MYTUBE-68/test_mytube_68.py::TestSortingAndTagIndexes::test_tag_index_used_for_tag_filter_query PASSED
```

## How it works

1. Drops all public tables and re-creates the schema from `0001_initial_schema.up.sql`.
2. Applies `0003_search_indexes.up.sql` to create the three target indexes.
3. Seeds 500+ video rows and 500+ video_tag rows, then runs `ANALYZE`.
4. Runs `EXPLAIN (FORMAT TEXT)` for each discovery query and asserts the expected
   index name appears in the plan output.
