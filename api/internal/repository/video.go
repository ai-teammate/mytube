// Package repository provides data-access objects for the mytube domain.
package repository

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"
)

// ErrForbidden is returned by ownership-enforced operations when the
// authenticated caller is not the resource owner.
var ErrForbidden = errors.New("forbidden")

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
	UploaderUsername  string
	UploaderAvatarURL *string
	// Tags populated separately
	Tags []string
}

// VideoRecord represents a newly created video row as returned by CreateVideo.
type VideoRecord struct {
	ID          string
	UploaderID  string
	Title       string
	Description *string
	CategoryID  *int
	Status      string
	GCSRawPath  *string
	CreatedAt   time.Time
}

// CreateVideoParams holds the input required to create a new video row.
type CreateVideoParams struct {
	// ID is the pre-generated UUID for the video row.  The handler generates
	// this before signing the GCS URL so that both use the same video ID.
	ID          string
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
	QueryContext(ctx context.Context, query string, args ...any) (*sql.Rows, error)
	BeginTx(ctx context.Context, opts *sql.TxOptions) (*sql.Tx, error)
}

// VideoRepository handles persistence for the videos and video_tags tables.
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

// Exists reports whether a ready video row with the given ID exists in the
// database. Only videos with status = 'ready' are considered to exist, matching
// the same visibility rule used by GetByID. Use this for a lightweight existence
// check before operating on video sub-resources (ratings, comments).
func (r *VideoRepository) Exists(ctx context.Context, videoID string) (bool, error) {
	const selectSQL = `SELECT 1 FROM videos WHERE id = $1 AND status = 'ready' LIMIT 1`
	row := r.db.QueryRowContext(ctx, selectSQL, videoID)
	var dummy int
	if err := row.Scan(&dummy); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return false, nil
		}
		return false, fmt.Errorf("check video exists: %w", err)
	}
	return true, nil
}

// DashboardVideo represents a video row as returned by the dashboard endpoint.
// All statuses are included (pending/processing/ready/failed).
type DashboardVideo struct {
	ID           string
	Title        string
	Status       string
	ThumbnailURL *string
	ViewCount    int64
	CreatedAt    time.Time
	Description  *string
	CategoryID   *int
	Tags         []string
}

// UpdateVideoParams holds the input required to update an existing video row.
type UpdateVideoParams struct {
	Title       string
	Description *string
	CategoryID  *int
	Tags        []string
}

