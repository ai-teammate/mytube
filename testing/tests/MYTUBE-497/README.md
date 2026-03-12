# MYTUBE-497: Non-auth route with auth prefix — AppShell layout is correctly applied

## Objective

Ensure that the layout exclusion logic (normalization and prefix checking) in
`AppShell.tsx` does NOT incorrectly hide the shell on pages whose pathname
*begins with* an auth route string (e.g. `/login-help`, `/register-confirmation`)
but are not the auth routes themselves.

## Test Steps

1. Navigate to `/login-help/` (a route sharing the `/login` prefix but distinct).
2. Inspect the DOM — verify `.shell` and `.page-wrap` are present.
3. Verify that standard shell styles (`max-width: 1320px`) are applied.
4. Navigate to `/register-confirmation/` (a route sharing the `/register` prefix).
5. Repeat DOM and style inspection.

## Expected Result

- `.shell` element **is present** on both routes.
- `.page-wrap` element **is present** on both routes.
- An element with `maxWidth: 1320px` **is found** on both routes.

## Architecture

- `WebConfig` from `testing/core/config/web_config.py` centralises env var access.
- `NonAuthShellPage` from `testing/components/pages/non_auth_shell_page/` encapsulates
  navigation and shell inspection.
- `ShellInspectionMixin` provides `has_shell_class`, `has_page_wrap_class`, and
  `has_shell_like_styles` helpers.

## Run

```bash
pytest testing/tests/MYTUBE-497/test_mytube_497.py -v
```
