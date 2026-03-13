# MYTUBE-574 — Hero landing image accessibility

Verifies that the Next.js `<Image>` component for the landing asset includes
`alt`, `width`, and `height` attributes required for accessibility (WCAG 1.1.1)
and performance (CLS prevention).

## Test layers

| Layer | Description |
|-------|-------------|
| **A — Static** | Reads `web/src/components/HeroSection.tsx` and asserts the props are set at the source level |
| **B — Playwright E2E** | Opens the deployed homepage and asserts the rendered `<img>` DOM attributes |

## Dependencies

```bash
pip install playwright pytest
playwright install chromium
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Deployed web app base URL |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms |

## Run

```bash
pytest testing/tests/MYTUBE-574/test_mytube_574.py -v
```
