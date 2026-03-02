// Package repository provides data-access objects for the mytube domain.
package repository

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"
)

// User represents a row in the users table.
type User struct {
	ID          string
	FirebaseUID string
	Username    string
	AvatarURL   *string
	CreatedAt   time.Time
}

// Video represents a video row as returned by the public profile endpoint.
type Video struct {
	ID           string
	Title        string
	ThumbnailURL *string
	ViewCount    int64
	CreatedAt    time.Time
}

// UserQuerier is the database interface used by UserRepository.
// Satisfied by *sql.DB and allows tests to inject a stub.
type UserQuerier interface {
	QueryRowContext(ctx context.Context, query string, args ...any) *sql.Row
	ExecContext(ctx context.Context, query string, args ...any) (sql.Result, error)
	QueryContext(ctx context.Context, query string, args ...any) (*sql.Rows, error)
}

// UserRepository handles persistence for the users table.
type UserRepository struct {
	db UserQuerier
}

// NewUserRepository constructs a UserRepository backed by db.
func NewUserRepository(db UserQuerier) *UserRepository {
	return &UserRepository{db: db}
}

// Upsert inserts a new user row for the given firebase_uid, defaulting the
// username to the email prefix (the part before "@") and storing the picture
// URL from the Firebase/Google ID token when provided.  On conflict it updates
// avatar_url only when the current value is NULL (i.e. the first Google login
// after the row was created with no avatar).  The current user row is then
// fetched and returned.
//
// This implements the auto-provisioning behaviour specified in MYTUBE-13: the
// first successful token verification creates the users row; all subsequent
// calls are no-ops except for syncing the avatar from Firebase.
func (r *UserRepository) Upsert(ctx context.Context, firebaseUID, email, pictureURL string) (*User, error) {
	username := emailPrefix(email)

	var avatarArg *string
	if pictureURL != "" {
		avatarArg = &pictureURL
	}

	const upsertSQL = `
INSERT INTO users (firebase_uid, username, avatar_url)
VALUES ($1, $2, $3)
ON CONFLICT (firebase_uid) DO UPDATE
    SET avatar_url = COALESCE(users.avatar_url, EXCLUDED.avatar_url)`

	if _, err := r.db.ExecContext(ctx, upsertSQL, firebaseUID, username, avatarArg); err != nil {
		return nil, fmt.Errorf("upsert user: %w", err)
	}

	return r.GetByFirebaseUID(ctx, firebaseUID)
}

// GetByFirebaseUID fetches the user row identified by firebase_uid.
// Returns (nil, nil) when no matching row exists.
func (r *UserRepository) GetByFirebaseUID(ctx context.Context, firebaseUID string) (*User, error) {
	const selectSQL = `
SELECT id, firebase_uid, username, avatar_url, created_at
FROM   users
WHERE  firebase_uid = $1`

	row := r.db.QueryRowContext(ctx, selectSQL, firebaseUID)

	var u User
	if err := row.Scan(&u.ID, &u.FirebaseUID, &u.Username, &u.AvatarURL, &u.CreatedAt); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, fmt.Errorf("get user by firebase uid: %w", err)
	}
	return &u, nil
}

// GetByUsername fetches the user row identified by username.
// Returns (nil, nil) when no matching row exists.
func (r *UserRepository) GetByUsername(ctx context.Context, username string) (*User, error) {
	const selectSQL = `
SELECT id, firebase_uid, username, avatar_url, created_at
FROM   users
WHERE  username = $1`

	row := r.db.QueryRowContext(ctx, selectSQL, username)

	var u User
	if err := row.Scan(&u.ID, &u.FirebaseUID, &u.Username, &u.AvatarURL, &u.CreatedAt); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, fmt.Errorf("get user by username: %w", err)
	}
	return &u, nil
}

// GetVideosByUserID returns up to 50 ready videos uploaded by the user with
// the given internal user ID, ordered by created_at DESC (newest first).
func (r *UserRepository) GetVideosByUserID(ctx context.Context, userID string) ([]Video, error) {
	const selectSQL = `
SELECT id, title, thumbnail_url, view_count, created_at
FROM   videos
WHERE  uploader_id = $1
  AND  status = 'ready'
ORDER BY created_at DESC
LIMIT 50`

	rows, err := r.db.QueryContext(ctx, selectSQL, userID)
	if err != nil {
		return nil, fmt.Errorf("get videos by user id: %w", err)
	}
	defer rows.Close()

	var videos []Video
	for rows.Next() {
		var v Video
		if err := rows.Scan(&v.ID, &v.Title, &v.ThumbnailURL, &v.ViewCount, &v.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan video row: %w", err)
		}
		videos = append(videos, v)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate video rows: %w", err)
	}
	return videos, nil
}

// UpdateProfile updates the username and avatar_url for the user identified by
// firebaseUID.  avatarURL may be nil to clear the avatar.  Returns the updated
// user row.  Returns (nil, nil) when no row matches the given firebaseUID.
func (r *UserRepository) UpdateProfile(ctx context.Context, firebaseUID, username string, avatarURL *string) (*User, error) {
	const updateSQL = `
UPDATE users
SET    username   = $1,
       avatar_url = $2
WHERE  firebase_uid = $3`

	result, err := r.db.ExecContext(ctx, updateSQL, username, avatarURL, firebaseUID)
	if err != nil {
		return nil, fmt.Errorf("update user profile: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return nil, fmt.Errorf("update user profile rows affected: %w", err)
	}
	if rows == 0 {
		return nil, nil
	}

	return r.GetByFirebaseUID(ctx, firebaseUID)
}

// emailPrefix returns the portion of addr before the first "@".
// If addr contains no "@", the whole string is returned.
func emailPrefix(addr string) string {
	if idx := strings.Index(addr, "@"); idx >= 0 {
		return addr[:idx]
	}
	return addr
}
