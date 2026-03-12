# MYTUBE-507 — Upload card visual styling: header and container match redesign spec

Verifies that the upload card container and its heading correctly consume the
redesign design tokens defined in `upload.module.css` and `globals.css`.

Assertions covered:

| Step | Assertion |
|------|-----------|
| 1 | Upload card element is present in the DOM |
| 2a | `background` resolves to `var(--bg-card)` = `rgb(243, 244, 248)` |
| 2b | `border-radius` is exactly `16px` |
| 2c | `border` is `1px solid rgba(127, 127, 127, 0.16)` |
| 2d | `box-shadow` resolves from `var(--shadow-card)` and contains `8px 20px` |
| 3a | Heading text is "Personal Video Upload" |
| 3b | Heading `font-size` is exactly `20px` |

## Dependencies

```bash
pip install playwright pytest
playwright install chromium
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms |

## Running the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-507/test_mytube_507.py -v
```
