# MYTUBE-427 — Icon library exports: all required icons available from index.ts

## Overview

Static source-code analysis test that verifies all seven required icons are exported
from the icon library's entry point: `web/src/components/icons/index.ts`.

## Test type

Static (no runtime environment required)

## Icons verified

- `LogoIcon`
- `DecorPlay`
- `DecorFilm`
- `DecorCamera`
- `DecorWave`
- `SunIcon`
- `MoonIcon`

## Steps verified

1. `web/src/components/icons/index.ts` exists in the repository.
2. Each of the 7 required icons has a named export statement in the file.

## How to run

```bash
pytest testing/tests/MYTUBE-427/
```

## Notes

- No environment variables or external dependencies required.
- The test uses regex matching to detect export patterns including
  `export { default as IconName }`, `export { IconName }`, and direct exports.
