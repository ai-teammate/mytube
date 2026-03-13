"use client";

import { useState, useEffect } from "react";
import type { RecommendationRepository } from "@/domain/video";
import type { VideoCardItem } from "@/domain/search";
import VideoCard from "@/components/VideoCard";
import styles from "./RecommendationSidebar.module.css";

const MIN_RECOMMENDATIONS = 2;

interface RecommendationSidebarProps {
  videoID: string;
  repository: RecommendationRepository;
}

/**
 * RecommendationSidebar fetches and displays videos related to the currently
 * playing video. Shows a skeleton loader while fetching. Hides entirely when
 * fewer than 2 recommendations are available or when the fetch fails.
 */
export default function RecommendationSidebar({
  videoID,
  repository,
}: RecommendationSidebarProps) {
  const [recommendations, setRecommendations] = useState<VideoCardItem[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function loadRecommendations() {
      setLoading(true);
      try {
        const data = await repository.getRecommendations(videoID);
        if (!cancelled) {
          setRecommendations(data);
        }
      } catch {
        if (!cancelled) {
          // Silently hide the section on error — consistent with <2-results rule.
          setRecommendations([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadRecommendations();
    return () => {
      cancelled = true;
    };
  }, [videoID, repository]);

  if (loading) {
    return (
      <div className={styles.section} aria-label="Loading recommendations">
        <div className={styles.skeleton} aria-hidden="true">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className={styles.skeletonCard} />
          ))}
        </div>
      </div>
    );
  }

  if (!recommendations || recommendations.length < MIN_RECOMMENDATIONS) {
    return null;
  }

  return (
    <div className={styles.section}>
      <h2 className={styles.heading}>More like this</h2>
      <div className={styles.list}>
        {recommendations.map((video) => (
          <VideoCard key={video.id} video={video} />
        ))}
      </div>
    </div>
  );
}
