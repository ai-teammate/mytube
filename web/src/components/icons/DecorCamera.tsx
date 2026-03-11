import React from "react";

interface DecorCameraProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
  style?: React.CSSProperties;
}

/**
 * DecorCamera — decorative camera/triangle shape.
 * Uses fill="currentColor". Intended as a background decoration.
 * Defaults to aria-hidden="true".
 */
export default function DecorCamera({
  className,
  style,
  "aria-hidden": ariaHidden = true,
  ...rest
}: DecorCameraProps) {
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
      {/* Camera body */}
      <rect x="10" y="38" width="80" height="56" rx="8" />
      {/* Camera lens circle */}
      <circle cx="50" cy="66" r="18" fill="white" />
      <circle cx="50" cy="66" r="12" />
      <circle cx="50" cy="66" r="5" fill="white" />
      {/* Viewfinder notch */}
      <rect x="28" y="30" width="24" height="12" rx="4" />
      {/* Decorative triangle accent (side lens cap) */}
      <polygon points="90,38 110,28 110,78 90,94" />
    </svg>
  );
}
