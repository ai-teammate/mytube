# MYTUBE-461 — Auth Submit Button: Green Gradient Pill Design

## Objective
Verify that the primary submit button on the Sign In and Register pages matches
the green gradient pill design specification.

## Test type
Static source analysis (TSX + CSS inspection). No browser or live server required.

## What is verified
- Submit button has `btn cta` CSS classes (Login & Register)
- Submit button is full-width (`w-full`) (Login & Register)
- Submit button uses green gradient via `var(--gradient-cta)` (Login & Register)
- Submit button has pill border-radius (`borderRadius: 999`) (Login & Register)
- `--gradient-cta` token resolves to `linear-gradient(90deg, #62c235 0%, #4fa82b 100%)`

## How to run
```bash
pytest testing/tests/MYTUBE-461/test_mytube_461.py -v
```
