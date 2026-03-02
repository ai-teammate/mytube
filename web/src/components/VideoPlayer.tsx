"use client";

import { useEffect, useRef } from "react";

// Video.js is loaded dynamically to avoid SSR issues with the static export.
// We import the types only here; the runtime import happens inside useEffect.
import type videojs from "video.js";

interface VideoPlayerProps {
  src: string;
  poster?: string | null;
}

/**
 * VideoPlayer renders a Video.js 8.x player configured for HLS streaming.
 * It initialises the player on mount and disposes it on unmount.
 */
export default function VideoPlayer({ src, poster }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const playerRef = useRef<ReturnType<typeof videojs> | null>(null);

  useEffect(() => {
    if (!videoRef.current) return;

    let isMounted = true;

    // Dynamically import video.js to ensure it runs client-side only.
    Promise.all([
      import("video.js"),
      import("video.js/dist/video-js.css"),
    ]).then(([{ default: videoJs }]) => {
      if (!isMounted || !videoRef.current) return;

      playerRef.current = videoJs(videoRef.current, {
        controls: true,
        autoplay: false,
        preload: "auto",
        fluid: true,
        sources: [
          {
            src,
            type: "application/x-mpegURL",
          },
        ],
        ...(poster ? { poster } : {}),
      });
    }).catch((err) => {
      if (isMounted) {
        console.error("Failed to load video player:", err);
      }
    });

    return () => {
      isMounted = false;
      if (playerRef.current) {
        playerRef.current.dispose();
        playerRef.current = null;
      }
    };
  }, [src, poster]);

  return (
    <div data-vjs-player>
      {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
      <video
        ref={videoRef}
        className="video-js vjs-big-play-centered"
        playsInline
      />
    </div>
  );
}
