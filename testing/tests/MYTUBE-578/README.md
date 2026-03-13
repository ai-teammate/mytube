# MYTUBE-578 — Update favicon and meta OG images: new logo reflected in browser tab and social previews

Verifies that the site's favicon (`link[rel='icon']`) and Open Graph image
(`meta[property='og:image']`) both reference the updated `logo.svg` asset.

## Objective

After the logo refresh, both the browser-tab icon and social-preview image
should be served from `logo.svg`.  This test navigates to the deployed home
page, inspects the `<head>` tag, and asserts the correct href/content values.

## Test steps

1. Open the application home page in a Chromium browser.
2. Inspect the HTML `<head>` via the `HeadMetaPage` component.
3. Locate `link[rel='icon']` and `meta[property='og:image']`.
4. Assert both tags reference `logo.svg`.

## Expected result

| Tag | Attribute | Expected value |
|-----|-----------|----------------|
| `<link rel="icon">` | `href` | contains `logo.svg` |
| `<meta property="og:image">` | `content` | contains `logo.svg` |

## Architecture

- **`HeadMetaPage`** (`testing/components/pages/head_meta_page/`) — Page Object
  encapsulating all Playwright DOM interactions with `<head>` metadata.
- **`WebConfig`** (`testing/core/config/web_config.py`) — centralises env var
  access; no hardcoded URLs.
- Playwright sync API with module-scoped pytest fixtures.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Deployed web app base URL |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms |

## Dependencies

```bash
pip install playwright pytest
playwright install chromium
```

## Running the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-578/test_mytube_578.py -v
```

## Expected output (passing)

```
PASSED test_favicon_tag_is_present
PASSED test_favicon_references_logo_svg
PASSED test_og_image_tag_is_present
PASSED test_og_image_references_logo_svg
```
