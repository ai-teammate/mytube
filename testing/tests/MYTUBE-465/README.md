# MYTUBE-465 — AppShell Layout Structure Test

## Objective
Verify the structural implementation of the AppShell layout: the `page-wrap` and `shell` containers carry all required CSS properties.

## Test Approach
Static source analysis — reads `web/src/components/AppShell.tsx` and `web/src/app/globals.css` directly. No browser or live server required.

## How to Run
```bash
pytest testing/tests/MYTUBE-465/test_mytube_465.py -v
```

## Coverage
- `AppShell.tsx` class name assertions (2 checks)
- `.page-wrap` CSS properties: `position`, `min-height`, `background` (3 checks)
- `.shell` CSS properties: `max-width`, `border-radius`, `background`, `box-shadow` (4 checks)
