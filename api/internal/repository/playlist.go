// Package repository provides data-access objects for the mytube domain.
package repository

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"
)

// Playlist represents a playlist row.
type Playlist struct {
	ID        string
	OwnerID   string
	Title     string
	CreatedAt time.Time
}

// PlaylistSummary represents a playlist with its owner username (for list endpoints).
type PlaylistSummary struct {
	ID            string
	Title         string
	OwnerUsername string
	VideoCount    int
	CreatedAt     time.Time
}

// PlaylistVideoItem represents a video entry inside a playlist response.
type PlaylistVideoItem struct {
	ID           string
	Title        string
	ThumbnailURL *string
	Position     int
}

// PlaylistDetail represents a full playlist with its videos and owner username.
type PlaylistDetail struct {
	ID            string
	Title         string
	OwnerUsername string
	Videos        []PlaylistVideoItem
}

// PlaylistQuerier is the database interface used by PlaylistRepository.
// Satisfied by *sql.DB and allows tests to inject a stub.
type PlaylistQuerier interface {
	QueryRowContext(ctx context.Context, query string, args ...any) *sql.Row
	ExecContext(ctx context.Context, query string, args ...any) (sql.Result, error)
	QueryContext(ctx context.Context, query string, args ...any) (*sql.Rows, error)
	BeginTx(ctx context.Context, opts *sql.TxOptions) (*sql.Tx, error)
}

// PlaylistRepository handles persistence for the playlists and playlist_videos tables.
type PlaylistRepository struct {
	db PlaylistQuerier
}

// NewPlaylistRepository constructs a PlaylistRepository backed by db.
func NewPlaylistRepository(db PlaylistQuerier) *PlaylistRepository {
	return &PlaylistRepository{db: db}
}

// Create inserts a new playlist row and returns it with owner username.
func (r *PlaylistRepository) Create(ctx context.Context, ownerID, title string) (*PlaylistSummary, error) {
	const insertSQL = `
WITH inserted AS (
    INSERT INTO playlists (owner_id, title)
    VALUES ($1, $2)
    RETURNING id, title, owner_id, created_at
)
SELECT i.id, i.title, u.username, 0 AS video_count, i.created_at
FROM   inserted i
JOIN   users    u ON u.id = i.owner_id`

	row := r.db.QueryRowContext(ctx, insertSQL, ownerID, title)

	var p PlaylistSummary
	if err := row.Scan(&p.ID, &p.Title, &p.OwnerUsername, &p.VideoCount, &p.CreatedAt); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, fmt.Errorf("create playlist: no row returned")
		}
		return nil, fmt.Errorf("create playlist: %w", err)
	}
	return &p, nil
}

// GetByID returns a playlist with its videos ordered by position, or (nil, nil) if not found.
func (r *PlaylistRepository) GetByID(ctx context.Context, playlistID string) (*PlaylistDetail, error) {
	const selectSQL = `
SELECT p.id, p.title, u.username
FROM   playlists p
JOIN   users     u ON u.id = p.owner_id
WHERE  p.id = $1`

	row := r.db.QueryRowContext(ctx, selectSQL, playlistID)

	var p PlaylistDetail
	if err := row.Scan(&p.ID, &p.Title, &p.OwnerUsername); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, fmt.Errorf("get playlist by id: %w", err)
	}

	// Fetch videos ordered by position.
	const videosSQL = `
SELECT v.id, v.title, v.thumbnail_url, pv.position
FROM   playlist_videos pv
JOIN   videos          v  ON v.id = pv.video_id
WHERE  pv.playlist_id = $1
  AND  v.status = 'ready'
ORDER BY pv.position ASC`

	rows, err := r.db.QueryContext(ctx, videosSQL, playlistID)
	if err != nil {
		return nil, fmt.Errorf("get playlist videos: %w", err)
	}
	defer rows.Close()

	p.Videos = []PlaylistVideoItem{}
	for rows.Next() {
		var v PlaylistVideoItem
		if err := rows.Scan(&v.ID, &v.Title, &v.ThumbnailURL, &v.Position); err != nil {
			return nil, fmt.Errorf("scan playlist video row: %w", err)
		}
		p.Videos = append(p.Videos, v)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate playlist video rows: %w", err)
	}

	return &p, nil
}

