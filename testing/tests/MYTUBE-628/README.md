# MYTUBE-628 — Upload avatar without authentication returns 401

## Objective

Ensure that `POST /api/me/avatar` requires valid authentication. An unauthenticated
request (no `Authorization` header) must receive HTTP 401 Unauthorized.

## Dependencies

- Python 3.x
- pytest (already in `testing/requirements.txt`)

## Environment Variables

| Variable        | Default                                                          | Description               |
|-----------------|------------------------------------------------------------------|---------------------------|
| `API_BASE_URL`  | `https://mytube-api-80693608388.us-central1.run.app`             | Base URL of the REST API  |

## Install dependencies

```bash
pip install -r testing/requirements.txt
```

## Run the test

```bash
pytest testing/tests/MYTUBE-628/test_mytube_628.py -v
```

## Expected output (passing)

```
PASSED testing/tests/MYTUBE-628/test_mytube_628.py::test_upload_avatar_without_auth_returns_401
1 passed in X.XXs
```
