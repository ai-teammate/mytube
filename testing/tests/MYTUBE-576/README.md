# MYTUBE-576 — Logo Icon SVG Matches Reference

## Objective

Verify that `LogoIcon.tsx` uses the exact SVG path data and structure from the
provided reference file (`favicon.svg`), resolving the discrepancy identified
in the design review.

## Approach

Dual-layer static analysis — no browser required.

**Layer A — Structural attribute check** (`LogoIcon.tsx`):
- `viewBox="0 0 40 40"`
- Root `fill="none"`
- `<rect>` geometry: `x=2 y=6 width=36 height=28 rx=10`
- Smile arc path: `M14 26 C16 28 24 28 26 26`
- Play triangle path: `M17.5 15.5 L24.5 19.5 L17.5 23.5 V15.5 Z`
- Linear gradient with CSS variable stops (`--logo-grad-start`, `--logo-grad-end`)
- Gradient geometry: `(0,0)→(40,40)` in `userSpaceOnUse`

**Layer B — Reference parity check** (`favicon.svg`):
- Extracts the same structural elements from both files and asserts they are identical.

## Files Under Test

- `web/src/components/icons/LogoIcon.tsx`
- `web/public/favicon.svg` (canonical reference)

## How to Run

From the repository root:

```bash
pytest testing/tests/MYTUBE-576/test_mytube_576.py -v
```
