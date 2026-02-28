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

// UserQuerier is the database interface used by UserRepository.
// Satisfied by *sql.DB and allows tests to inject a stub.
type UserQuerier interface {
	QueryRowContext(ctx context.Context, query string, args ...any) *sql.Row
	ExecContext(ctx context.Context, query string, args ...any) (sql.Result, error)
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
// username to the email prefix (the part before "@").  On conflict it does
// nothing, leaving the existing row unchanged.  The current user row is then
// fetched and returned.
//
// This implements the auto-provisioning behaviour specified in MYTUBE-13: the
// first successful token verification creates the users row; all subsequent
// calls are no-ops.
func (r *UserRepository) Upsert(ctx context.Context, firebaseUID, email string) (*User, error) {
	username := emailPrefix(email)

	const upsertSQL = `
INSERT INTO users (firebase_uid, username)
VALUES ($1, $2)
ON CONFLICT (firebase_uid) DO NOTHING`

	if _, err := r.db.ExecContext(ctx, upsertSQL, firebaseUID, username); err != nil {
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

// emailPrefix returns the portion of addr before the first "@".
// If addr contains no "@", the whole string is returned.
func emailPrefix(addr string) string {
	if idx := strings.Index(addr, "@"); idx >= 0 {
		return addr[:idx]
	}
	return addr
}
