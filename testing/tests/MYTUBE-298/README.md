# MYTUBE-298 — OPTIONS preflight for /api/me/videos — 200 OK and CORS headers returned

Verifies that the API server responds to CORS OPTIONS preflight requests for
`/api/me/videos` with HTTP 200 and the required `Access-Control-*` headers,
and that the request is not blocked by authentication middleware.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `http://localhost:8080` | Base URL of the deployed API |
| `API_HOST` | — | API host (used when `API_BASE_URL` is absent) |
| `API_PORT` | — | API port (used when `API_BASE_URL` is absent) |

## Running the test

```bash
pytest testing/tests/MYTUBE-298/
```
