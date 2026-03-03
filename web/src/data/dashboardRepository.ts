// Data layer: HTTP repository implementations for the dashboard domain.
// Depends only on domain types — no React or Next.js imports.

import type {
  DashboardVideo,
  DashboardVideoRepository,
  UpdateVideoParams,
  UpdatedVideo,
  VideoManagementRepository,
} from "@/domain/dashboard";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

/**
 * ApiDashboardVideoRepository calls GET /api/me/videos to fetch the
 * authenticated user's video list.
 */
export class ApiDashboardVideoRepository implements DashboardVideoRepository {
  private readonly baseUrl: string;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl;
  }

  async listMyVideos(token: string): Promise<DashboardVideo[]> {
    const res = await fetch(`${this.baseUrl}/api/me/videos`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.error ?? `Failed to fetch videos: ${res.status}`);
    }

    const data: Array<{
      id: string;
      title: string;
      status: string;
      thumbnail_url: string | null;
      view_count: number;
      created_at: string;
      description: string | null;
      category_id: number | null;
      tags: string[];
    }> = await res.json();

    return data.map((v) => ({
      id: v.id,
      title: v.title,
      status: v.status as DashboardVideo["status"],
      thumbnailUrl: v.thumbnail_url,
      viewCount: v.view_count,
      createdAt: v.created_at,
      description: v.description ?? null,
      categoryId: v.category_id ?? null,
      tags: v.tags ?? [],
    }));
  }
}

/**
 * ApiVideoManagementRepository calls PUT /api/videos/:id and
 * DELETE /api/videos/:id for editing and deleting videos.
 */
export class ApiVideoManagementRepository implements VideoManagementRepository {
  private readonly baseUrl: string;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl;
  }

  async updateVideo(
    videoId: string,
    params: UpdateVideoParams,
    token: string
  ): Promise<UpdatedVideo> {
    const res = await fetch(`${this.baseUrl}/api/videos/${videoId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        title: params.title,
        description: params.description,
        category_id: params.categoryId,
        tags: params.tags,
      }),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.error ?? `Failed to update video: ${res.status}`);
    }

    const data = await res.json();
    return {
      id: data.id,
      title: data.title,
      description: data.description ?? null,
      status: data.status,
      thumbnailUrl: data.thumbnail_url ?? null,
      viewCount: data.view_count,
      tags: data.tags ?? [],
      uploader: {
        username: data.uploader?.username ?? "",
        avatarUrl: data.uploader?.avatar_url ?? null,
      },
    };
  }

  async deleteVideo(videoId: string, token: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/api/videos/${videoId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.error ?? `Failed to delete video: ${res.status}`);
    }
  }
}
