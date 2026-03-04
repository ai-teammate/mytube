// Domain layer: entities and repository interface for video ratings.
// No framework dependencies.

/** Aggregated rating data for a video. */
export interface RatingSummary {
  averageRating: number;
  ratingCount: number;
  /** null when the viewer is not authenticated or has not rated. */
  myRating: number | null;
}

/** Repository interface for video ratings. */
export interface RatingRepository {
  getSummary(videoID: string, token: string | null): Promise<RatingSummary>;
  submitRating(videoID: string, stars: number, token: string): Promise<RatingSummary>;
}
