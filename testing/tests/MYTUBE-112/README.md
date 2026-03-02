# MYTUBE-112 — Login with incorrect credentials: error message displayed and access denied

## What this test verifies

Verifies that the login page (`/login`) handles Firebase authentication failures gracefully:

- A clear error message is rendered in a `role="alert"` element when incorrect credentials are submitted.
- The user is **not** redirected to `/` on failure.
- Covers Firebase error codes: `auth/invalid-credential`, `auth/user-not-found`, `auth/wrong-password`, `auth/too-many-requests`, `auth/popup-closed-by-user`, and generic/unknown errors.

## How it works

This Python pytest module invokes the existing Jest + React Testing Library suite for the login page component (`web/src/__tests__/app/login/page.test.tsx`), scoped to the authentication-failure test cases. Firebase and Next.js router are mocked; no real network calls are made.

## Dependencies

**Node.js / npm** (already present in this repo):

```bash
cd web && npm install
```

**Python** (for the pytest wrapper):

```bash
pip install pytest
```

## How to run

From the repository root:

```bash
pytest testing/tests/MYTUBE-112/test_mytube_112.py -v
```

Or run the underlying Jest suite directly:

```bash
cd web
npm test -- --testPathPatterns "login/page" \
  --testNamePattern "shows error message on sign-in failure|shows error message for too-many-requests|shows generic error|shows error on Google sign-in popup closed" \
  --no-coverage --forceExit
```

## Environment variables

No environment variables are required. Firebase and the Next.js router are fully mocked in the Jest suite.

## Expected output when the test passes

```
testing/tests/MYTUBE-112/test_mytube_112.py::TestLoginIncorrectCredentials::test_login_failure_shows_error_message_and_denies_access PASSED
```

The underlying Jest run will also print something like:

```
PASS src/__tests__/app/login/page.test.tsx
  LoginPage
    ✓ shows error message on sign-in failure with invalid-credential code
    ✓ shows error message for too-many-requests code
    ✓ shows generic error for unknown error code
    ✓ shows generic error for non-object errors
    ✓ shows error on Google sign-in popup closed
```
