"use client";

import { use, useState, useEffect } from "react";
import type { VideoCardItem, CategoryRepository, Category } from "@/domain/search";
import { ApiCategoryRepository } from "@/data/searchRepository";
import VideoCard from "@/components/VideoCard";
import SiteHeader from "@/components/SiteHeader";

const defaultRepository: CategoryRepository = new ApiCategoryRepository();

interface CategoryPageProps {
  params: Promise<{ id: string }>;
  repository?: CategoryRepository;
}

export default function CategoryPage({
  params,
  repository = defaultRepository,
}: CategoryPageProps) {
  const { id } = use(params);
  const categoryId = parseInt(id, 10);

  const [videos, setVideos] = useState<VideoCardItem[]>([]);
  const [category, setCategory] = useState<Category | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isNaN(categoryId)) {
      setError("Invalid category.");
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function loadCategory() {
      try {
        const [cats, vids] = await Promise.all([
          repository.getAll(),
          repository.getVideosByCategory(categoryId, 20, 0),
        ]);
        if (cancelled) return;
        const found = cats.find((c) => c.id === categoryId) ?? null;
        setCategory(found);
        setVideos(vids);
      } catch {
        if (!cancelled) {
          setError("Could not load category. Please try again later.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadCategory();
    return () => {
      cancelled = true;
    };
  }, [categoryId, repository]);

  return (
    <div className="min-h-screen bg-gray-50">
      <SiteHeader />

      <main className="max-w-7xl mx-auto px-4 py-8">
        {loading && (
          <p className="text-gray-500 text-center py-16">Loading…</p>
        )}

        {error && !loading && (
          <p role="alert" className="text-red-600 text-center py-8">
            {error}
          </p>
        )}

        {!loading && !error && (
          <>
            <h1 className="text-2xl font-bold text-gray-900 mb-6">
              {category ? category.name : `Category ${categoryId}`}
            </h1>

            {videos.length === 0 ? (
              <p className="text-gray-500">No videos in this category yet.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {videos.map((video) => (
                  <VideoCard key={video.id} video={video} />
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
