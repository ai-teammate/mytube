# MYTUBE-516 — Comment form redesign: input field and submit button styling

## Objective
Verify the redesign of the comment input form, including the borderless state and the CTA button style.

## Approach
Static source analysis of `CommentSection.tsx`, `CommentSection.module.css`, and `globals.css`.

## Files under test
- `web/src/components/CommentSection.tsx`
- `web/src/components/CommentSection.module.css`
- `web/src/app/globals.css`

## Run
```bash
python -m pytest testing/tests/MYTUBE-516/test_mytube_516.py -v
```
