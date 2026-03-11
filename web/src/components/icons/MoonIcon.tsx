import React from "react";

interface MoonIconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
  style?: React.CSSProperties;
}

/**
 * MoonIcon — moon SVG for the dark-mode toggle button.
 * Uses stroke="currentColor" / fill="none" (outline style, stroke-width 2).
 * Recommended: text-gray-100 on dark backgrounds (contrast ≥ 7:1).
 * Defaults to aria-hidden="true"; pass aria-label / role="img" when used standalone.
 */
export default function MoonIcon({
  className,
  style,
  "aria-hidden": ariaHidden = true,
  ...rest
}: MoonIconProps) {
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
      {/* Crescent moon path */}
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}
