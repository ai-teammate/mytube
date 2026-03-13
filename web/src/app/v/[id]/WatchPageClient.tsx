"use client";

import { use, useState, useEffect, useCallback } from "react";
import Image from "next/image";
import Link from "next/link";
import type { VideoDetail, VideoRepository, RecommendationRepository } from "@/domain/video";
import type { RatingRepository } from "@/domain/rating";
import type { CommentRepository } from "@/domain/comment";
import type { PlaylistRepository } from "@/domain/playlist";
import { ApiVideoRepository } from "@/data/videoRepository";
import { ApiRecommendationRepository } from "@/data/videoRepository";
import { ApiRatingRepository } from "@/data/ratingRepository";
import { ApiCommentRepository } from "@/data/commentRepository";
import { ApiPlaylistRepository } from "@/data/playlistRepository";
import { useAuth } from "@/context/AuthContext";
import StarRating from "@/components/StarRating";
import CommentSection from "@/components/CommentSection";
import SaveToPlaylist from "@/components/SaveToPlaylist";
import RecommendationSidebar from "@/components/RecommendationSidebar";
import styles from "./WatchPageClient.module.css";
import WatchPageSkeleton from "./WatchPageSkeleton";

// Lazy-load VideoPlayer to keep the static shell lightweight.
import dynamic from "next/dynamic";
const VideoPlayer = dynamic(() => import("@/components/VideoPlayer"), {
  ssr: false,
  loading: () => (
    <div className="w-full aspect-video bg-black flex items-center justify-center">
      <p className="text-gray-400">Loading player…</p>
    </div>
  ),
});

// Default singleton repositories used in production.
const defaultRepository: VideoRepository = new ApiVideoRepository();
const defaultRecommendationRepository: RecommendationRepository = new ApiRecommendationRepository();
const defaultRatingRepository: RatingRepository = new ApiRatingRepository();
const defaultCommentRepository: CommentRepository = new ApiCommentRepository();
const defaultPlaylistRepository: PlaylistRepository = new ApiPlaylistRepository();

interface WatchPageProps {
  // Next.js 15+ passes params as a Promise; unwrap with React.use().
  params: Promise<{ id: string }>;
  // Optional repositories for dependency injection (e.g. in tests).
  repository?: VideoRepository;
  recommendationRepository?: RecommendationRepository;
  ratingRepository?: RatingRepository;
  commentRepository?: CommentRepository;
  playlistRepository?: PlaylistRepository;
}

