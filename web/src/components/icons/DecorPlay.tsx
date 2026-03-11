import React from "react";

interface DecorPlayProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
  style?: React.CSSProperties;
}

/**
 * DecorPlay — decorative play/sigma shape (120×120).
 * Uses fill="currentColor". Intended as a background decoration, not an interactive element.
 * Defaults to aria-hidden="true".
 */
export default function DecorPlay({
  className,
  style,
  "aria-hidden": ariaHidden = true,
  ...rest
}: DecorPlayProps) {
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
      {/* Sigma / play hybrid — a stylised Σ that echoes a right-pointing arrow */}
      <path d="M20 10 L20 24 L62 60 L20 96 L20 110 L100 110 L100 96 L44 96 L80 60 L44 24 L100 24 L100 10 Z" />
    </svg>
  );
}
