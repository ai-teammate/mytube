"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import type { VideoCardItem } from "@/domain/search";
import styles from "./VideoCard.module.css";

const MAX_VISIBLE_TAGS = 3;

interface VideoCardProps {
  video: VideoCardItem;
}

/**
 * VideoCard displays a video in a styled card layout with a 16:9 thumbnail,
 * HD quality overlay, title, sub-line (uploader · views · date), and optional
 * tag pills. Used across the homepage, search results, and category browse.
 */
export default function VideoCard({ video }: VideoCardProps) {
  const router = useRouter();
  const [imgLoaded, setImgLoaded] = useState(false);

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

  const tags = video.tags ?? [];
  const visibleTags = tags.slice(0, MAX_VISIBLE_TAGS);
  const overflowCount = tags.length - visibleTags.length;

  return (
    <div className={styles.card}>
      {/* Thumbnail — links to watch page */}
      <Link
        href={`/v/${video.id}`}
        onClick={handleWatchClick}
        aria-label={video.title}
        className={styles.thumb}
      >
        {video.thumbnailUrl ? (
          <Image
            src={video.thumbnailUrl}
            alt={video.title}
            fill
            className={`object-cover ${imgLoaded ? styles.loaded : ""}`}
            onLoad={() => setImgLoaded(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-400 text-sm">
            No thumbnail
          </div>
        )}
      </Link>

      <div className={styles.body}>
        {/* Title — two-line clamp */}
        <Link
          href={`/v/${video.id}`}
          onClick={handleWatchClick}
          className={styles.videoTitle}
        >
          {video.title}
        </Link>

        {/* Sub-line: uploader · view count · date */}
        <div className={styles.videoSub}>
          <Link href={`/u/${video.uploaderUsername}`} className={styles.videoSubLink}>
            {video.uploaderUsername}
          </Link>
          <span aria-hidden="true">·</span>
          <span>{video.viewCount.toLocaleString()} views</span>
          <span aria-hidden="true">·</span>
          <span>{new Date(video.createdAt).toLocaleDateString()}</span>
        </div>

        {/* Tags row — max 3 visible tags with "+N more" overflow indicator */}
        {visibleTags.length > 0 && (
          <div className={styles.videoTags}>
            {visibleTags.map((tag) => (
              <span key={tag} className={styles.tagPill}>
                {tag}
              </span>
            ))}
            {overflowCount > 0 && (
              <span className={styles.tagOverflow}>+{overflowCount} more</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