export default function WatchPage({
  params,
  repository = defaultRepository,
  recommendationRepository = defaultRecommendationRepository,
  ratingRepository = defaultRatingRepository,
  commentRepository = defaultCommentRepository,
  playlistRepository = defaultPlaylistRepository,
}: WatchPageProps) {
  const { id: paramId } = use(params);

  // GitHub Pages SPA fallback: public/404.html stores the real video UUID in
  // sessionStorage under '__spa_video_id' and redirects to the pre-built shell
  // at /v/_/. Resolve the actual ID once at mount via a lazy state initialiser
  // so the loadVideo effect always sees the correct UUID on its first run.
  const [id] = useState<string>(() => {
    if (paramId !== "_" || typeof window === "undefined") return paramId;
    const storedId = sessionStorage.getItem("__spa_video_id");
    if (storedId) {
      sessionStorage.removeItem("__spa_video_id");
      return storedId;
    }
    return paramId;
  });

  // Correct the browser URL so the address bar shows /v/<real-uuid>/ instead
  // of the placeholder /v/_/. Runs once after mount.
  useEffect(() => {
    if (id !== paramId && paramId === "_" && typeof window !== "undefined") {
      const corrected = window.location.pathname.replace(
        "/v/_/",
        `/v/${id}/`
      );
      window.history.replaceState(null, "", corrected);
    }
    // Only run once at mount — id and paramId are stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { user, getIdToken, loading: authLoading } = useAuth();

  const [video, setVideo] = useState<VideoDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Start as true so the skeleton is visible while the first fetch is in-flight.
  // Reset to true whenever the video id changes so a new fetch is always attempted.
  const [hasRecommendations, setHasRecommendations] = useState(true);
  useEffect(() => {
    setHasRecommendations(true);
  }, [id]);

  useEffect(() => {
    let cancelled = false;

    async function loadVideo() {
      try {
        const data = await repository.getByID(id);
        if (cancelled) return;
        if (data === null) {
          setNotFound(true);
        } else {
          setVideo(data);
        }
      } catch {
        if (!cancelled) {
          setError("Could not load video. Please try again later.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadVideo();
    return () => {
      cancelled = true;
    };
  }, [id, repository]);

  // Set OG meta tags via DOM for social sharing.
  // Note: With Next.js static export (CSR), these are rendered client-side and
  // may not be visible to crawlers. This is a known trade-off of the static
  // export architecture (MYTUBE-123 Option A). A separate server-side meta
  // proxy can be added in a follow-up ticket.
  useEffect(() => {
    if (!video) return;

    document.title = video.title;

    const setMeta = (property: string, content: string) => {
      let el = document.querySelector<HTMLMetaElement>(
        `meta[property="${property}"]`
      );
      if (!el) {
        el = document.createElement("meta");
        el.setAttribute("property", property);
        document.head.appendChild(el);
      }
      el.setAttribute("content", content);
    };

    setMeta("og:title", video.title);
    if (video.thumbnailUrl) {
      setMeta("og:image", video.thumbnailUrl);
    }
  }, [video]);

  // Stable token getter passed to child components.
  const getToken = useCallback(() => getIdToken(), [getIdToken]);

  if (loading) {
    return <WatchPageSkeleton />;
  }

  if (notFound) {
    return (
      <div className={styles.stateContainer}>
        <p className={styles.stateText}>Video not found.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.stateContainer}>
        <p role="alert" className={styles.stateError}>
          {error}
        </p>
      </div>
    );
  }

  if (!video) return null;

  return (
    <div className={styles.watchLayout}>
      {/* Main content: player + metadata (left column) */}
      <main>
        {/* Player container */}
        <div className={styles.player}>
          {video.hlsManifestUrl ? (
            <VideoPlayer
              src={video.hlsManifestUrl}
              poster={video.thumbnailUrl}
            />
          ) : (
            <div className="w-full aspect-video flex items-center justify-center">
              <p className="text-gray-400">Video not available yet.</p>
            </div>
          )}
        </div>

        {/* Video title */}
        <h1 className={styles.videoTitle}>{video.title}</h1>

        {/* Uploader row */}
        <div className={styles.uploaderRow}>
          {video.uploader.avatarUrl ? (
            <Image
              src={video.uploader.avatarUrl}
              alt={`${video.uploader.username}'s avatar`}
              width={36}
              height={36}
              className="rounded-full object-cover"
            />
          ) : (
            <div
              className={styles.uploaderInitials}
              aria-label={`${video.uploader.username}'s avatar`}
            >
              {video.uploader.username.charAt(0).toUpperCase()}
            </div>
          )}
          <Link
            href={`/u/${video.uploader.username}`}
            className={styles.uploaderName}
          >
            {video.uploader.username}
          </Link>
        </div>

        {/* Meta line: views · date */}
        <div className={styles.metaLine}>
          <span>{video.viewCount.toLocaleString()} views</span>
          <span aria-hidden="true">·</span>
          <span>{new Date(video.createdAt).toLocaleDateString()}</span>
        </div>

        {/* Tags */}
        {video.tags.length > 0 && (
          <div className={styles.tagsRow}>
            {video.tags.map((tag) => (
              <span key={tag} className={styles.tagPill}>
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* Actions row: star rating + save to playlist */}
        <div className={styles.actionsRow}>
          <StarRating
            videoID={id}
            repository={ratingRepository}
            getToken={getToken}
            authLoading={authLoading}
          />
          <SaveToPlaylist
            videoID={id}
            repository={playlistRepository}
            getToken={getToken}
            hidden={authLoading || !user}
          />
        </div>

        {/* Description */}
        {video.description && (
          <div className={styles.description}>{video.description}</div>
        )}

        {/* Comment section */}
        <CommentSection
          videoID={id}
          repository={commentRepository}
          getToken={getToken}
          authLoading={authLoading}
        />
      </main>

      {/* Sidebar: recommendations (right column at lg+).
          Hidden (aside unmounted) when the sidebar signals <2 results or an
          error via onHasRecommendations. Resets to visible on each id change
          so new videos always attempt a fresh fetch. */}
      {hasRecommendations && (
        <aside className={styles.sidebar}>
          <RecommendationSidebar
            videoID={id}
            repository={recommendationRepository}
            onHasRecommendations={setHasRecommendations}
          />
        </aside>
      )}
    </div>
  );
}
