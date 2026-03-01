# MYTUBE-67 — Verify title full-text search index (GIN / English)

Automated test for the Jira ticket **MYTUBE-67**.

Confirms that the GIN index `videos_title_fts` created by migration
`0003_search_indexes` is correctly utilised for English full-text search
queries on the `videos.title` column.

---

## What is tested

| # | Assertion |
|---|-----------|
| 1 | Index `videos_title_fts` exists on the `videos` table |
| 2 | Index type is GIN |
| 3 | Index uses the `english` text-search configuration |
| 4 | FTS query returns exactly the rows whose titles match the search term |
| 5 | FTS query excludes non-matching rows |
| 6 | All matching titles are present in the result set |
| 7 | `EXPLAIN ANALYZE` plan references `videos_title_fts` |
| 8 | Plan contains `Bitmap Index Scan` or `Index Scan` |
| 9 | Plan does not use `Seq Scan` (skipped for small datasets < 100 rows) |

---

## Dependencies

```
psycopg2-binary
pytest
```

Install:

```bash
pip install psycopg2-binary pytest
```

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_USER` | `testuser` | Database user |
| `DB_PASSWORD` | `testpass` | Database password |
| `DB_NAME` | `mytube_test` | Database name |
| `DB_SSLMODE` | `disable` | SSL mode |

---

## How to run

From the repository root:

```bash
pytest testing/tests/MYTUBE-67/test_mytube_67.py -v
```

---

## Expected output when the test passes

```
testing/tests/MYTUBE-67/test_mytube_67.py::TestGINIndexExists::test_videos_title_fts_index_exists PASSED
testing/tests/MYTUBE-67/test_mytube_67.py::TestGINIndexExists::test_videos_title_fts_is_gin PASSED
testing/tests/MYTUBE-67/test_mytube_67.py::TestGINIndexExists::test_videos_title_fts_uses_english_config PASSED
testing/tests/MYTUBE-67/test_mytube_67.py::TestFullTextSearchReturnsRelevantRecords::test_fts_query_returns_matching_rows PASSED
testing/tests/MYTUBE-67/test_mytube_67.py::TestFullTextSearchReturnsRelevantRecords::test_fts_query_excludes_non_matching_rows PASSED
testing/tests/MYTUBE-67/test_mytube_67.py::TestFullTextSearchReturnsRelevantRecords::test_fts_query_returns_all_matching_titles PASSED
testing/tests/MYTUBE-67/test_mytube_67.py::TestQueryPlanUsesGINIndex::test_plan_references_videos_title_fts_index PASSED
testing/tests/MYTUBE-67/test_mytube_67.py::TestQueryPlanUsesGINIndex::test_plan_uses_index_scan_or_bitmap_index_scan PASSED
testing/tests/MYTUBE-67/test_mytube_67.py::TestQueryPlanUsesGINIndex::test_plan_does_not_use_seq_scan_for_fts SKIPPED (small dataset)

9 passed (or 8 passed, 1 skipped)
```
