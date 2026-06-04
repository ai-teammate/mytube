# MYTUBE-661 — Hero and Header unit tests pass with new copy

## Objective

Verify that the Jest unit tests for `HeroSection`, `SiteHeader`, and the home
`page` component all pass with the updated string matchers.

## Prerequisites

Node.js ≥ 18 and project dependencies installed:

```bash
cd web
npm install
```

## Run the test

From the repository root:

```bash
python testing/tests/MYTUBE-661/test_mytube_661.py
```

Or run the Jest suite directly:

```bash
cd web
npx jest --no-coverage src/__tests__/components/HeroSection.test.tsx \
                       src/__tests__/components/SiteHeader.test.tsx \
                       src/__tests__/app/home/page.test.tsx
```

## Expected output

All three Jest test suites report `PASS` and the script exits with code `0`.

## Environment variables

None required — tests use mocked dependencies only.
