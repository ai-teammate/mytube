# MYTUBE-459 — Social login buttons: style and icons match redesign

## What this test verifies

Verifies that the Google and GitHub social login buttons rendered by the `LoginPage` component match the redesign specification:

- Both `.auth-btn` buttons are rendered.
- **Border**: `1.5px solid var(--border-light)` on both buttons.
- **Border radius**: `12px` on both buttons.
- **Background**: `var(--bg-content)` on both buttons.
- **Full-width**: each button carries the `w-full` Tailwind class.
- **Google icon**: an SVG with 4 brand-color paths (`#4285F4`, `#34A853`, `#FBBC05`, `#EA4335`).
- **GitHub icon**: an SVG with at least one path (GitHub mark using `fill="currentColor"`).

## How it works

The Python pytest module invokes the Jest + React Testing Library suite in
`web/src/__tests__/app/login/social_buttons_style.test.tsx`, which renders
`LoginPage` in jsdom and inspects inline styles and SVG child elements of each
`.auth-btn` button. Firebase and Next.js router are fully mocked; no real
network calls are made.

## Dependencies

**Node.js / npm** (already present in this repo):

```bash
cd web && npm install
```

**Python** (for the pytest wrapper):

```bash
pip install pytest
```

## How to run

From the repository root:

```bash
pytest testing/tests/MYTUBE-459/test_mytube_459.py -v
```

Or run the underlying Jest suite directly:

```bash
cd web
npm test -- --testPathPatterns "__tests__/app/login/social_buttons_style" \
  --no-coverage --forceExit --verbose
```

## Environment variables

No environment variables are required. Firebase and the Next.js router are
fully mocked in the Jest suite.

## Expected output when the test passes

```
testing/tests/MYTUBE-459/test_mytube_459.py::TestSocialLoginButtonStyles::test_google_button_border PASSED
testing/tests/MYTUBE-459/test_mytube_459.py::TestSocialLoginButtonStyles::test_google_button_border_radius PASSED
testing/tests/MYTUBE-459/test_mytube_459.py::TestSocialLoginButtonStyles::test_google_button_background PASSED
testing/tests/MYTUBE-459/test_mytube_459.py::TestSocialLoginButtonStyles::test_google_button_full_width PASSED
testing/tests/MYTUBE-459/test_mytube_459.py::TestSocialLoginButtonStyles::test_google_button_svg_icon PASSED
testing/tests/MYTUBE-459/test_mytube_459.py::TestSocialLoginButtonStyles::test_github_button_border PASSED
testing/tests/MYTUBE-459/test_mytube_459.py::TestSocialLoginButtonStyles::test_github_button_border_radius PASSED
testing/tests/MYTUBE-459/test_mytube_459.py::TestSocialLoginButtonStyles::test_github_button_background PASSED
testing/tests/MYTUBE-459/test_mytube_459.py::TestSocialLoginButtonStyles::test_github_button_full_width PASSED
testing/tests/MYTUBE-459/test_mytube_459.py::TestSocialLoginButtonStyles::test_github_button_svg_icon PASSED
```
