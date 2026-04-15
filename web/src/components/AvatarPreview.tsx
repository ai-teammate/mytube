"use client";

import { useState, useEffect } from "react";

interface AvatarPreviewProps {
  src: string;
}

/**
 * Renders a circular avatar preview for a given URL.
 * Shows a grey placeholder with a person icon if the URL is empty or fails to load.
 */
export default function AvatarPreview({ src }: AvatarPreviewProps) {
  const [error, setError] = useState(false);

  // Reset error state whenever the src changes so a corrected URL retries.
  useEffect(() => {
    setError(false);
  }, [src]);

  const showImage = src && !error;

  return (
    <div
      role="img"
      aria-label="Avatar preview"
      className="w-16 h-16 rounded-full overflow-hidden flex items-center justify-center bg-gray-200 flex-shrink-0"
    >
      {showImage ? (
        <img
          src={src}
          alt=""
          onError={() => setError(true)}
          className="w-16 h-16 rounded-full object-cover"
        />
      ) : (
        <svg
          aria-hidden="true"
          className="w-8 h-8 text-gray-400"
          fill="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z" />
        </svg>
      )}
    </div>
  );
}
