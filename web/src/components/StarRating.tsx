"use client";

import { useState, useEffect } from "react";
import type { RatingSummary, RatingRepository } from "@/domain/rating";
import styles from "./StarRating.module.css";

interface StarRatingProps {
  videoID: string;
  repository: RatingRepository;
  /** Returns the current Firebase ID token, or null if not authenticated. */
  getToken: () => Promise<string | null>;
  /** True if the auth state is still being resolved. */
  authLoading?: boolean;
}

/**
 * StarRating renders a 1–5 star rating widget.
 *
 * - Shows average rating and count.
 * - Authenticated users can click a star to rate (set-only for MVP).
 * - Errors shown as inline text (no toast library dependency).
 */
export default function StarRating({
  videoID,
  repository,
  getToken,
  authLoading = false,
}: StarRatingProps) {
  const [summary, setSummary] = useState<RatingSummary | null>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    getToken().then((t) => {
      if (!cancelled) setIsAuthenticated(t !== null);
    });
    return () => {
      cancelled = true;
    };
  }, [authLoading, getToken]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const token = await getToken();
        const data = await repository.getSummary(videoID, token);
        if (!cancelled) setSummary(data);
      } catch {
        // Non-critical: rating widget failure should not block the page.
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [videoID, repository, getToken]);

  async function handleStarClick(stars: number) {
    setError(null);
    setSubmitting(true);
    try {
      const token = await getToken();
      if (!token) {
        setError("Please log in to rate this video.");
        return;
      }
      const updated = await repository.submitRating(videoID, stars, token);
      setSummary(updated);
    } catch {
      setError("Could not submit rating. Please try again.");
      // Restore the actual server state by refetching the summary
      try {
        const token = await getToken();
        const current = await repository.getSummary(videoID, token);
        setSummary(current);
      } catch {
        // Non-critical: if refresh fails, keep the error message displayed
      }
    } finally {
      setSubmitting(false);
    }
  }

  const displayRating = summary?.averageRating ?? 0;
  const displayCount = summary?.ratingCount ?? 0;
  const myRating = summary?.myRating ?? null;

  // Stars to display: hover state > my rating > nothing (empty stars)
  const activeStars = hovered ?? myRating ?? 0;

  return (
    <div className={styles.container}>
      <p className={styles.heading}>Rate this video</p>
      <div className={styles.ratingRow}>
        <div
          className={styles.starsGroup}
          role="group"
          aria-label="Star rating"
        >
          {[1, 2, 3, 4, 5].map((star) => (
            <button
              key={star}
              type="button"
              aria-label={`Rate ${star} star${star !== 1 ? "s" : ""}`}
              aria-pressed={myRating === star}
              disabled={submitting || authLoading}
              onClick={() => handleStarClick(star)}
              onMouseEnter={() => setHovered(star)}
              onMouseLeave={() => setHovered(null)}
              className={`${styles.starButton} ${star <= activeStars ? styles.starFilled : ""}`}
            >
              ★
            </button>
          ))}
        </div>

        {summary !== null && (
          <span className={styles.ratingSummary}>
            {displayCount > 0
              ? `${displayRating.toFixed(1)} / 5 (${displayCount.toLocaleString()})`
              : "No ratings yet"}
          </span>
        )}
      </div>

      {!isAuthenticated && !authLoading && (
        <p className={styles.loginPrompt}>
          <a href="/login" className={styles.loginLink}>
            Log in
          </a>{" "}
          to rate this video.
        </p>
      )}

      {error && (
        <p role="alert" className={styles.errorText}>
          {error}
        </p>
      )}
    </div>
  );
}
