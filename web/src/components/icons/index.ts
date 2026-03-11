/**
 * Icon library — inline SVG React components.
 *
 * All icons accept `className`, `style`, and any SVG prop via `...rest`.
 * All icons default to `aria-hidden="true"` (decorative). Override by passing
 * `aria-label` and `role="img"` when the icon must be perceivable to screen readers.
 *
 * Colour usage guidelines (WCAG AA, 4.5:1 minimum contrast):
 *   • Light backgrounds : use `text-gray-900`  (contrast ≥ 15:1 on white)
 *   • Dark backgrounds  : use `text-white` or `text-gray-100`  (contrast ≥ 12:1 on gray-900)
 *   • Brand accent      : use `text-red-600` for LogoIcon on white  (contrast ≥ 4.7:1)
 */

export { default as LogoIcon } from "./LogoIcon";
export { default as DecorPlay } from "./DecorPlay";
export { default as DecorFilm } from "./DecorFilm";
export { default as DecorCamera } from "./DecorCamera";
export { default as DecorWave } from "./DecorWave";
export { default as SunIcon } from "./SunIcon";
export { default as MoonIcon } from "./MoonIcon";
