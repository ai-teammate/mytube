# MYTUBE-289 — Retrieve video metadata with no category — category_id is null in response

## Objective

Verify that the `GET /api/videos/:id` endpoint correctly returns `null` for
`category_id` when no category is assigned to the video.

## Preconditions

- At least one video must exist in the deployed environment with `category_id` set to `null`.
- The `API_BASE_URL` environment variable must point to the deployed instance (or the
  default `http://localhost:8080` must be reachable).

## Test Cases

| # | Test | Description |
|---|------|-------------|
| 1 | `test_status_code_is_200` | `GET /api/videos/:id` returns HTTP 200 OK for an uncategorised video |
| 2 | `test_response_body_contains_category_id_field` | Response JSON object includes the `category_id` field |
| 3 | `test_category_id_is_null` | `category_id` value is `null` |

## Environment Variables

| Variable      | Required | Description                                                      |
|---------------|----------|------------------------------------------------------------------|
| `API_BASE_URL`| No       | Base URL of the deployed API. Default: `http://localhost:8080`   |
| `API_HOST`    | No       | API host (used when `API_BASE_URL` is absent)                    |
| `API_PORT`    | No       | API port (used when `API_BASE_URL` is absent)                    |

## Running the Tests

```bash
pytest testing/tests/MYTUBE-289/ -v
```

If no video with `category_id = null` is found in the environment the tests are
skipped automatically with an explanatory message.
