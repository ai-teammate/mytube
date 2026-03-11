import React from "react";

interface SunIconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
  style?: React.CSSProperties;
}

/**
 * SunIcon — sun SVG for the light-mode toggle button.
 * Uses stroke="currentColor" / fill="none" (outline style, stroke-width 2).
 * Recommended: text-gray-800 on light backgrounds (contrast ≥ 7:1).
 * Defaults to aria-hidden="true"; pass aria-label / role="img" when used standalone.
 */
export default function SunIcon({
  className,
  style,
  "aria-hidden": ariaHidden = true,
  ...rest
}: SunIconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={style}
      aria-hidden={ariaHidden}
      {...rest}
    >
      {/* Central circle */}
      <circle cx="12" cy="12" r="4" />
      {/* Rays */}
      <line x1="12" y1="2" x2="12" y2="5" />
      <line x1="12" y1="19" x2="12" y2="22" />
      <line x1="2" y1="12" x2="5" y2="12" />
      <line x1="19" y1="12" x2="22" y2="12" />
      <line x1="4.22" y1="4.22" x2="6.34" y2="6.34" />
      <line x1="17.66" y1="17.66" x2="19.78" y2="19.78" />
      <line x1="4.22" y1="19.78" x2="6.34" y2="17.66" />
      <line x1="17.66" y1="6.34" x2="19.78" y2="4.22" />
    </svg>
  );
}
