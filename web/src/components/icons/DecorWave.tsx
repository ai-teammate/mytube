import React from "react";
import type { IconBaseProps } from "./types";

/**
 * DecorWave — decorative wave/book shape.
 * Uses fill="currentColor". Intended as a background decoration.
 * Defaults to aria-hidden="true".
 */
export default function DecorWave({
  className,
  style,
  "aria-hidden": ariaHidden = true,
  ...rest
}: IconBaseProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 120 120"
      fill="currentColor"
      className={className}
      style={style}
      aria-hidden={ariaHidden}
      {...rest}
    >
      {/* Book spine */}
      <rect x="54" y="18" width="12" height="84" rx="3" />
      {/* Left page */}
      <path d="M54 22 Q30 30 18 50 Q12 66 18 82 Q30 96 54 102 Z" />
      {/* Right page */}
      <path d="M66 22 Q90 30 102 50 Q108 66 102 82 Q90 96 66 102 Z" />
      {/* Wave decoration lines on left page */}
      <path
        d="M26 52 Q34 48 42 52 Q50 56 54 54"
        stroke="white"
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
      />
      <path
        d="M24 62 Q32 58 40 62 Q48 66 54 64"
        stroke="white"
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
      />
      <path
        d="M26 72 Q34 68 42 72 Q50 76 54 74"
        stroke="white"
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
      />
    </svg>
  );
}
