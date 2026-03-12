# MYTUBE-462: Auth page heading — text and typography match redesign

## Objective

Verify that the main heading inside the auth card on the login page displays the correct text
and typography values after the redesign: text reads "Welcome to MyTube", font-size is 22px,
and font-weight is 700 (bold).

## Preconditions

- The deployed web application is accessible at the URL defined by `WEB_BASE_URL`.
- Playwright with Chromium is installed in the test environment.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `WEB_BASE_URL` | ✅ Yes | Base URL of the deployed web app (e.g. `https://ai-teammate.github.io/mytube`). |
| `PLAYWRIGHT_HEADLESS` | No | Run browser headless. Default: `true`. |
| `PLAYWRIGHT_SLOW_MO` | No | Slow-motion delay in ms. Default: `0`. |

## Test Steps

1. Navigate to `/login/`.
2. Wait for the login form to be visible.
3. Locate the `<h1>` heading inside the `.auth-card` container.
4. Verify the heading text equals `"Welcome to MyTube"`.
5. Verify the computed `font-size` equals `22px`.
6. Verify the computed `font-weight` equals `700`.

## Expected Result

- Heading text is `"Welcome to MyTube"`.
- Heading `font-size` is `22px`.
- Heading `font-weight` is `700` (bold).

## Test Files

| File | Purpose |
|---|---|
| `test_mytube_462.py` | Playwright test implementation |
| `config.yaml` | Test metadata (framework, platform, dependencies) |
