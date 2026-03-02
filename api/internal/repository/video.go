// Package repository provides data-access objects for the mytube domain.
package repository

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"
)

// VideoRecord represents a newly created video row as returned by CreateVideo.
type VideoRecord struct {
	ID         string
	UploaderID string
	Title      string
	Description *string
	CategoryID  *int
	Status      string
	GCSRawPath  *string
	CreatedAt   time.Time
}

// CreateVideoParams holds the input required to create a new video row.
type CreateVideoParams struct {
	UploaderID  string
	Title       string
	Description *string
	CategoryID  *int
	Tags        []string
	GCSRawPath  string
}

// VideoQuerier is the database interface used by VideoRepository.
// Satisfied by *sql.DB and allows tests to inject a stub.
type VideoQuerier interface {
	QueryRowContext(ctx context.Context, query string, args ...any) *sql.Row
	ExecContext(ctx context.Context, query string, args ...any) (sql.Result, error)
}

// VideoRepository handles persistence for the videos and video_tags tables.
type VideoRepository struct {
	db VideoQuerier
}

// NewVideoRepository constructs a VideoRepository backed by db.
func NewVideoRepository(db VideoQuerier) *VideoRepository {
	return &VideoRepository{db: db}
}

// Create inserts a new video row with status=pending and the given GCS raw path,
// then inserts any provided tags into the video_tags table.
// Returns the created VideoRecord.
func (r *VideoRepository) Create(ctx context.Context, p CreateVideoParams) (*VideoRecord, error) {
	const insertSQL = `
INSERT INTO videos (uploader_id, title, description, category_id, status, gcs_raw_path)
VALUES ($1, $2, $3, $4, 'pending', $5)
RETURNING id, uploader_id, title, description, category_id, status, gcs_raw_path, created_at`

	row := r.db.QueryRowContext(ctx, insertSQL,
		p.UploaderID,
		p.Title,
		p.Description,
		p.CategoryID,
		p.GCSRawPath,
	)

	var v VideoRecord
	if err := row.Scan(
		&v.ID,
		&v.UploaderID,
		&v.Title,
		&v.Description,
		&v.CategoryID,
		&v.Status,
		&v.GCSRawPath,
		&v.CreatedAt,
	); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, fmt.Errorf("create video: no row returned")
		}
		return nil, fmt.Errorf("create video: %w", err)
	}

	for _, tag := range p.Tags {
		if tag == "" {
			continue
		}
		const tagSQL = `
INSERT INTO video_tags (video_id, tag)
VALUES ($1, $2)
ON CONFLICT DO NOTHING`
		if _, err := r.db.ExecContext(ctx, tagSQL, v.ID, tag); err != nil {
			return nil, fmt.Errorf("insert tag %q for video %s: %w", tag, v.ID, err)
		}
	}

	return &v, nil
}