// ListByOwnerID returns all playlists for the given internal owner user ID.
func (r *PlaylistRepository) ListByOwnerID(ctx context.Context, ownerID string) ([]PlaylistSummary, error) {
	const selectSQL = `
SELECT p.id, p.title, u.username, COUNT(pv.video_id) AS video_count, p.created_at
FROM   playlists p
JOIN   users          u  ON u.id = p.owner_id
LEFT JOIN playlist_videos pv ON pv.playlist_id = p.id
WHERE  p.owner_id = $1
GROUP BY p.id, p.title, u.username, p.created_at
ORDER BY p.created_at DESC`

	rows, err := r.db.QueryContext(ctx, selectSQL, ownerID)
	if err != nil {
		return nil, fmt.Errorf("list playlists by owner: %w", err)
	}
	defer rows.Close()

	playlists := []PlaylistSummary{}
	for rows.Next() {
		var p PlaylistSummary
		if err := rows.Scan(&p.ID, &p.Title, &p.OwnerUsername, &p.VideoCount, &p.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan playlist row: %w", err)
		}
		playlists = append(playlists, p)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate playlist rows: %w", err)
	}

	return playlists, nil
}

// ListByOwnerUsername returns all playlists for the given owner username (public endpoint).
func (r *PlaylistRepository) ListByOwnerUsername(ctx context.Context, username string) ([]PlaylistSummary, error) {
	const selectSQL = `
SELECT p.id, p.title, u.username, COUNT(pv.video_id) AS video_count, p.created_at
FROM   playlists p
JOIN   users          u  ON u.id = p.owner_id
LEFT JOIN playlist_videos pv ON pv.playlist_id = p.id
WHERE  u.username = $1
GROUP BY p.id, p.title, u.username, p.created_at
ORDER BY p.created_at DESC`

	rows, err := r.db.QueryContext(ctx, selectSQL, username)
	if err != nil {
		return nil, fmt.Errorf("list playlists by username: %w", err)
	}
	defer rows.Close()

	playlists := []PlaylistSummary{}
	for rows.Next() {
		var p PlaylistSummary
		if err := rows.Scan(&p.ID, &p.Title, &p.OwnerUsername, &p.VideoCount, &p.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan playlist row: %w", err)
		}
		playlists = append(playlists, p)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate playlist rows: %w", err)
	}

	return playlists, nil
}

// UpdateTitle updates the title of the playlist with the given ID, enforcing ownership.
// Returns (nil, nil) when no row matches playlistID.
// Returns (nil, ErrForbidden) when the playlist exists but ownerID does not match.
func (r *PlaylistRepository) UpdateTitle(ctx context.Context, playlistID, ownerID, title string) (*PlaylistSummary, error) {
	const ownerSQL = `SELECT owner_id FROM playlists WHERE id = $1`
	row := r.db.QueryRowContext(ctx, ownerSQL, playlistID)
	var actualOwnerID string
	if err := row.Scan(&actualOwnerID); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil // not found
		}
		return nil, fmt.Errorf("check playlist owner for update: %w", err)
	}
	if actualOwnerID != ownerID {
		return nil, ErrForbidden
	}

	const updateSQL = `
UPDATE playlists
SET    title    = $1
WHERE  id       = $2
  AND  owner_id = $3`

	_, err := r.db.ExecContext(ctx, updateSQL, title, playlistID, ownerID)
	if err != nil {
		return nil, fmt.Errorf("update playlist title: %w", err)
	}

	const selectSQL = `
SELECT p.id, p.title, u.username,
       (SELECT COUNT(*) FROM playlist_videos pv WHERE pv.playlist_id = p.id) AS video_count,
       p.created_at
FROM   playlists p
JOIN   users     u ON u.id = p.owner_id
WHERE  p.id = $1`

	refetchRow := r.db.QueryRowContext(ctx, selectSQL, playlistID)
	var p PlaylistSummary
	if err := refetchRow.Scan(&p.ID, &p.Title, &p.OwnerUsername, &p.VideoCount, &p.CreatedAt); err != nil {
		return nil, fmt.Errorf("fetch updated playlist: %w", err)
	}
	return &p, nil
}

