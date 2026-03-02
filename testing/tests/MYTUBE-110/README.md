# MYTUBE-110 — Access protected /settings page while unauthenticated: user redirected to login

## What this test verifies

Verifies that the `/settings` protected page is inaccessible to unauthenticated users and that the application automatically redirects them to `/login` via the shared React `AuthContext`:

- `router.replace("/login")` is called when an unauthenticated user (`user=null`, `loading=false`) renders `/settings`.
- No premature redirect is fired while the auth state is still loading (`loading=true`).
- An authenticated user on `/settings` is **not** redirected to `/login`.

## How it works

Component-level unit test using Jest + React Testing Library (jsdom). The `useAuth` hook is mocked to simulate an unauthenticated, fully-resolved auth state (`user: null, loading: false`). `useRouter` from `next/navigation` is mocked to capture redirect calls. No real network calls or browser sessions are involved.

## Dependencies

**Node.js / npm** (already present in this repo):

```bash
cd web && npm install
```

## Environment variables

No environment variables are required. Auth state and the Next.js router are fully mocked.

## How to run

From the repository root:

```bash
cd web && npx jest \
  --roots "$(pwd)" "../testing/tests/MYTUBE-110" \
  --testPathPatterns="MYTUBE-110" \
  --no-coverage \
  --modulePaths="$(pwd)/node_modules"
```

## Expected output when the test passes

```
PASS ../testing/tests/MYTUBE-110/test_mytube_110.test.tsx
  MYTUBE-110 — /settings redirect for unauthenticated user
    ✓ redirects unauthenticated user from /settings to /login
    ✓ does not redirect while auth state is still loading
    ✓ does not redirect an authenticated user away from /settings

Test Suites: 1 passed, 1 total
Tests:       3 passed, 3 total
```
