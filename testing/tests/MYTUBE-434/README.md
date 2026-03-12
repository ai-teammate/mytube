# MYTUBE-434 — Verify font cleanup: Geist font references are removed

## Objective

Ensure that all previous references to the Geist font have been removed from the application styles, so that "Geist" does not appear in any CSS, TypeScript, or rendered HTML.

## Test Type

`static-analysis`

## Approach

Two complementary strategies are used:

1. **Static source analysis** — scans all `.css`, `.ts`, `.tsx`, and `.js` files under `web/src/` (excluding `__tests__/` sub-trees to avoid false positives from test assertions) for the string "Geist" (case-insensitive).

2. **Jest rendered-HTML assertion** — delegates to the existing Jest test `does NOT include Geist font variables in body className` inside `src/__tests__/app/layout.test.tsx`. This renders the Next.js `RootLayout` via React Testing Library / jsdom and asserts that neither `geist` nor `--font-geist` appear in the `<body>` className at runtime.

## Test Structure

| File | Description |
|------|-------------|
| `test_mytube_434.py` | Main pytest test module |
| `__init__.py` | Package marker |
| `config.yaml` | Test metadata for architecture compliance |
| `README.md` | This file |

## Test Cases

| Test | Step | Description |
|------|------|-------------|
| `test_no_geist_in_css_files` | Step 1–2 | No "Geist" string in any `.css` file under `web/src/` |
| `test_no_geist_in_typescript_files` | Step 1–2 | No "Geist" string in any `.ts`/`.tsx` file under `web/src/` |
| `test_no_geist_in_layout_tsx` | Step 1–2 | `web/src/app/layout.tsx` does not import or reference Geist |
| `test_body_does_not_use_geist_font_class` | Step 3 | Rendered `<body>` className contains no Geist class (via Jest + jsdom) |

## How to Run

From the repository root:

```bash
pytest testing/tests/MYTUBE-434/test_mytube_434.py -v
```

Prerequisites: Node.js and npm dependencies installed in `web/` (`npm install` if needed).
