"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import type { VideoCardItem, SearchRepository } from "@/domain/search";
import { ApiSearchRepository } from "@/data/searchRepository";
import VideoCard from "@/components/VideoCard";

const defaultRepository: SearchRepository = new ApiSearchRepository();

interface SearchPageProps {
  repository?: SearchRepository;
}

function SearchResults({ repository = defaultRepository }: SearchPageProps) {
  const searchParams = useSearchParams();
  const query = searchParams.get("q") ?? "";

  const [videos, setVideos] = useState<VideoCardItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function loadResults() {
      setLoading(true);
      setError(null);
      try {
        const results = await repository.search(query, undefined, 20, 0);
        if (cancelled) return;
        setVideos(results);
      } catch {
        if (!cancelled) {
          setError("Could not load search results. Please try again later.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadResults();
    return () => {
      cancelled = true;
    };
  }, [query, repository]);

  return (
    <main className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-xl font-semibold text-gray-900 mb-6">
        {query ? (
          <>
            Search results for{" "}
            <span className="text-blue-600 font-bold">&ldquo;{query}&rdquo;</span>
          </>
        ) : (
          "Search"
        )}
      </h1>

      {loading && (
        <p className="text-gray-500 text-center py-16">Loading…</p>
      )}

      {error && (
        <p role="alert" className="text-red-600 text-center py-8">
          {error}
        </p>
      )}

      {!loading && !error && videos.length === 0 && (
        <p className="text-gray-500 text-center py-8">No videos found.</p>
      )}

      {!loading && !error && videos.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {videos.map((video) => (
            <VideoCard key={video.id} video={video} />
          ))}
        </div>
      )}
    </main>
  );
}

export default function SearchPageClient({ repository = defaultRepository }: SearchPageProps) {
  return (
    <Suspense fallback={<p className="text-gray-500 text-center py-16">Loading…</p>}>
      <SearchResults repository={repository} />
    </Suspense>
  );
}
