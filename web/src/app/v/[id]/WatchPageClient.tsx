"use client";

import { use, useState, useEffect } from "react";
import Image from "next/image";
import type { VideoDetail, VideoRepository } from "@/domain/video";
import { ApiVideoRepository } from "@/data/videoRepository";

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

// Default singleton repository used in production.
const defaultRepository: VideoRepository = new ApiVideoRepository();

interface WatchPageProps {
  // Next.js 15+ passes params as a Promise; unwrap with React.use().
  params: Promise<{ id: string }>;
  // Optional repository for dependency injection (e.g. in tests).
  repository?: VideoRepository;
}

export default function WatchPage({
  params,
  repository = defaultRepository,
}: WatchPageProps) {
  const { id } = use(params);

  const [video, setVideo] = useState<VideoDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
        <p className="text-gray-500">Video not found.</p>
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

  if (!video) return null;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto px-4 py-6">
        {/* Video player */}
        <div className="w-full bg-black rounded-lg overflow-hidden mb-4">
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

        {/* Video metadata */}
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          {video.title}
        </h1>

        {/* Uploader and view count row */}
        <div className="flex items-center gap-3 mb-4">
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
              className="w-9 h-9 rounded-full bg-gray-300 flex items-center justify-center text-sm font-bold text-gray-600"
              aria-label={`${video.uploader.username}'s avatar`}
            >
              {video.uploader.username.charAt(0).toUpperCase()}
            </div>
          )}
          <a
            href={`/u/${video.uploader.username}`}
            className="text-sm font-medium text-gray-900 hover:underline"
          >
            {video.uploader.username}
          </a>
          <span className="text-sm text-gray-500 ml-auto">
            {video.viewCount.toLocaleString()} views ·{" "}
            {new Date(video.createdAt).toLocaleDateString()}
          </span>
        </div>

        {/* Tags */}
        {video.tags.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {video.tags.map((tag) => (
              <span
                key={tag}
                className="px-3 py-1 text-xs font-medium bg-gray-100 text-gray-700 rounded-full"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* Description */}
        {video.description && (
          <div className="bg-white rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap">
            {video.description}
          </div>
        )}
      </div>
    </div>
  );
}
