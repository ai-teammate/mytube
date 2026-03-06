# MYTUBE-268 — Request videos for non-existent category ID

Automates the test case: verify that the API correctly handles requests for 
videos in a non-existent category by returning HTTP 200 with an empty array, 
rather than an error or unfiltered results.

## What is tested

| Layer | Endpoint |
|-------|----------|
| API   | `GET /api/videos?category_id=99999&limit=20` |

## Dependencies

```
pip install pytest
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `http://localhost:8080` | Backend API base URL |

No database access, no authentication, no secrets required — the test runs 
entirely against the deployed public API.

## Run

From the repository root:

```bash
python -m pytest testing/tests/MYTUBE-268/test_mytube_268.py -v
```

### Example with explicit API URL

```bash
API_BASE_URL=https://mytube-api-80693608388.us-central1.run.app \
python -m pytest testing/tests/MYTUBE-268/test_mytube_268.py -v
```

## Expected output when passing

```
PASSED testing/tests/MYTUBE-268/test_mytube_268.py::TestNonexistentCategoryVideos::test_status_code_is_200
PASSED testing/tests/MYTUBE-268/test_mytube_268.py::TestNonexistentCategoryVideos::test_response_body_is_empty_array
PASSED testing/tests/MYTUBE-268/test_mytube_268.py::TestNonexistentCategoryVideos::test_no_error_message
```
