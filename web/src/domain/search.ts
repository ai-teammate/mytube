// Domain layer: entities and repository interfaces for search and discovery.
// No framework dependencies.

/** A video card as shown in search results, homepage, and category browse. */
export interface VideoCardItem {
  id: string;
  title: string;
  thumbnailUrl: string | null;
  viewCount: number;
  uploaderUsername: string;
  createdAt: string; // ISO-8601
}

/** A category as returned by GET /api/categories. */
export interface Category {
  id: number;
  name: string;
}

/** Repository interface for search. */
export interface SearchRepository {
  search(query: string, categoryId?: number, limit?: number, offset?: number): Promise<VideoCardItem[]>;
}

/** Repository interface for discovery (recent + popular). */
export interface DiscoveryRepository {
  getRecent(limit?: number): Promise<VideoCardItem[]>;
  getPopular(limit?: number): Promise<VideoCardItem[]>;
}

/** Repository interface for categories. */
export interface CategoryRepository {
  getAll(): Promise<Category[]>;
  getVideosByCategory(categoryId: number, limit?: number, offset?: number): Promise<VideoCardItem[]>;
}
