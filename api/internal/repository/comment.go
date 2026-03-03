// Package repository provides data-access objects for the mytube domain.
package repository

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"
)

// Comment represents a comment row with author info.
type Comment struct {
	ID            string
	Body          string
	AuthorID      string
	AuthorUsername string
	AuthorAvatarURL *string
	CreatedAt     time.Time
}

// CreateCommentParams holds the input required to create a comment.
type CreateCommentParams struct {
	VideoID  string
	AuthorID string
	Body     string
}

// CommentQuerier is the database interface used by CommentRepository.
// Satisfied by *sql.DB and allows tests to inject a stub.
type CommentQuerier interface {
	QueryRowContext(ctx context.Context, query string, args ...any) *sql.Row
	ExecContext(ctx context.Context, query string, args ...any) (sql.Result, error)
	QueryContext(ctx context.Context, query string, args ...any) (*sql.Rows, error)
}

// CommentRepository handles persistence for the comments table.
type CommentRepository struct {
	db CommentQuerier
}

// NewCommentRepository constructs a CommentRepository backed by db.
func NewCommentRepository(db CommentQuerier) *CommentRepository {
	return &CommentRepository{db: db}
}

// Create inserts a new comment row and returns it with author info.
// A single CTE query is used to avoid the N+1 round-trip and the theoretical
// race condition between a two-query approach.
func (r *CommentRepository) Create(ctx context.Context, p CreateCommentParams) (*Comment, error) {
	const insertSQL = `
WITH inserted AS (
    INSERT INTO comments (video_id, author_id, body)
    VALUES ($1, $2, $3)
    RETURNING id, body, author_id, created_at
)
SELECT i.id, i.body, i.author_id, u.username, u.avatar_url, i.created_at
FROM   inserted i
JOIN   users    u ON u.id = i.author_id`

	row := r.db.QueryRowContext(ctx, insertSQL, p.VideoID, p.AuthorID, p.Body)

	var c Comment
	if err := row.Scan(&c.ID, &c.Body, &c.AuthorID, &c.AuthorUsername, &c.AuthorAvatarURL, &c.CreatedAt); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, fmt.Errorf("create comment: no row returned")
		}
		return nil, fmt.Errorf("create comment: %w", err)
	}

	return &c, nil
}

// ListByVideoID returns up to 100 comments for a video, ordered by created_at DESC.
func (r *CommentRepository) ListByVideoID(ctx context.Context, videoID string) ([]Comment, error) {
	const selectSQL = `
SELECT c.id, c.body, c.author_id, u.username, u.avatar_url, c.created_at
FROM   comments c
JOIN   users    u ON u.id = c.author_id
WHERE  c.video_id = $1
ORDER BY c.created_at DESC
LIMIT 100`

	rows, err := r.db.QueryContext(ctx, selectSQL, videoID)
	if err != nil {
		return nil, fmt.Errorf("list comments: %w", err)
	}
	defer rows.Close()

	var comments []Comment
	for rows.Next() {
		var c Comment
		if err := rows.Scan(&c.ID, &c.Body, &c.AuthorID, &c.AuthorUsername, &c.AuthorAvatarURL, &c.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan comment row: %w", err)
		}
		comments = append(comments, c)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate comment rows: %w", err)
	}
	if comments == nil {
		comments = []Comment{}
	}
	return comments, nil
}

// Delete hard-deletes a comment by ID. ownerID is the authenticated user; the
// delete is conditional on the comment belonging to ownerID.
// Returns (true, nil) when deleted, (false, nil) when not found or not owned.
func (r *CommentRepository) Delete(ctx context.Context, commentID, ownerID string) (bool, error) {
	const deleteSQL = `
DELETE FROM comments
WHERE  id = $1
  AND  author_id = $2`

	result, err := r.db.ExecContext(ctx, deleteSQL, commentID, ownerID)
	if err != nil {
		return false, fmt.Errorf("delete comment: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return false, fmt.Errorf("delete comment rows affected: %w", err)
	}
	return rows > 0, nil
}
