# MYTUBE-451 — VideoCard title clamping: long titles are truncated at two lines

## Objective

Ensure that video titles that exceed the available width are limited to two lines to maintain card layout consistency. The title text must be restricted to a maximum of two lines, with overflowing text hidden (two-line clamp), preventing the card height from expanding excessively.

## Test Type

`static-analysis`

## Approach

Static CSS inspection: reads `web/src/components/VideoCard.module.css` and verifies that the `.videoTitle` rule contains all required two-line clamping properties. Also verifies that `VideoCard.tsx` applies `styles.videoTitle` to the title `Link` element, confirming the CSS rule is wired to the rendered output.

## Files Inspected

| File | Purpose |
|------|---------|
| `web/src/components/VideoCard.module.css` | CSS module defining `.videoTitle` clamping styles |
| `web/src/components/VideoCard.tsx` | React component that applies `styles.videoTitle` |

## Test Structure

| File | Description |
|------|-------------|
| `test_mytube_451.py` | Main pytest test module |
| `__init__.py` | Package marker |
| `config.yaml` | Test metadata for architecture compliance |
| `README.md` | This file |

## Test Cases

| # | Test | Description |
|---|------|-------------|
| 1 | `test_videotitle_rule_exists_in_css_module` | `.videoTitle` selector is present in `VideoCard.module.css` |
| 2 | `test_display_webkit_box` | `display: -webkit-box` is set on `.videoTitle` |
| 3 | `test_webkit_line_clamp_is_2` | `-webkit-line-clamp: 2` restricts titles to two lines |
| 4 | `test_webkit_box_orient_vertical` | `-webkit-box-orient: vertical` enables line clamping |
| 5 | `test_overflow_hidden` | `overflow: hidden` hides text beyond two lines |
| 6 | `test_videotitle_class_applied_in_component` | `styles.videoTitle` is applied in `VideoCard.tsx` |

## How to Run

From the repository root:

```bash
pytest testing/tests/MYTUBE-451/test_mytube_451.py -v
```
