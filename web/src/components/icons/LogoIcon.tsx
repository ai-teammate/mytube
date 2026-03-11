import React from "react";
import type { IconBaseProps } from "./types";

/**
 * LogoIcon — the "smile-play" brand logo.
 * Uses fill="currentColor" so colour is controlled by the parent's CSS class.
 * Recommended: text-red-600 on white backgrounds.
 * Defaults to aria-hidden="true" (decorative); pass aria-label / role="img" to make it semantic.
 */
export default function LogoIcon({
  className,
  style,
  "aria-hidden": ariaHidden = true,
  ...rest
}: IconBaseProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 44 44"
      fill="currentColor"
      className={className}
      style={style}
      aria-hidden={ariaHidden}
      {...rest}
    >
      {/* Outer circle */}
      <circle cx="22" cy="22" r="20" />
      {/* Play triangle (white cutout via fill) */}
      <polygon points="17,14 17,30 33,22" fill="white" />
      {/* Smile arc */}
      <path
        d="M14 26 Q22 34 30 26"
        stroke="white"
        strokeWidth="2.5"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  );
}
