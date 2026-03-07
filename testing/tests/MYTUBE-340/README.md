# MYTUBE-340 — Click logo in header — user redirected to homepage

Verifies that clicking the site logo in the SiteHeader always redirects the user to the root homepage (`/`), regardless of which sub-page they are currently on.

## Preconditions

- The sub-pages `/search` and `/register` must be accessible without authentication.
- The deployed web app must be reachable at the configured base URL.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Deployed web app base URL |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms for debugging |

## Running the test

```bash
cd testing
pip install -r requirements.txt
playwright install chromium
pytest tests/MYTUBE-340/ -v
```

## Test cases

| # | Test | Description |
|---|------|-------------|
| 1 | `test_logo_click_redirects_to_homepage[search-page]` | Logo click from `/search` navigates to homepage (`/`) |
| 2 | `test_logo_click_redirects_to_homepage[register-page]` | Logo click from `/register` navigates to homepage (`/`) |
| 3 | `test_homepage_content_rendered_after_logo_click` | Homepage discovery sections (Recently Uploaded / Most Viewed) are visible after logo click |

## Components used

- `testing/components/pages/site_header/` — Page Object for the global header
- `testing/components/pages/home_page/` — Page Object for the homepage discovery sections
- `testing/core/config/web_config.py` — Centralised environment variable access
