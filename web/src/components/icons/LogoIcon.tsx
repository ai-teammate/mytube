import React, { useId } from "react";
import type { IconBaseProps } from "./types";

/**
 * LogoIcon — the "smile-play" brand logo.
 * Uses a linear gradient driven by CSS custom properties (--logo-grad-start, --logo-grad-end)
 * so the gradient colours respect the theming system defined in globals.css.
 * Uses useId() to generate a unique gradient ID per instance, avoiding duplicate IDs
 * when the logo renders in multiple places on the same page (header + auth cards).
 * Defaults to aria-hidden="true" (decorative); pass aria-label / role="img" to make it semantic.
 */
export default function LogoIcon({
  className,
  style,
  "aria-hidden": ariaHidden = true,
  ...rest
}: IconBaseProps) {
  const uid = useId();
  const gradId = `logo-grad-${uid}`;

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 40 40"
      fill="none"
      className={className}
      style={style}
      aria-hidden={ariaHidden}
      {...rest}
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="var(--logo-grad-start)" />
          <stop offset="100%" stopColor="var(--logo-grad-end)" />
        </linearGradient>
      </defs>
      <rect x="2" y="6" width="36" height="28" rx="10" fill={`url(#${gradId})`} />
      {/* Smile arc */}
      <path
        d="M14 26 C16 28 24 28 26 26"
        stroke="white"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      {/* Play triangle */}
      <path
        d="M17.5 15.5 L24.5 19.5 L17.5 23.5 V15.5 Z"
        fill="white"
        stroke="white"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}
