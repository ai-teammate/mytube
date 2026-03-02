// Package repository provides data-access objects for the mytube domain.
package repository

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"
)

// VideoDetail represents a full video row with uploader info as returned by
// the public video watch endpoint.
type VideoDetail struct {
	ID              string
	Title           string
	Description     *string
	HLSManifestPath *string // raw GCS path, e.g. gs://bucket/videos/{id}/index.m3u8
	ThumbnailURL    *string
	ViewCount       int64
	CreatedAt       time.Time
	Status          string
	// Uploader fields
	UploaderUsername string
	UploaderAvatarURL *string
	// Tags populated separately
	Tags []string
}

// VideoQuerier is the database interface used by VideoRepository.
// Satisfied by *sql.DB and allows tests to inject a stub.
type VideoQuerier interface {
	QueryRowContext(ctx context.Context, query string, args ...any) *sql.Row
	ExecContext(ctx context.Context, query string, args ...any) (sql.Result, error)
	QueryContext(ctx context.Context, query string, args ...any) (*sql.Rows, error)
}

// VideoRepository handles persistence for the videos table.
type VideoRepository struct {
	db VideoQuerier
}

// NewVideoRepository constructs a VideoRepository backed by db.
func NewVideoRepository(db VideoQuerier) *VideoRepository {
	return &VideoRepository{db: db}
}

// GetByID fetches the video with the given ID along with its uploader info.
// Returns (nil, nil) when no matching row exists or the video status is not "ready".
func (r *VideoRepository) GetByID(ctx context.Context, videoID string) (*VideoDetail, error) {
	const selectSQL = `
SELECT v.id,
       v.title,
       v.description,
       v.hls_manifest_path,
       v.thumbnail_url,
       v.view_count,
       v.created_at,
       v.status,
       u.username,
       u.avatar_url
FROM   videos v
JOIN   users  u ON u.id = v.uploader_id
WHERE  v.id = $1
  AND  v.status = 'ready'`

	row := r.db.QueryRowContext(ctx, selectSQL, videoID)

	var v VideoDetail
	if err := row.Scan(
		&v.ID,
		&v.Title,
		&v.Description,
		&v.HLSManifestPath,
		&v.ThumbnailURL,
		&v.ViewCount,
		&v.CreatedAt,
		&v.Status,
		&v.UploaderUsername,
		&v.UploaderAvatarURL,
	); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, fmt.Errorf("get video by id: %w", err)
	}
	return &v, nil
}

// IncrementViewCount atomically increments the view_count for the video with
// the given ID. Returns (false, nil) when no matching row exists.
func (r *VideoRepository) IncrementViewCount(ctx context.Context, videoID string) (bool, error) {
	const updateSQL = `
UPDATE videos
SET    view_count = view_count + 1
WHERE  id = $1`

	result, err := r.db.ExecContext(ctx, updateSQL, videoID)
	if err != nil {
		return false, fmt.Errorf("increment view count: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return false, fmt.Errorf("increment view count rows affected: %w", err)
	}
	return rows > 0, nil
}

// GetTagsByVideoID returns the tags associated with the given video ID.
// Returns an empty slice when no tags exist.
func (r *VideoRepository) GetTagsByVideoID(ctx context.Context, videoID string) ([]string, error) {
	const selectSQL = `
SELECT tag
FROM   video_tags
WHERE  video_id = $1
ORDER BY tag`

	rows, err := r.db.QueryContext(ctx, selectSQL, videoID)
	if err != nil {
		return nil, fmt.Errorf("get tags by video id: %w", err)
	}
	defer rows.Close()

	var tags []string
	for rows.Next() {
		var tag string
		if err := rows.Scan(&tag); err != nil {
			return nil, fmt.Errorf("scan tag row: %w", err)
		}
		tags = append(tags, tag)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate tag rows: %w", err)
	}
	if tags == nil {
		tags = []string{}
	}
	return tags, nil
}
