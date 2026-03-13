"use client";

import { useState, useEffect } from "react";
import type { VideoCardItem, DiscoveryRepository } from "@/domain/search";
import { ApiDiscoveryRepository } from "@/data/searchRepository";
import VideoCard from "@/components/VideoCard";
import HeroSection from "@/components/HeroSection";

const defaultRepository: DiscoveryRepository = new ApiDiscoveryRepository();

interface HomePageProps {
  repository?: DiscoveryRepository;
}

export default function HomePageClient({ repository = defaultRepository }: HomePageProps) {
  const [recentVideos, setRecentVideos] = useState<VideoCardItem[]>([]);
  const [popularVideos, setPopularVideos] = useState<VideoCardItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function loadVideos() {
      try {
        const [recent, popular] = await Promise.all([
          repository.getRecent(20),
          repository.getPopular(20),
        ]);
        if (cancelled) return;
        setRecentVideos(recent);
        setPopularVideos(popular);
      } catch {
        if (!cancelled) {
          setError("Could not load videos. Please try again later.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadVideos();
    return () => {
      cancelled = true;
    };
  }, [repository]);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Hero section — replaces the previous inline hero markup */}
      <HeroSection thumbnailUrl={recentVideos[0]?.thumbnailUrl} />

      {loading && (
        <p className="text-gray-500 text-center py-16">Loading…</p>
      )}

      {error && (
        <p role="alert" className="text-red-600 text-center py-16">
          {error}
        </p>
      )}

      {!loading && !error && (
        <div id="video-grid">
          {/* Recently Uploaded section */}
          <section aria-labelledby="recently-uploaded-heading" className="mb-12">
            <h2
              id="recently-uploaded-heading"
              className="text-xl font-semibold text-gray-900 mb-4"
            >
              Recently Uploaded
            </h2>
            {recentVideos.length === 0 ? (
              <p className="text-gray-500">No videos yet.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {recentVideos.map((video) => (
                  <VideoCard key={video.id} video={video} />
                ))}
              </div>
            )}
          </section>

          {/* Most Viewed section */}
          <section aria-labelledby="most-viewed-heading">
            <h2
              id="most-viewed-heading"
              className="text-xl font-semibold text-gray-900 mb-4"
            >
              Most Viewed
            </h2>
            {popularVideos.length === 0 ? (
              <p className="text-gray-500">No videos yet.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {popularVideos.map((video) => (
                  <VideoCard key={video.id} video={video} />
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
