// Data layer: HTTP repository implementation for RatingRepository.
// Depends only on domain types — no React or Next.js imports.

import type { RatingSummary, RatingRepository } from "@/domain/rating";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

/**
 * ApiRatingRepository fetches and submits video ratings via the backend API.
 */
export class ApiRatingRepository implements RatingRepository {
  private readonly baseUrl: string;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl;
  }

  async getSummary(videoID: string, token: string | null): Promise<RatingSummary> {
    const headers: Record<string, string> = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const res = await fetch(
      `${this.baseUrl}/api/videos/${encodeURIComponent(videoID)}/rating`,
      { headers }
    );

    if (!res.ok) {
      throw new Error(`Failed to fetch rating for ${videoID}: ${res.status}`);
    }

    const data = await res.json();
    return mapRatingSummary(data);
  }

  async submitRating(videoID: string, stars: number, token: string): Promise<RatingSummary> {
    const res = await fetch(
      `${this.baseUrl}/api/videos/${encodeURIComponent(videoID)}/rating`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ stars }),
      }
    );

    if (!res.ok) {
      throw new Error(`Failed to submit rating for ${videoID}: ${res.status}`);
    }

    const data = await res.json();
    return mapRatingSummary(data);
  }
}

function mapRatingSummary(data: {
  average_rating: number;
  rating_count: number;
  my_rating: number | null;
}): RatingSummary {
  return {
    averageRating: data.average_rating,
    ratingCount: data.rating_count,
    myRating: data.my_rating ?? null,
  };
}
