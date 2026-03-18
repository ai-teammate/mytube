"use client";

import { use, useState, useCallback, useRef, useEffect } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import type { PlaylistDetail, PlaylistRepository, PlaylistVideoItem } from "@/domain/playlist";
import type { VideoRepository } from "@/domain/video";
import { ApiPlaylistRepository } from "@/data/playlistRepository";
import { ApiVideoRepository } from "@/data/videoRepository";
import styles from "./PlaylistPageClient.module.css";

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
const defaultVideoRepository: VideoRepository = new ApiVideoRepository();

interface PlaylistPageProps {
  params: Promise<{ id: string }>;
  repository?: PlaylistRepository;
  videoRepository?: VideoRepository;
}

export default function PlaylistPageClient({
  params,
  repository = defaultRepository,
  videoRepository = defaultVideoRepository,
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
      <div className={styles.loadingState}>
        <p className={styles.loadingText}>Loading…</p>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className={styles.loadingState}>
        <p className={styles.loadingText}>Playlist not found.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.loadingState}>
        <p role="alert" className={styles.errorText}>
          {error}
        </p>
      </div>
    );
  }

  if (!playlist) return null;

  return (
    <div className={styles.page}>
      {/* Playlist title */}
      <div className={styles.header}>
        <h1 className={styles.title}>{playlist.title}</h1>
        <p className={styles.subtitle}>
          by{" "}
          <Link
            href={`/u/${playlist.ownerUsername}`}
            className={styles.subtitleLink}
          >
            {playlist.ownerUsername}
          </Link>{" "}
          · {playlist.videos.length} video{playlist.videos.length !== 1 ? "s" : ""}
        </p>
      </div>

      {playlist.videos.length === 0 ? (
        <div className={styles.emptyMessage}>
          <p>This playlist has no videos yet.</p>
        </div>
      ) : (
        /* Split view: player on left, queue on right */
        <div className={styles.splitView}>
          {/* Player area */}
          <div className={styles.playerArea}>
            <div className={styles.playerWrap}>
              {ended ? (
                /* End-of-playlist overlay (Option A: stop and prompt) */
                <div
                  data-testid="end-of-playlist"
                  className={styles.endOverlay}
                >
                  <p className={styles.endTitle}>
                    End of playlist
                  </p>
                  <button
                    onClick={handlePlayAgain}
                    className={styles.btnPlayAgain}
                  >
                    Play again
                  </button>
                </div>
              ) : currentVideo?.id ? (
                <PlaylistVideoPlayerWrapper
                  videoID={currentVideo.id}
                  thumbnailUrl={currentVideo.thumbnailUrl}
                  onEnded={handleVideoEnded}
                  videoRepository={videoRepository}
                />
              ) : null}
            </div>

            {/* Now playing info */}
            {!ended && currentVideo && (
              <div className="mt-3">
                <p className={styles.nowPlayingLabel}>
                  Now playing ({currentIndex + 1}/{playlist.videos.length})
                </p>
                <Link
                  href={`/v/${currentVideo.id}`}
                  className={styles.nowPlayingTitle}
                >
                  {currentVideo.title}
                </Link>
              </div>
            )}
          </div>

          {/* Queue panel */}
          <div className={styles.queuePanel}>
            <div className={styles.queueCard}>
              <div className={styles.queueHeader}>
                <h2 className={styles.queueHeaderTitle}>
                  Queue
                </h2>
              </div>
              <div className={styles.queueList}>
                {playlist.videos.map((video, index) => (
                  <button
                    key={video.id}
                    onClick={() => {
                      setCurrentIndex(index);
                      setEnded(false);
                    }}
                    className={`${styles.queueItem} ${
                      index === currentIndex && !ended ? styles.queueItemActive : ""
                    }`}
                    aria-label={`Play ${video.title}`}
                    aria-current={index === currentIndex && !ended ? "true" : undefined}
                  >
                    {/* Thumbnail */}
                    <div className={styles.queueThumb}>
                      {video.thumbnailUrl ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={video.thumbnailUrl}
                          alt={video.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className={styles.queueThumbPlaceholder}>
                          —
                        </div>
                      )}
                      {/* Position badge */}
                      <span className="absolute bottom-0.5 right-0.5 bg-black/70 text-white text-[10px] px-1 rounded">
                        {index + 1}
                      </span>
                    </div>

                    {/* Title */}
                    <p className={styles.queueItemTitle}>
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
  videoRepository: VideoRepository;
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
  videoRepository,
}: PlaylistVideoPlayerWrapperProps) {
  // The HLS manifest URL for this video.
  const [hlsUrl, setHlsUrl] = useState<string | null>(null);
  const [videoLoading, setVideoLoading] = useState(true);
  const [videoError, setVideoError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setVideoLoading(true);
    setVideoError(false);
    setHlsUrl(null);

    async function loadVideo() {
      try {
        const detail = await videoRepository.getByID(videoID);
        if (cancelled) return;
        if (detail === null) {
          setVideoError(true);
        } else {
          setHlsUrl(detail.hlsManifestUrl ?? null);
        }
      } catch {
        if (!cancelled) setVideoError(true);
      } finally {
        if (!cancelled) setVideoLoading(false);
      }
    }

    loadVideo();

    return () => {
      cancelled = true;
    };
  }, [videoID, videoRepository]);

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
  const cleanupRef = useRef<() => void>(() => {});
  const setupRef = useRef(setup);

  // Keep setupRef current without invalidating the stable callback.
  useEffect(() => {
    setupRef.current = setup;
  });

  return useCallback((node: T | null) => {
    cleanupRef.current?.();
    const cleanup = setupRef.current(node);
    cleanupRef.current = cleanup ?? (() => {});
  }, []); // stable — no deps needed
}
