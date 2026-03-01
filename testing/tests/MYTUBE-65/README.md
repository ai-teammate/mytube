# MYTUBE-65 — Authenticate with malformed Authorization header

Verifies that the `RequireAuth` middleware rejects requests whose `Authorization`
header does not follow the `Bearer <token>` format, returning HTTP 401 in all
three malformed-header scenarios.

## Prerequisites

- **Go toolchain** (1.21+) — required to build the test server
- **Python 3.9+**
- **pytest** — `pip install pytest`

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TEST_SERVER_BINARY` | `testing/testserver/testserver` | Path to a pre-built testserver binary. If unset and the binary is absent, the test builds it automatically. |

## Build the test server manually

```bash
cd testing/testserver
go build -o testserver .
```

The binary is a stdlib-only Go HTTP server — no external Go dependencies.

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-65/test_mytube_65.py -v
```

## Expected output when the test passes

```
testing/tests/MYTUBE-65/test_mytube_65.py::TestMalformedAuthorizationHeader::test_basic_scheme_returns_401 PASSED
testing/tests/MYTUBE-65/test_mytube_65.py::TestMalformedAuthorizationHeader::test_bearer_without_token_returns_401 PASSED
testing/tests/MYTUBE-65/test_mytube_65.py::TestMalformedAuthorizationHeader::test_token_without_bearer_prefix_returns_401 PASSED

3 passed in ...s
```

## How it works

A standalone Go test server (`testing/testserver/`) is started as a subprocess.
It implements the identical `bearerToken()` / `requireAuth` logic from
`api/internal/middleware/auth.go` without requiring Firebase credentials or a
live database. The server exposes:

- `GET /health` — always 200 (readiness probe)
- `GET /api/me` — protected by `requireAuth`; returns 401 for any malformed header

Three requests are sent via `ApiProcessService`:

| # | Header value | Expected |
|---|---|---|
| 1 | `Authorization: Basic dXNlcjpwYXNz` | 401 |
| 2 | `Authorization: Bearer ` (empty token) | 401 |
| 3 | `Authorization: eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.fake` (no scheme) | 401 |