// GetByIDForOwner fetches a video row by ID without filtering by status.
// Returns (nil, nil) when no matching row exists.
func (r *VideoRepository) GetByIDForOwner(ctx context.Context, videoID string) (*VideoDetail, error) {
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
WHERE  v.id = $1`

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
		return nil, fmt.Errorf("get video by id for owner: %w", err)
	}
	return &v, nil
}

// GetVideosByUploaderID returns all non-deleted videos uploaded by the user
// with the given internal user ID (all statuses except 'deleted'), ordered by
// created_at DESC (newest first). Tags for each video are fetched separately.
func (r *VideoRepository) GetVideosByUploaderID(ctx context.Context, uploaderID string) ([]DashboardVideo, error) {
	const selectSQL = `
SELECT id, title, status, thumbnail_url, view_count, created_at, description, category_id
FROM   videos
WHERE  uploader_id = $1
  AND  status != 'deleted'
ORDER BY created_at DESC`

	rows, err := r.db.QueryContext(ctx, selectSQL, uploaderID)
	if err != nil {
		return nil, fmt.Errorf("get videos by uploader id: %w", err)
	}
	defer rows.Close()

	var videos []DashboardVideo
	for rows.Next() {
		var v DashboardVideo
		if err := rows.Scan(&v.ID, &v.Title, &v.Status, &v.ThumbnailURL, &v.ViewCount, &v.CreatedAt, &v.Description, &v.CategoryID); err != nil {
			return nil, fmt.Errorf("scan dashboard video row: %w", err)
		}
		videos = append(videos, v)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate dashboard video rows: %w", err)
	}
	if videos == nil {
		videos = []DashboardVideo{}
	}

	// Populate tags for each video.
	for i := range videos {
		tags, err := r.GetTagsByVideoID(ctx, videos[i].ID)
		if err != nil {
			return nil, fmt.Errorf("get tags for video %s: %w", videos[i].ID, err)
		}
		videos[i].Tags = tags
	}

	return videos, nil
}

// Update updates the title, description, category_id, and tags for the video
// with the given ID, enforcing ownership atomically in the WHERE clause.
// Tags are replaced: existing tags are deleted and the new set is inserted, all
// within a single transaction to prevent partial updates.
// Returns (nil, nil) when no row matches the given videoID or uploaderID.
func (r *VideoRepository) Update(ctx context.Context, videoID string, uploaderID string, p UpdateVideoParams) (*VideoDetail, error) {
	tx, err := r.db.BeginTx(ctx, nil)
	if err != nil {
		return nil, fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback() //nolint:errcheck

	const updateSQL = `
UPDATE videos
SET    title       = $1,
       description = $2,
       category_id = $3
WHERE  id          = $4
  AND  uploader_id = $5`

	result, err := tx.ExecContext(ctx, updateSQL, p.Title, p.Description, p.CategoryID, videoID, uploaderID)
	if err != nil {
		return nil, fmt.Errorf("update video: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return nil, fmt.Errorf("update video rows affected: %w", err)
	}
	if rows == 0 {
		return nil, nil
	}

	// Replace tags: delete existing then insert new set.
	const deleteTagsSQL = `DELETE FROM video_tags WHERE video_id = $1`
	if _, err := tx.ExecContext(ctx, deleteTagsSQL, videoID); err != nil {
		return nil, fmt.Errorf("delete tags for video %s: %w", videoID, err)
	}

	for _, tag := range p.Tags {
		if tag == "" {
			continue
		}
		const insertTagSQL = `
INSERT INTO video_tags (video_id, tag)
VALUES ($1, $2)
ON CONFLICT DO NOTHING`
		if _, err := tx.ExecContext(ctx, insertTagSQL, videoID, tag); err != nil {
			return nil, fmt.Errorf("insert tag %q for video %s: %w", tag, videoID, err)
		}
	}

	if err := tx.Commit(); err != nil {
		return nil, fmt.Errorf("commit: %w", err)
	}

	return r.GetByIDForOwner(ctx, videoID)
}

// SoftDelete sets the status of the video with the given ID to 'deleted'.
// Ownership is checked explicitly before the update so callers can distinguish
// between "video not found" and "caller is not the owner":
//   - Returns (false, nil)          when the video does not exist or is already deleted.
//   - Returns (false, ErrForbidden) when the video exists but uploaderID is not the owner.
//   - Returns (true,  nil)          on successful soft-deletion.
func (r *VideoRepository) SoftDelete(ctx context.Context, videoID string, uploaderID string) (bool, error) {
	// Check existence and ownership before attempting the update.
	const ownerSQL = `SELECT uploader_id FROM videos WHERE id = $1 AND status != 'deleted'`
	row := r.db.QueryRowContext(ctx, ownerSQL, videoID)
	var ownerID string
	if err := row.Scan(&ownerID); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return false, nil // video not found or already deleted
		}
		return false, fmt.Errorf("check video owner: %w", err)
	}
	if ownerID != uploaderID {
		return false, ErrForbidden
	}

	const updateSQL = `
UPDATE videos
SET    status = 'deleted'
WHERE  id          = $1
  AND  uploader_id = $2
  AND  status     != 'deleted'`

	result, err := r.db.ExecContext(ctx, updateSQL, videoID, uploaderID)
	if err != nil {
		return false, fmt.Errorf("soft delete video: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return false, fmt.Errorf("soft delete video rows affected: %w", err)
	}
	return rows > 0, nil
}

// Create inserts a new video row with status=pending and the given GCS raw path,
// then inserts any provided tags into the video_tags table.
// Returns the created VideoRecord.
func (r *VideoRepository) Create(ctx context.Context, p CreateVideoParams) (*VideoRecord, error) {
	const insertSQL = `
INSERT INTO videos (id, uploader_id, title, description, category_id, status, gcs_raw_path)
VALUES ($1, $2, $3, $4, $5, 'pending', $6)
RETURNING id, uploader_id, title, description, category_id, status, gcs_raw_path, created_at`

	row := r.db.QueryRowContext(ctx, insertSQL,
		p.ID,
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
