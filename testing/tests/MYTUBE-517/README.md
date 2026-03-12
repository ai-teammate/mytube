# MYTUBE-517: Comment list items — card styling and author metadata alignment

## Objective
Verify that individual comment items apply the new card-based design system and typography.

## Test Layers
- **Layer A** — CSS source analysis (`web/src/components/CommentSection.module.css`)
- **Layer B** — Playwright fixture computed styles
- **Layer C** — Live app integration with mocked API

## Running
```bash
pytest testing/tests/MYTUBE-517/
```

## Environment Variables
- `APP_URL` / `WEB_BASE_URL` — base URL of deployed app (defaults to `https://ai-teammate.github.io/mytube`)
- `PLAYWRIGHT_HEADLESS` — headless mode (default: `true`)
