"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback } from "react";
import { useRouter } from "next/navigation";
import type { VideoCardItem } from "@/domain/search";

interface VideoCardProps {
  video: VideoCardItem;
}

/**
 * VideoCard displays a video in a vertical card layout with a 16:9 thumbnail.
 * Used across the homepage, search results page, and category browse page.
 */
export default function VideoCard({ video }: VideoCardProps) {
  const router = useRouter();

  // GitHub Pages static export only pre-builds /v/_/ as the watch-page shell.
  // Direct client-side navigation to /v/<uuid> bypasses the 404.html SPA
  // fallback and causes the Next.js router to render its own 404 page.
  // Instead, store the real video ID in sessionStorage and navigate to the
  // pre-built shell so WatchPageClient can resolve it.
  const handleWatchClick = useCallback(
    (e: React.MouseEvent<HTMLAnchorElement>) => {
      // Let modifier-key clicks (new tab / new window) and non-primary-button
      // clicks fall through to native browser behaviour.
      // 404.html SPA fallback handles the resulting hard navigation correctly.
      if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
      e.preventDefault();
      sessionStorage.setItem("__spa_video_id", video.id);
      router.push("/v/_/");
    },
    [video.id, router]
  );

  return (
    <div className="rounded-lg overflow-hidden bg-white shadow hover:shadow-md transition-shadow">
      {/* 16:9 Thumbnail — links to watch page */}
      <Link
        href={`/v/${video.id}`}
        onClick={handleWatchClick}
        aria-label={video.title}
        className="block relative w-full aspect-video bg-gray-200"
      >
        {video.thumbnailUrl ? (
          <Image
            src={video.thumbnailUrl}
            alt={video.title}
            fill
            className="object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-400 text-sm">
            No thumbnail
          </div>
        )}
      </Link>
      <div className="p-3">
        <Link
          href={`/v/${video.id}`}
          onClick={handleWatchClick}
          className="text-sm font-medium text-gray-900 line-clamp-2 hover:underline"
        >
          {video.title}
        </Link>
        <Link
          href={`/u/${video.uploaderUsername}`}
          className="text-xs text-blue-600 hover:underline mt-1 block"
        >
          {video.uploaderUsername}
        </Link>
        <p className="text-xs text-gray-500 mt-0.5">
          {video.viewCount.toLocaleString()} views &middot;{" "}
          {new Date(video.createdAt).toLocaleDateString()}
        </p>
      </div>
    </div>
  );
}
