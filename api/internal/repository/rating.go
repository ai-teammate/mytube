// Package repository provides data-access objects for the mytube domain.
package repository

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
)

// RatingSummary holds aggregated rating data for a video.
type RatingSummary struct {
	AverageRating float64
	RatingCount   int64
	MyRating      *int // nil when the caller is not authenticated or has not rated
}

// RatingQuerier is the database interface used by RatingRepository.
// Satisfied by *sql.DB and allows tests to inject a stub.
type RatingQuerier interface {
	QueryRowContext(ctx context.Context, query string, args ...any) *sql.Row
	ExecContext(ctx context.Context, query string, args ...any) (sql.Result, error)
}

// RatingRepository handles persistence for the ratings table.
type RatingRepository struct {
	db RatingQuerier
}

// NewRatingRepository constructs a RatingRepository backed by db.
func NewRatingRepository(db RatingQuerier) *RatingRepository {
	return &RatingRepository{db: db}
}

// UpsertRating inserts or updates a rating for the given video and user.
// stars must be in the range 1–5; callers are responsible for validation.
// Returns the updated RatingSummary for the video.
func (r *RatingRepository) UpsertRating(ctx context.Context, videoID, userID string, stars int) (*RatingSummary, error) {
	const upsertSQL = `
INSERT INTO ratings (video_id, user_id, stars)
VALUES ($1, $2, $3)
ON CONFLICT (video_id, user_id) DO UPDATE
    SET stars = EXCLUDED.stars`

	if _, err := r.db.ExecContext(ctx, upsertSQL, videoID, userID, stars); err != nil {
		return nil, fmt.Errorf("upsert rating: %w", err)
	}

	return r.GetSummary(ctx, videoID, &userID)
}

// GetSummary returns the aggregated rating data for a video.
// userID may be nil; when nil, MyRating in the result is always nil.
func (r *RatingRepository) GetSummary(ctx context.Context, videoID string, userID *string) (*RatingSummary, error) {
	const selectSQL = `
SELECT COALESCE(AVG(stars::float), 0),
       COUNT(*),
       (SELECT stars FROM ratings WHERE video_id = $1 AND user_id = $2)
FROM   ratings
WHERE  video_id = $1`

	var avgRating float64
	var count int64
	var myRating *int

	// Use a typed nil (*string) so that the pq driver encodes it as SQL NULL
	// instead of receiving an untyped interface{}(nil) which some drivers reject.
	var uid *string
	if userID != nil {
		uid = userID
	}

	row := r.db.QueryRowContext(ctx, selectSQL, videoID, uid)
	if err := row.Scan(&avgRating, &count, &myRating); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return &RatingSummary{}, nil
		}
		return nil, fmt.Errorf("get rating summary: %w", err)
	}

	return &RatingSummary{
		AverageRating: avgRating,
		RatingCount:   count,
		MyRating:      myRating,
	}, nil
}
