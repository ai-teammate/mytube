"use client";

import { use, useState, useCallback } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import type { PlaylistDetail, PlaylistRepository, PlaylistVideoItem } from "@/domain/playlist";
import { ApiPlaylistRepository } from "@/data/playlistRepository";
import { useEffect } from "react";

// Lazy-load VideoPlayer to keep the static shell lightweight.
const VideoPlayer = dynamic(() => import("@/components/VideoPlayer"), {
  ssr: false,
  loading: () => (
    <div className="w-full aspect-video bg-black flex items-center justify-center">
      <p className="text-gray-400">Loading player…</p>
    </div>
  ),
});

const defaultRepository: PlaylistRepository = new ApiPlaylistRepository();

interface PlaylistPageProps {
  params: Promise<{ id: string }>;
  repository?: PlaylistRepository;
}

export default function PlaylistPageClient({
  params,
  repository = defaultRepository,
}: PlaylistPageProps) {
  const { id } = use(params);

  const [playlist, setPlaylist] = useState<PlaylistDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Index of the currently playing video.
  const [currentIndex, setCurrentIndex] = useState(0);
  // Whether the playlist has ended (last video finished).
  const [ended, setEnded] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadPlaylist() {
      try {
        const data = await repository.getByID(id);
        if (cancelled) return;
        if (data === null) {
          setNotFound(true);
        } else {
          setPlaylist(data);
        }
      } catch {
        if (!cancelled) {
          setError("Could not load playlist. Please try again later.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadPlaylist();
    return () => {
      cancelled = true;
    };
  }, [id, repository]);

  const currentVideo: PlaylistVideoItem | null =
    playlist && playlist.videos.length > 0
      ? playlist.videos[currentIndex] ?? null
      : null;

  const handleVideoEnded = useCallback(() => {
    if (!playlist) return;
    const nextIndex = currentIndex + 1;
    if (nextIndex < playlist.videos.length) {
      setCurrentIndex(nextIndex);
    } else {
      setEnded(true);
    }
  }, [currentIndex, playlist]);

  const handlePlayAgain = useCallback(() => {
    setCurrentIndex(0);
    setEnded(false);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">Playlist not found.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p role="alert" className="text-red-600">
          {error}
        </p>
      </div>
    );
  }

  if (!playlist) return null;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Playlist title */}
      <div className="max-w-7xl mx-auto px-4 py-4">
        <h1 className="text-2xl font-bold text-gray-900">{playlist.title}</h1>
        <p className="text-sm text-gray-500 mt-1">
          by{" "}
          <Link
            href={`/u/${playlist.ownerUsername}`}
            className="hover:underline text-blue-600"
          >
            {playlist.ownerUsername}
          </Link>{" "}
          · {playlist.videos.length} video{playlist.videos.length !== 1 ? "s" : ""}
        </p>
      </div>

      {playlist.videos.length === 0 ? (
        <div className="max-w-7xl mx-auto px-4 py-8 text-center">
          <p className="text-gray-500">This playlist has no videos yet.</p>
        </div>
      ) : (
        /* Split view: player on left, queue on right */
        <div className="max-w-7xl mx-auto px-4 pb-8 flex flex-col lg:flex-row gap-4">
          {/* Player area */}
          <div className="flex-1 min-w-0">
            <div className="w-full bg-black rounded-lg overflow-hidden relative">
              {ended ? (
                /* End-of-playlist overlay (Option A: stop and prompt) */
                <div
                  data-testid="end-of-playlist"
                  className="w-full aspect-video flex flex-col items-center justify-center bg-black"
                >
                  <p className="text-white text-xl font-semibold mb-4">
                    End of playlist
                  </p>
                  <button
                    onClick={handlePlayAgain}
                    className="rounded-lg bg-blue-600 px-6 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
                  >
                    Play again
                  </button>
                </div>
              ) : currentVideo?.id ? (
                <PlaylistVideoPlayerWrapper
                  videoID={currentVideo.id}
                  thumbnailUrl={currentVideo.thumbnailUrl}
                  onEnded={handleVideoEnded}
                />
              ) : null}
            </div>

            {/* Now playing info */}
            {!ended && currentVideo && (
              <div className="mt-3">
                <p className="text-xs text-gray-500 uppercase tracking-wide">
                  Now playing ({currentIndex + 1}/{playlist.videos.length})
                </p>
                <Link
                  href={`/v/${currentVideo.id}`}
                  className="text-lg font-semibold text-gray-900 hover:text-blue-600 transition-colors line-clamp-2"
                >
                  {currentVideo.title}
                </Link>
              </div>
            )}
          </div>

          {/* Queue panel */}
          <div className="lg:w-80 xl:w-96 flex-shrink-0">
            <div className="bg-white rounded-lg shadow-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100">
                <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
                  Queue
                </h2>
              </div>
              <div className="overflow-y-auto max-h-[500px] lg:max-h-[600px]">
                {playlist.videos.map((video, index) => (
                  <button
                    key={video.id}
                    onClick={() => {
                      setCurrentIndex(index);
                      setEnded(false);
                    }}
                    className={`w-full text-left flex items-start gap-3 px-4 py-3 hover:bg-gray-50 transition-colors border-b border-gray-50 last:border-0 ${
                      index === currentIndex && !ended
                        ? "bg-blue-50 border-l-4 border-l-blue-500"
                        : ""
                    }`}
                    aria-label={`Play ${video.title}`}
                    aria-current={index === currentIndex && !ended ? "true" : undefined}
                  >
                    {/* Thumbnail */}
                    <div className="flex-shrink-0 w-20 h-12 bg-gray-200 rounded overflow-hidden relative">
                      {video.thumbnailUrl ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={video.thumbnailUrl}
                          alt={video.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-gray-400 text-xs">
                          —
                        </div>
                      )}
                      {/* Position badge */}
                      <span className="absolute bottom-0.5 right-0.5 bg-black/70 text-white text-[10px] px-1 rounded">
                        {index + 1}
                      </span>
                    </div>

                    {/* Title */}
                    <p className="text-sm text-gray-900 line-clamp-2 flex-1">
                      {video.title}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── PlaylistVideoPlayerWrapper ───────────────────────────────────────────────

interface PlaylistVideoPlayerWrapperProps {
  videoID: string;
  thumbnailUrl: string | null;
  onEnded: () => void;
}

/**
 * Wraps the VideoPlayer with an onEnded callback using a hidden video element
 * overlay to detect the 'ended' event. Since VideoPlayer uses Video.js
 * internally, we use a key prop to remount on video change to reset playback.
 */
function PlaylistVideoPlayerWrapper({
  videoID,
  thumbnailUrl,
  onEnded,
}: PlaylistVideoPlayerWrapperProps) {
  const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

  // The HLS manifest URL for this video.
  // We construct it from the video detail endpoint lazily.
  const [hlsUrl, setHlsUrl] = useState<string | null>(null);
  const [videoLoading, setVideoLoading] = useState(true);
  const [videoError, setVideoError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setVideoLoading(true);
    setVideoError(false);
    setHlsUrl(null);

    fetch(`${API_URL}/api/videos/${encodeURIComponent(videoID)}`)
      .then((res) => {
        if (!res.ok) throw new Error("not found");
        return res.json();
      })
      .then((data: { hls_manifest_path?: string }) => {
        if (cancelled) return;
        setHlsUrl(data.hls_manifest_path ?? null);
      })
      .catch(() => {
        if (!cancelled) setVideoError(true);
      })
      .finally(() => {
        if (!cancelled) setVideoLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [videoID, API_URL]);

  if (videoLoading) {
    return (
      <div className="w-full aspect-video flex items-center justify-center bg-black">
        <p className="text-gray-400">Loading…</p>
      </div>
    );
  }

  if (videoError || !hlsUrl) {
    return (
      <div className="w-full aspect-video flex items-center justify-center bg-black">
        <p className="text-gray-400">Video not available.</p>
        <button
          onClick={onEnded}
          className="ml-4 text-sm text-blue-400 hover:underline"
        >
          Skip
        </button>
      </div>
    );
  }

  return (
    <AutoAdvancePlayer
      key={videoID}
      src={hlsUrl}
      poster={thumbnailUrl}
      onEnded={onEnded}
    />
  );
}

// ─── AutoAdvancePlayer ────────────────────────────────────────────────────────

interface AutoAdvancePlayerProps {
  src: string;
  poster: string | null;
  onEnded: () => void;
}

/**
 * Renders the VideoPlayer and fires onEnded when the video finishes.
 * Uses a thin overlay div that listens for the 'ended' event on the video element.
 */
function AutoAdvancePlayer({ src, poster, onEnded }: AutoAdvancePlayerProps) {
  const containerRef = useCallbackRef<HTMLDivElement>((node) => {
    if (!node) return;
    const listener = () => onEnded();
    // Video.js adds the video element as a child; listen on the container.
    const video = node.querySelector("video");
    if (video) {
      video.addEventListener("ended", listener);
      return () => video.removeEventListener("ended", listener);
    }
  });

  return (
    <div ref={containerRef}>
      <VideoPlayer src={src} poster={poster} />
    </div>
  );
}

/**
 * A simple ref callback hook that runs the setup function when the node mounts.
 */
function useCallbackRef<T extends HTMLElement>(
  setup: (node: T | null) => (() => void) | void
) {
  const cleanupRef = { current: (() => {}) as () => void };

  return useCallback(
    (node: T | null) => {
      cleanupRef.current?.();
      const cleanup = setup(node);
      cleanupRef.current = cleanup ?? (() => {});
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [setup]
  );
}