// Delete hard-deletes the playlist and its playlist_videos rows (cascade).
// Returns (false, ErrForbidden) when the playlist exists but the caller is not the owner.
// Returns (false, nil) when the playlist does not exist.
// Returns (true, nil) on success.
func (r *PlaylistRepository) Delete(ctx context.Context, playlistID, ownerID string) (bool, error) {
	const ownerSQL = `SELECT owner_id FROM playlists WHERE id = $1`
	row := r.db.QueryRowContext(ctx, ownerSQL, playlistID)
	var actualOwnerID string
	if err := row.Scan(&actualOwnerID); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return false, nil
		}
		return false, fmt.Errorf("check playlist owner: %w", err)
	}
	if actualOwnerID != ownerID {
		return false, ErrForbidden
	}

	const deleteSQL = `DELETE FROM playlists WHERE id = $1 AND owner_id = $2`
	result, err := r.db.ExecContext(ctx, deleteSQL, playlistID, ownerID)
	if err != nil {
		return false, fmt.Errorf("delete playlist: %w", err)
	}

	rowsAff, err := result.RowsAffected()
	if err != nil {
		return false, fmt.Errorf("delete playlist rows affected: %w", err)
	}
	return rowsAff > 0, nil
}

// AddVideo appends a video to a playlist at position max(position)+1.
// Returns ErrForbidden when the caller is not the playlist owner.
// Returns (false, nil) when the playlist does not exist.
// Returns (true, nil) on success.
func (r *PlaylistRepository) AddVideo(ctx context.Context, playlistID, ownerID, videoID string) (bool, error) {
	const ownerSQL = `SELECT owner_id FROM playlists WHERE id = $1`
	row := r.db.QueryRowContext(ctx, ownerSQL, playlistID)
	var actualOwnerID string
	if err := row.Scan(&actualOwnerID); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return false, nil
		}
		return false, fmt.Errorf("check playlist owner for add video: %w", err)
	}
	if actualOwnerID != ownerID {
		return false, ErrForbidden
	}

	tx, err := r.db.BeginTx(ctx, nil)
	if err != nil {
		return false, fmt.Errorf("begin tx add video: %w", err)
	}
	defer tx.Rollback() //nolint:errcheck

	const posSQL = `SELECT COALESCE(MAX(position), 0) + 1 FROM playlist_videos WHERE playlist_id = $1`
	posRow := tx.QueryRowContext(ctx, posSQL, playlistID)
	var nextPos int
	if err := posRow.Scan(&nextPos); err != nil {
		return false, fmt.Errorf("compute next position: %w", err)
	}

	const insertSQL = `
INSERT INTO playlist_videos (playlist_id, video_id, position)
VALUES ($1, $2, $3)
ON CONFLICT (playlist_id, video_id) DO NOTHING`

	_, err = tx.ExecContext(ctx, insertSQL, playlistID, videoID, nextPos)
	if err != nil {
		return false, fmt.Errorf("insert playlist video: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return false, fmt.Errorf("commit add video: %w", err)
	}

	return true, nil
}

// RemoveVideo removes a video from a playlist.
// Returns ErrForbidden when the caller is not the playlist owner.
// Returns (false, nil) when the playlist or video entry does not exist.
// Returns (true, nil) on success.
func (r *PlaylistRepository) RemoveVideo(ctx context.Context, playlistID, ownerID, videoID string) (bool, error) {
	const ownerSQL = `SELECT owner_id FROM playlists WHERE id = $1`
	row := r.db.QueryRowContext(ctx, ownerSQL, playlistID)
	var actualOwnerID string
	if err := row.Scan(&actualOwnerID); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return false, nil
		}
		return false, fmt.Errorf("check playlist owner for remove video: %w", err)
	}
	if actualOwnerID != ownerID {
		return false, ErrForbidden
	}

	const deleteSQL = `
DELETE FROM playlist_videos
WHERE playlist_id = $1
  AND video_id    = $2`

	result, err := r.db.ExecContext(ctx, deleteSQL, playlistID, videoID)
	if err != nil {
		return false, fmt.Errorf("remove playlist video: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return false, fmt.Errorf("remove playlist video rows affected: %w", err)
	}
	return rows > 0, nil
}
