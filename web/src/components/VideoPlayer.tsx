"use client";

import { useEffect, useRef, useState } from "react";

// Video.js is loaded dynamically to avoid SSR issues with the static export.
// We import the types only here; the runtime import happens inside useEffect.
import type videojs from "video.js";
import "video.js/dist/video-js.css";

interface VideoPlayerProps {
  src: string;
  poster?: string | null;
}

/**
 * VideoPlayer renders a Video.js 8.x player configured for HLS streaming.
 * It initialises the player on mount and disposes it on unmount.
 * Displays error alert when media fails to load.
 */
export default function VideoPlayer({ src, poster }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const playerRef = useRef<ReturnType<typeof videojs> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!videoRef.current || !src || !src.trim()) return;

    // Clear any previous error state when src prop changes
    setError(null);

    let isMounted = true;

    // Dynamically import video.js and the HLS plugin to ensure they run client-side only.
    // @videojs/http-streaming is required for HLS playback on non-Safari browsers.
    Promise.all([
      import("video.js"),
      import("@videojs/http-streaming"),
    ]).then(([{ default: videoJs }]) => {
      if (!isMounted || !videoRef.current || !src || !src.trim()) return;

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

      // Register error event listener to handle media load failures
      playerRef.current.on("error", () => {
        if (isMounted && playerRef.current) {
          const errorData = playerRef.current.error();
          if (errorData) {
            let message = "Failed to load video. ";
            switch (errorData.code) {
              case 1:
                message += "Loading aborted.";
                break;
              case 2:
                message += "Network error occurred.";
                break;
              case 3:
                message += "Decoding failed.";
                break;
              case 4:
                message += "Media format not supported.";
                break;
              default:
                message += "An error occurred while loading the media.";
            }
            setError(message);
          } else {
            setError("Failed to load video. Please try again later.");
          }
        }
      });

      // Register loadstart event listener to clear error when playback begins
      playerRef.current.on("loadstart", () => {
        if (isMounted) {
          setError(null);
        }
      });
    }).catch((err) => {
      if (isMounted) {
        console.error("Failed to load video player:", err);
        setError("Failed to initialize video player. Please try again later.");
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
      {error && (
        <div className="absolute inset-0 pointer-events-none rounded-lg">
          <div className="absolute inset-0 bg-black/40"></div>
          <div className="absolute inset-0 flex items-center justify-center pointer-events-auto">
            <div
              role="alert"
              className="bg-red-600 text-white px-6 py-4 rounded text-center max-w-sm shadow-lg"
            >
              <p className="mb-4">{error}</p>
              <button
                onClick={() => setError(null)}
                className="bg-red-800 hover:bg-red-900 text-white px-4 py-2 rounded font-semibold transition-colors"
              >
                Try Again
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
