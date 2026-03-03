# MYTUBE-177 — Search pagination: offset and limit correctly slice results

## What this test verifies

Sends two consecutive GET requests to `/api/search` with the same keyword but
different `offset` values, and asserts that:

1. Request 1 (`limit=20&offset=0`) returns **exactly 20 items**.
2. Request 2 (`limit=20&offset=20`) returns **exactly 5 items**.
3. **No video ID appears in both result sets** (no overlap).
4. Together the two pages cover all 25 seeded videos.

---

## Dependencies

- Python 3.11+
- `psycopg2-binary`
- `pytest`
- Go toolchain (only if the API binary is not pre-built)

Install Python dependencies:

```bash
pip install pytest psycopg2-binary
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `API_BINARY` | `api/mytube-api` (repo root) | Path to the pre-built Go API binary |
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_USER` | `testuser` | PostgreSQL user |
| `DB_PASSWORD` | `testpass` | PostgreSQL password |
| `DB_NAME` | `mytube_test` | PostgreSQL database name |
| `SSL_MODE` | `disable` | PostgreSQL SSL mode |

> **Note:** `FIREBASE_PROJECT_ID` is **not required** — the `/api/search` endpoint
> is unauthenticated and does not need Firebase token verification.

---

## How to run

From the repository root:

```bash
pytest testing/tests/MYTUBE-177/test_mytube_177.py -v
```

---

## Expected output (passing)

```
testing/tests/MYTUBE-177/test_mytube_177.py::TestSearchPagination::test_page_one_status_is_200 PASSED
testing/tests/MYTUBE-177/test_mytube_177.py::TestSearchPagination::test_page_one_returns_20_results PASSED
testing/tests/MYTUBE-177/test_mytube_177.py::TestSearchPagination::test_page_one_all_titles_contain_keyword PASSED
testing/tests/MYTUBE-177/test_mytube_177.py::TestSearchPagination::test_page_two_status_is_200 PASSED
testing/tests/MYTUBE-177/test_mytube_177.py::TestSearchPagination::test_page_two_returns_5_results PASSED
testing/tests/MYTUBE-177/test_mytube_177.py::TestSearchPagination::test_page_two_all_titles_contain_keyword PASSED
testing/tests/MYTUBE-177/test_mytube_177.py::TestSearchPagination::test_no_overlap_between_pages PASSED
testing/tests/MYTUBE-177/test_mytube_177.py::TestSearchPagination::test_combined_results_cover_all_25_videos PASSED

8 passed in Xs
```
