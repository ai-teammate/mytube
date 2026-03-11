import React from "react";

interface DecorFilmProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
  style?: React.CSSProperties;
}

/**
 * DecorFilm — decorative film/atom shape.
 * Uses fill="currentColor". Intended as a background decoration.
 * Defaults to aria-hidden="true".
 */
export default function DecorFilm({
  className,
  style,
  "aria-hidden": ariaHidden = true,
  ...rest
}: DecorFilmProps) {
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
      {/* Film strip outer frame */}
      <rect x="10" y="30" width="100" height="60" rx="6" />
      {/* Sprocket holes — left column */}
      <rect x="18" y="40" width="12" height="10" rx="2" fill="white" />
      <rect x="18" y="55" width="12" height="10" rx="2" fill="white" />
      <rect x="18" y="70" width="12" height="10" rx="2" fill="white" />
      {/* Sprocket holes — right column */}
      <rect x="90" y="40" width="12" height="10" rx="2" fill="white" />
      <rect x="90" y="55" width="12" height="10" rx="2" fill="white" />
      <rect x="90" y="70" width="12" height="10" rx="2" fill="white" />
      {/* Centre frame window */}
      <rect x="38" y="38" width="44" height="44" rx="4" fill="white" />
      {/* Atom nucleus */}
      <circle cx="60" cy="60" r="8" />
      {/* Atom orbit rings */}
      <ellipse
        cx="60"
        cy="60"
        rx="18"
        ry="6"
        stroke="currentColor"
        strokeWidth="2.5"
        fill="none"
        transform="rotate(0 60 60)"
      />
      <ellipse
        cx="60"
        cy="60"
        rx="18"
        ry="6"
        stroke="currentColor"
        strokeWidth="2.5"
        fill="none"
        transform="rotate(60 60 60)"
      />
      <ellipse
        cx="60"
        cy="60"
        rx="18"
        ry="6"
        stroke="currentColor"
        strokeWidth="2.5"
        fill="none"
        transform="rotate(120 60 60)"
      />
    </svg>
  );
}
