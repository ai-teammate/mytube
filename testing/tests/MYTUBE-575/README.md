# MYTUBE-575 — Hero landing image source: asset served from static directory

## Objective

Verify that `landing_image.png` is served correctly as a static asset with
HTTP 200 from the static assets directory. The test covers the ticket steps:
open the homepage, observe network requests, filter for `landing_image.png`,
and assert HTTP 200.

## Test Type

`ui` — dual-mode: static file-system check + Playwright network interception.

## Test Structure

### Layer A — Static source check (`TestLandingImageSource`)

Runs without a browser. Confirms `landing_image.png` exists in `web/public/`
so Next.js can serve it as a static asset.

### Layer B — HTTP network check (`TestLandingImageHTTP`)

Uses `HeroImageNetworkComponent` (in
`testing/components/pages/hero_section/hero_image_network_component.py`) which
owns the full Playwright browser/request lifecycle:

- `test_landing_image_returns_http_200` — direct `APIRequestContext` GET to the
  asset URL; asserts HTTP 200 and correct `Content-Type`.
- `test_landing_image_intercepted_on_homepage` — loads the homepage, intercepts
  all `response` events, filters for `landing_image.png`, and asserts HTTP 200.

## Architecture

```
tests/MYTUBE-575/test_mytube_575.py
  └── components/pages/hero_section/hero_image_network_component.py
        └── playwright.sync_api (framework layer)
              └── testing/core/config/web_config.py (core config)
```

## Environment Variables

| Variable             | Required for   | Description                                        |
|----------------------|----------------|----------------------------------------------------|
| `APP_URL`            | Layer B        | Base URL of the deployed app (default: GitHub Pages) |
| `PLAYWRIGHT_HEADLESS`| Layer B        | Run browser headless (default: `true`)             |

## How to Run

```bash
# All layers
pytest testing/tests/MYTUBE-575/test_mytube_575.py -v

# Layer A only (no network)
pytest testing/tests/MYTUBE-575/test_mytube_575.py::TestLandingImageSource -v

# Layer B only
pytest testing/tests/MYTUBE-575/test_mytube_575.py::TestLandingImageHTTP -v
```
