# MYTUBE-513 — Player container and title styling: design system visual attributes applied

Verifies that the video player container (`.player`) and video title (`.videoTitle`)
on the watch page carry the correct design-system CSS values as specified.

## What is tested

| Element | Property | Expected value |
|---------|----------|----------------|
| `.player` | `border-radius` | `16px` |
| `.player` | `overflow` | `hidden` |
| `.player` | `background` | `#000` |
| `.player` | `box-shadow` | `var(--shadow-card)` |
| `.videoTitle` | `font-size` | `22px` |
| `.videoTitle` | `font-weight` | `700` |
| `.videoTitle` | `color` | `var(--text-primary)` |
| `globals.css :root` | `--shadow-card` | defined |
| `globals.css :root` | `--text-primary` | defined |

## Test modes

### Static (primary, always runs)
Reads `web/src/app/v/[id]/WatchPageClient.module.css` and `web/src/app/globals.css`
directly and asserts the correct values with regex. No browser required.

### Live (secondary, requires `APP_URL`)
Uses Playwright (via the `WatchPage` Page Object) to navigate to a deployed watch
page and verify computed CSS values in the DOM. Video discovery uses
`VideoApiService` from `testing/components/services/`.

## Dependencies

```bash
pip install playwright pytest
playwright install chromium
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` / `WEB_BASE_URL` | *(static only)* | Deployed web app base URL; enables live mode |
| `API_BASE_URL` | `http://localhost:8081` | Backend API URL for video discovery in live mode |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms |

## Running the test

```bash
# Static only (default — no live URL needed)
pytest testing/tests/MYTUBE-513/test_mytube_513.py -v

# With live browser tests
APP_URL=https://ai-teammate.github.io/mytube \
  API_BASE_URL=https://mytube-api-80693608388.us-central1.run.app \
  pytest testing/tests/MYTUBE-513/test_mytube_513.py -v
```

## Expected output (static, passing)

```
PASSED TestPlayerStylingStatic::test_player_border_radius
PASSED TestPlayerStylingStatic::test_player_overflow_hidden
PASSED TestPlayerStylingStatic::test_player_background_black
PASSED TestPlayerStylingStatic::test_player_box_shadow
PASSED TestVideoTitleStylingStatic::test_title_font_size
PASSED TestVideoTitleStylingStatic::test_title_font_weight
PASSED TestVideoTitleStylingStatic::test_title_color_token
PASSED TestDesignTokensInGlobalsCss::test_globals_css_defines_shadow_card
PASSED TestDesignTokensInGlobalsCss::test_globals_css_defines_text_primary
```
