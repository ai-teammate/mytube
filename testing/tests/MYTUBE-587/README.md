# MYTUBE-587 — HeroSection landing image src includes basePath prefix

## Ticket

**MYTUBE-587**: HeroSection landing image on GitHub Pages — `src` attribute includes basePath prefix

## Purpose

Regression guard for **MYTUBE-584**.  Verifies that the hero landing image
`src` attribute is correctly prefixed with `/mytube` (the GitHub Pages
`basePath`) so the browser fetches `/mytube/landing_image.png` (HTTP 200)
instead of the bare `/landing_image.png` (HTTP 404).

The fix in MYTUBE-584 made `HeroSection.tsx` read `NEXT_PUBLIC_BASE_PATH` and
prepend it to the image `src`.  These tests confirm that behaviour is present
and correct on every deployment.

## What is Verified

| Layer | Test | Assertion |
|-------|------|-----------|
| A — DOM | `TestHeroImageSrcBasePath::test_landing_image_src_has_basepath_prefix` | Rendered `<img src>` contains `/mytube/landing_image.png` |
| B-1 — Direct HTTP | `TestHeroImageNetworkWithBasePath::test_landing_image_fetched_with_http_200` | Direct GET to `<base_url>/landing_image.png` returns HTTP 200 |
| B-2 — Browser intercept | `TestHeroImageNetworkWithBasePath::test_landing_image_intercepted_with_prefixed_url` | Browser-intercepted request URL contains `/mytube` prefix and status is HTTP 200 |

## How to Run

```bash
pytest testing/tests/MYTUBE-587/test_mytube_587.py -v
```

Run against the default GitHub Pages URL (`https://ai-teammate.github.io/mytube`):

```bash
APP_URL=https://ai-teammate.github.io/mytube pytest testing/tests/MYTUBE-587/test_mytube_587.py -v
```

## Required Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` | `https://ai-teammate.github.io/mytube` | Base URL of the deployed application |
| `PLAYWRIGHT_HEADLESS` | `true` | Set to `false` to run with a visible browser window |
