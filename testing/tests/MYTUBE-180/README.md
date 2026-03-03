# MYTUBE-180: Retrieve all categories — API returns full list for navigation

Verifies that `GET /api/categories` returns a JSON array where every element contains `id` (integer) and `name` (string) fields.

## Dependencies

```bash
pip install pytest
```

No additional packages required — the test uses only the Python standard library for HTTP calls.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `https://mytube-api-80693608388.us-central1.run.app` | Base URL of the deployed API |

## Run

```bash
cd <repo-root>
pytest testing/tests/MYTUBE-180/test_mytube_180.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-180/test_mytube_180.py::TestGetCategoriesEndpoint::test_status_code_is_200 PASSED
testing/tests/MYTUBE-180/test_mytube_180.py::TestGetCategoriesEndpoint::test_response_body_is_json_array PASSED
testing/tests/MYTUBE-180/test_mytube_180.py::TestGetCategoriesEndpoint::test_response_is_non_empty PASSED
testing/tests/MYTUBE-180/test_mytube_180.py::TestGetCategoriesEndpoint::test_every_category_has_id_field PASSED
testing/tests/MYTUBE-180/test_mytube_180.py::TestGetCategoriesEndpoint::test_every_category_id_is_integer PASSED
testing/tests/MYTUBE-180/test_mytube_180.py::TestGetCategoriesEndpoint::test_every_category_has_name_field PASSED
testing/tests/MYTUBE-180/test_mytube_180.py::TestGetCategoriesEndpoint::test_every_category_name_is_non_empty_string PASSED
testing/tests/MYTUBE-180/test_mytube_180.py::TestGetCategoriesEndpoint::test_no_extra_unexpected_fields PASSED
```
