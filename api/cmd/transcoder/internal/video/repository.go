// Package video provides the repository for updating video records in the database.
package video

import (
	"context"
	"database/sql"
	"fmt"
)

// Status represents the processing state of a video.
type Status string

const (
	StatusReady  Status = "ready"
	StatusFailed Status = "failed"
)

// Update holds the fields to be written to the videos row on completion.
type Update struct {
	HLSManifestPath string
	ThumbnailURL    string
	Status          Status
}

// Querier abstracts *sql.DB so that tests can inject a stub.
type Querier interface {
	ExecContext(ctx context.Context, query string, args ...interface{}) (sql.Result, error)
}

// Repository updates video records via the Querier.
type Repository struct {
	db Querier
}

// NewRepository constructs a Repository backed by the provided Querier.
func NewRepository(db Querier) *Repository {
	return &Repository{db: db}
}

// UpdateVideo applies u to the videos row identified by videoID.
// It returns an error if the row does not exist or the query fails.
func (r *Repository) UpdateVideo(ctx context.Context, videoID string, u Update) error {
	const query = `
		UPDATE videos
		SET hls_manifest_path = $1,
		    thumbnail_url      = $2,
		    status             = $3
		WHERE id = $4`

	res, err := r.db.ExecContext(ctx, query, u.HLSManifestPath, u.ThumbnailURL, string(u.Status), videoID)
	if err != nil {
		return fmt.Errorf("update video %s: %w", videoID, err)
	}
	n, err := res.RowsAffected()
	if err != nil {
		return fmt.Errorf("rows affected for video %s: %w", videoID, err)
	}
	if n == 0 {
		return fmt.Errorf("video %s not found", videoID)
	}
	return nil
}

// MarkFailed sets the video status to "failed".
// It is a best-effort call — errors are returned but callers may choose to log
// and ignore them so as not to mask the original failure.
func (r *Repository) MarkFailed(ctx context.Context, videoID string) error {
	const query = `UPDATE videos SET status = $1 WHERE id = $2`
	_, err := r.db.ExecContext(ctx, query, string(StatusFailed), videoID)
	if err != nil {
		return fmt.Errorf("mark video %s failed: %w", videoID, err)
	}
	return nil
}
