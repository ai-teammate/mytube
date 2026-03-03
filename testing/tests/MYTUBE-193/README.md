# MYTUBE-193: Visual distinction of status badges — processing and failed states differentiated

## Overview

Verifies that status badges on the `/dashboard` page are visually distinct for
`processing` and `failed` transcoding states (different Tailwind color classes).

The source code (`web/src/app/dashboard/page.tsx`) applies:
- `bg-yellow-100 text-yellow-800` for **processing**
- `bg-red-100 text-red-800` for **failed**

## Test modes

| Mode | Conditions | What runs |
|------|------------|-----------|
| **Live** | `FIREBASE_TEST_EMAIL` + `FIREBASE_TEST_PASSWORD` + DB reachable + app reachable | Login → seed videos → real dashboard |
| **Fixture** | Fallback (always available) | Local HTML server with pre-styled badges |

## Install dependencies

```bash
pip install playwright pytest psycopg2-binary
playwright install chromium
```

## Run the test

```bash
cd <repo-root>
python -m pytest testing/tests/MYTUBE-193/test_mytube_193.py -v
```

## Environment variables

| Variable | Required for | Default |
|----------|-------------|---------|
| `APP_URL` / `WEB_BASE_URL` | Live mode | `https://ai-teammate.github.io/mytube` |
| `API_BASE_URL` | Live mode | `http://localhost:8081` |
| `FIREBASE_TEST_EMAIL` | Live mode | — |
| `FIREBASE_TEST_PASSWORD` | Live mode | — |
| `FIREBASE_TEST_UID` | Live mode DB seeding | — |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | Live mode | defaults |
| `PLAYWRIGHT_HEADLESS` | Both | `true` |

## Expected output when passing

```
PASSED testing/tests/MYTUBE-193/test_mytube_193.py::TestStatusBadgeVisualDistinction::test_processing_badge_is_present
PASSED testing/tests/MYTUBE-193/test_mytube_193.py::TestStatusBadgeVisualDistinction::test_failed_badge_is_present
PASSED testing/tests/MYTUBE-193/test_mytube_193.py::TestStatusBadgeVisualDistinction::test_processing_badge_uses_yellow_color_class
PASSED testing/tests/MYTUBE-193/test_mytube_193.py::TestStatusBadgeVisualDistinction::test_failed_badge_uses_red_color_class
PASSED testing/tests/MYTUBE-193/test_mytube_193.py::TestStatusBadgeVisualDistinction::test_processing_and_failed_badges_have_different_color_classes
```
