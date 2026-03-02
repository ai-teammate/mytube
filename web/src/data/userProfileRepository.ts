// Data layer: HTTP repository implementation for UserProfileRepository.
// Depends only on domain types — no React or Next.js imports.

import type {
  UserProfile,
  UserProfileRepository,
} from "@/domain/userProfile";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

/**
 * ApiUserProfileRepository fetches user profiles from the backend API.
 */
export class ApiUserProfileRepository implements UserProfileRepository {
  private readonly baseUrl: string;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl;
  }

  async getByUsername(username: string): Promise<UserProfile | null> {
    const res = await fetch(
      `${this.baseUrl}/api/users/${encodeURIComponent(username)}`
    );

    if (res.status === 404) {
      return null;
    }

    if (!res.ok) {
      throw new Error(`Failed to fetch profile for ${username}: ${res.status}`);
    }

    // Map snake_case API response to camelCase domain type.
    const data = await res.json();
    return {
      username: data.username,
      avatarUrl: data.avatar_url ?? null,
      videos: (data.videos ?? []).map(
        (v: {
          id: string;
          title: string;
          thumbnail_url: string | null;
          view_count: number;
          created_at: string;
        }) => ({
          id: v.id,
          title: v.title,
          thumbnailUrl: v.thumbnail_url ?? null,
          viewCount: v.view_count,
          createdAt: v.created_at,
        })
      ),
    };
  }
}
