// Data layer: HTTP repository implementation for VideoRepository.
// Depends only on domain types — no React or Next.js imports.

import type { VideoDetail, VideoRepository, RecommendationRepository } from "@/domain/video";
import type { VideoCardItem } from "@/domain/search";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

/**
 * ApiVideoRepository fetches video details from the backend API.
 */
export class ApiVideoRepository implements VideoRepository {
  private readonly baseUrl: string;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl;
  }

  async getByID(videoID: string): Promise<VideoDetail | null> {
    const res = await fetch(
      `${this.baseUrl}/api/videos/${encodeURIComponent(videoID)}`
    );

    if (res.status === 404) {
      return null;
    }

    if (!res.ok) {
      throw new Error(`Failed to fetch video ${videoID}: ${res.status}`);
    }

    // Map snake_case API response to camelCase domain type.
    const data = await res.json();
    return {
      id: data.id,
      title: data.title,
      description: data.description ?? null,
      hlsManifestUrl: data.hls_manifest_url ?? null,
      thumbnailUrl: data.thumbnail_url ?? null,
      viewCount: data.view_count,
      createdAt: data.created_at,
      status: data.status,
      uploader: {
        username: data.uploader.username,
        avatarUrl: data.uploader.avatar_url ?? null,
      },
      tags: data.tags ?? [],
    };
  }
}

/**
 * ApiRecommendationRepository fetches video recommendations from the backend API.
 */
export class ApiRecommendationRepository implements RecommendationRepository {
  private readonly baseUrl: string;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl;
  }

  async getRecommendations(videoID: string): Promise<VideoCardItem[]> {
    const res = await fetch(
      `${this.baseUrl}/api/videos/${encodeURIComponent(videoID)}/recommendations`
    );

    if (!res.ok) {
      throw new Error(
        `Failed to fetch recommendations for ${videoID}: ${res.status}`
      );
    }

    const data = await res.json();
    const items: { id: string; title: string; thumbnail_url: string | null; view_count: number; uploader_username: string; created_at: string }[] =
      data.recommendations ?? [];

    return items.map((item) => ({
      id: item.id,
      title: item.title,
      thumbnailUrl: item.thumbnail_url ?? null,
      viewCount: item.view_count,
      uploaderUsername: item.uploader_username,
      createdAt: item.created_at,
    }));
  }
}
