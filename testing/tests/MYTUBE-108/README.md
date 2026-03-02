# MYTUBE-108 — Sign in with Google: user authenticated via Firebase and redirected

## Objective

Verify that clicking "Sign in with Google" on `/login`:
1. Calls Firebase `signInWithPopup` with a `GoogleAuthProvider`.
2. On success, the user object (with accessible ID token) is stored in the auth context.
3. The user is redirected to the home page (`/`).

## Test Type

- **Type:** Web UI (component)
- **Framework:** Jest + React Testing Library (jsdom)
- **Runner:** pytest (delegates to `npm test` in `web/`)

## Why Jest, not Playwright

Google OAuth uses a browser popup (`signInWithPopup`) that requires a real Google
account and cannot be automated in CI without mocking. The project already has Jest
configured with `@testing-library/react` and full Firebase mocking infrastructure.
The component-level test covers the same behaviour contract: button presence,
`signInWithPopup` invocation, and redirect on success.

## Prerequisites

- Node.js ≥ 18
- Python 3.10+
- `pytest` installed (`pip install pytest`)
- Run `npm install` inside `web/` at least once

## Install dependencies

```bash
cd web && npm install
pip install pytest
```

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-108/test_mytube_108.py -v
```

To run the underlying Jest suite directly:

```bash
cd web && npm test -- --testPathPatterns="__tests__/app/login/page.test.tsx" --verbose --no-coverage --forceExit
```

## Environment variables

No environment variables are required. Firebase is fully mocked in the Jest suite.

## Expected output when the test passes

```
testing/tests/MYTUBE-108/test_mytube_108.py::TestGoogleSignIn::test_google_signin_full_suite_passes PASSED

1 passed in Xs
```
