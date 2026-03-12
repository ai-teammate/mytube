# MYTUBE-496 — Auth Routes GitHub Pages Base Path: Layout Wrappers Excluded

## Objective

Verify that the AppShell layout components (`.shell`, `.page-wrap`) and their associated
styles are correctly excluded when authentication routes (`/login/`, `/register/`) are
accessed under the GitHub Pages base path (`/mytube`) with trailing slashes.

## Background

Bug MYTUBE-495 identified that `AppShell.tsx` compared `pathname` against hardcoded
`AUTH_ROUTES` (`["/login", "/register"]`) using an exact match. Under the GitHub Pages
base path (`/mytube`), `usePathname()` returns `/mytube/login/` and `/mytube/register/`,
which never matched, so the shell wrapper was incorrectly rendered on auth pages.

The fix normalises the pathname by stripping the `NEXT_PUBLIC_BASE_PATH` prefix and
trailing slash before the auth-route check.

## Steps

1. Navigate to `https://ai-teammate.github.io/mytube/login/`
2. Inspect the DOM — assert no `.shell` element is present
3. Inspect the DOM — assert no `.page-wrap` element is present
4. Verify that no elements (excluding `.auth-card`) have `max-width:1320px` or `border-radius:24px` shell styles
5. Repeat steps 1–4 for `https://ai-teammate.github.io/mytube/register/`

## Expected Result

Neither `.shell` nor `.page-wrap` is present in the DOM on either auth page. The
shell-based styles (rounded corners and max-width) are not applied to the page
containers, ensuring auth pages use their dedicated standalone layout.

## Run Locally

```bash
pytest testing/tests/MYTUBE-496/test_mytube_496.py -v
```

## Environment

- **URL**: `https://ai-teammate.github.io/mytube`
- **Browser**: Chromium (headless)
- **Framework**: Playwright (Python)
