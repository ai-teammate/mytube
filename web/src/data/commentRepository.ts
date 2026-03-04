// Data layer: HTTP repository implementation for CommentRepository.
// Depends only on domain types — no React or Next.js imports.

import type { Comment, CommentRepository } from "@/domain/comment";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

/**
 * ApiCommentRepository manages video comments via the backend API.
 */
export class ApiCommentRepository implements CommentRepository {
  private readonly baseUrl: string;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl;
  }

  async listByVideoID(videoID: string): Promise<Comment[]> {
    const res = await fetch(
      `${this.baseUrl}/api/videos/${encodeURIComponent(videoID)}/comments`
    );

    if (!res.ok) {
      throw new Error(`Failed to fetch comments for ${videoID}: ${res.status}`);
    }

    const data = await res.json();
    return (data as RawComment[]).map(mapComment);
  }

  async create(videoID: string, body: string, token: string): Promise<Comment> {
    const res = await fetch(
      `${this.baseUrl}/api/videos/${encodeURIComponent(videoID)}/comments`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ body }),
      }
    );

    if (!res.ok) {
      throw new Error(`Failed to create comment for ${videoID}: ${res.status}`);
    }

    const data = await res.json();
    return mapComment(data);
  }

  async deleteComment(commentID: string, token: string): Promise<void> {
    const res = await fetch(
      `${this.baseUrl}/api/comments/${encodeURIComponent(commentID)}`,
      {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    if (!res.ok) {
      throw new Error(`Failed to delete comment ${commentID}: ${res.status}`);
    }
  }
}

interface RawComment {
  id: string;
  body: string;
  author: {
    username: string;
    avatar_url: string | null;
  };
  created_at: string;
}

function mapComment(data: RawComment): Comment {
  return {
    id: data.id,
    body: data.body,
    author: {
      username: data.author.username,
      avatarUrl: data.author.avatar_url ?? null,
    },
    createdAt: data.created_at,
  };
}
