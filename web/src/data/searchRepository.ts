// Data layer: HTTP repository implementations for search and discovery.
// Depends only on domain types — no React or Next.js imports.

import type {
  VideoCardItem,
  Category,
  SearchRepository,
  DiscoveryRepository,
  CategoryRepository,
} from "@/domain/search";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

/** Maps a raw API video card object to the domain VideoCardItem type. */
function mapVideoCard(data: {
  id: string;
  title: string;
  thumbnail_url: string | null;
  view_count: number;
  uploader_username: string;
  created_at: string;
}): VideoCardItem {
  return {
    id: data.id,
    title: data.title,
    thumbnailUrl: data.thumbnail_url ?? null,
    viewCount: data.view_count,
    uploaderUsername: data.uploader_username,
    createdAt: data.created_at,
  };
}

/**
 * ApiSearchRepository implements SearchRepository against the backend API.
 */
export class ApiSearchRepository implements SearchRepository {
  private readonly baseUrl: string;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl;
  }

  async search(
    query: string,
    categoryId?: number,
    limit = 20,
    offset = 0
  ): Promise<VideoCardItem[]> {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (categoryId !== undefined) params.set("category_id", String(categoryId));
    params.set("limit", String(limit));
    params.set("offset", String(offset));

    const res = await fetch(`${this.baseUrl}/api/search?${params.toString()}`);

    if (!res.ok) {
      throw new Error(`Search failed: ${res.status}`);
    }

    const data = await res.json();
    return (data ?? []).map(mapVideoCard);
  }
}

/**
 * ApiDiscoveryRepository implements DiscoveryRepository against the backend API.
 */
export class ApiDiscoveryRepository implements DiscoveryRepository {
  private readonly baseUrl: string;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl;
  }

  async getRecent(limit = 20): Promise<VideoCardItem[]> {
    const res = await fetch(
      `${this.baseUrl}/api/videos/recent?limit=${limit}`
    );

    if (!res.ok) {
      throw new Error(`Failed to fetch recent videos: ${res.status}`);
    }

    const data = await res.json();
    return (data ?? []).map(mapVideoCard);
  }

  async getPopular(limit = 20): Promise<VideoCardItem[]> {
    const res = await fetch(
      `${this.baseUrl}/api/videos/popular?limit=${limit}`
    );

    if (!res.ok) {
      throw new Error(`Failed to fetch popular videos: ${res.status}`);
    }

    const data = await res.json();
    return (data ?? []).map(mapVideoCard);
  }
}

/**
 * ApiCategoryRepository implements CategoryRepository against the backend API.
 */
export class ApiCategoryRepository implements CategoryRepository {
  private readonly baseUrl: string;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl;
  }

  async getAll(): Promise<Category[]> {
    const res = await fetch(`${this.baseUrl}/api/categories`);

    if (!res.ok) {
      throw new Error(`Failed to fetch categories: ${res.status}`);
    }

    const data = await res.json();
    return (data ?? []).map(
      (c: { id: number; name: string }) => ({ id: c.id, name: c.name })
    );
  }

  async getVideosByCategory(
    categoryId: number,
    limit = 20,
    offset = 0
  ): Promise<VideoCardItem[]> {
    const params = new URLSearchParams({
      category_id: String(categoryId),
      limit: String(limit),
      offset: String(offset),
    });

    const res = await fetch(
      `${this.baseUrl}/api/videos?${params.toString()}`
    );

    if (!res.ok) {
      throw new Error(
        `Failed to fetch videos for category ${categoryId}: ${res.status}`
      );
    }

    const data = await res.json();
    return (data ?? []).map(mapVideoCard);
  }
}
