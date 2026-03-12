# MYTUBE-456 — VideoCard tags row omission

## Objective

Verify that the `VideoCard` component does not render an empty or broken tags row when `video.tags` is empty or undefined.

## Test approach

Component-level unit test (Jest + React Testing Library / jsdom).

## How to run

```bash
npx jest testing/tests/MYTUBE-456/
```

## Coverage

| Scenario | Assertion |
|---|---|
| `tags: []` | `.videoTags` absent from DOM |
| `tags` is `undefined` | `.videoTags` absent from DOM |
| `tags: ["react"]` (positive control) | `.videoTags` present in DOM |
| `tags: []` | No `.tagPill` / `.tagOverflow` elements |
