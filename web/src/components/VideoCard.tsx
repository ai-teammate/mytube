"use client";

import Image from "next/image";
import type { VideoCardItem } from "@/domain/search";

interface VideoCardProps {
  video: VideoCardItem;
}

/**
 * VideoCard displays a video in a vertical card layout with a 16:9 thumbnail.
 * Used across the homepage, search results page, and category browse page.
 */
export default function VideoCard({ video }: VideoCardProps) {
  return (
    <div className="rounded-lg overflow-hidden bg-white shadow hover:shadow-md transition-shadow">
      {/* 16:9 Thumbnail — links to watch page */}
      <a
        href={`/v/${video.id}`}
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
      </a>

      {/* Metadata */}
      <div className="p-3">
        <a
          href={`/v/${video.id}`}
          className="text-sm font-medium text-gray-900 line-clamp-2 hover:underline"
        >
          {video.title}
        </a>
        <a
          href={`/u/${video.uploaderUsername}`}
          className="text-xs text-blue-600 hover:underline mt-1 block"
        >
          {video.uploaderUsername}
        </a>
        <p className="text-xs text-gray-500 mt-0.5">
          {video.viewCount.toLocaleString()} views &middot;{" "}
          {new Date(video.createdAt).toLocaleDateString()}
        </p>
      </div>
    </div>
  );
}
