package repository_test

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"errors"
	"testing"
	"time"

	"github.com/ai-teammate/mytube/api/internal/repository"
)

// ─── commentQuerier stub ──────────────────────────────────────────────────────

type commentQuerier struct {
	t           *testing.T
	comment     *repository.Comment
	comments    []repository.Comment
	queryRowErr bool
	execErr     error
	rowsAff     int64
	queryErr    error
}

func (q *commentQuerier) ExecContext(_ context.Context, _ string, _ ...any) (sql.Result, error) {
	if q.execErr != nil {
		return nil, q.execErr
	}
	return rowsAffectedResult{n: q.rowsAff}, nil
}

func (q *commentQuerier) QueryRowContext(_ context.Context, _ string, _ ...any) *sql.Row {
	if q.queryRowErr || q.comment == nil {
		return emptyDB().QueryRowContext(context.Background(), "SELECT 1")
	}
	// CTE query returns: id, body, author_id, username, avatar_url, created_at
	avatarVal := driver.Value(nil)
	if q.comment.AuthorAvatarURL != nil {
		avatarVal = *q.comment.AuthorAvatarURL
	}
	dsn := registerResults(q.t, []fakeQueryResult{
		{
			columns: []string{"id", "body", "author_id", "username", "avatar_url", "created_at"},
			rows: [][]driver.Value{{
				q.comment.ID, q.comment.Body, q.comment.AuthorID,
				q.comment.AuthorUsername, avatarVal, q.comment.CreatedAt,
			}},
		},
	})
	db, _ := sql.Open("fakedb", dsn)
	return db.QueryRowContext(context.Background(), "SELECT 1")
}

func (q *commentQuerier) QueryContext(_ context.Context, _ string, _ ...any) (*sql.Rows, error) {
	if q.queryErr != nil {
		return nil, q.queryErr
	}
	if len(q.comments) == 0 {
		return emptyDB().QueryContext(context.Background(), "SELECT 1 WHERE 1=0")
	}

	var rows [][]driver.Value
	for _, c := range q.comments {
		avatarVal := driver.Value(nil)
		if c.AuthorAvatarURL != nil {
			avatarVal = *c.AuthorAvatarURL
		}
		rows = append(rows, []driver.Value{
			c.ID, c.Body, c.AuthorID, c.AuthorUsername, avatarVal, c.CreatedAt,
		})
	}
	dsn := registerResults(q.t, []fakeQueryResult{
		{
			columns: []string{"id", "body", "author_id", "username", "avatar_url", "created_at"},
			rows:    rows,
		},
	})
	db, _ := sql.Open("fakedb", dsn)
	return db.QueryContext(context.Background(), "SELECT 1")
}

// ─── ListByVideoID tests ──────────────────────────────────────────────────────

func TestListByVideoID_EmptyReturnsEmptySlice(t *testing.T) {
	q := &commentQuerier{t: t, comments: nil}
	repo := repository.NewCommentRepository(q)

	comments, err := repo.ListByVideoID(context.Background(), "video-1")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(comments) != 0 {
		t.Errorf("expected 0 comments, got %d", len(comments))
	}
	// Must be a non-nil slice for JSON serialization.
	if comments == nil {
		t.Errorf("expected empty slice, got nil")
	}
}

func TestListByVideoID_ReturnsComments(t *testing.T) {
	now := time.Now().Truncate(time.Second)
	avatarURL := "https://example.com/avatar.png"
	q := &commentQuerier{
		t: t,
		comments: []repository.Comment{
			{
				ID:              "c1",
				Body:            "Great video!",
				AuthorID:        "user-1",
				AuthorUsername:  "alice",
				AuthorAvatarURL: &avatarURL,
				CreatedAt:       now,
			},
			{
				ID:              "c2",
				Body:            "Thanks!",
				AuthorID:        "user-2",
				AuthorUsername:  "bob",
				AuthorAvatarURL: nil,
				CreatedAt:       now,
			},
		},
	}
	repo := repository.NewCommentRepository(q)

	comments, err := repo.ListByVideoID(context.Background(), "video-1")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(comments) != 2 {
		t.Fatalf("expected 2 comments, got %d", len(comments))
	}
	if comments[0].ID != "c1" {
		t.Errorf("comments[0].ID: got %q, want c1", comments[0].ID)
	}
	if comments[0].Body != "Great video!" {
		t.Errorf("comments[0].Body: got %q", comments[0].Body)
	}
	if comments[0].AuthorUsername != "alice" {
		t.Errorf("comments[0].AuthorUsername: got %q", comments[0].AuthorUsername)
	}
	if comments[0].AuthorAvatarURL == nil || *comments[0].AuthorAvatarURL != avatarURL {
		t.Errorf("comments[0].AuthorAvatarURL: expected %q", avatarURL)
	}
	if comments[1].AuthorAvatarURL != nil {
		t.Errorf("comments[1].AuthorAvatarURL: expected nil")
	}
}

func TestListByVideoID_QueryError_ReturnsError(t *testing.T) {
	dbErr := errors.New("query failed")
	q := &commentQuerier{t: t, queryErr: dbErr}
	repo := repository.NewCommentRepository(q)

	comments, err := repo.ListByVideoID(context.Background(), "video-1")

	if comments != nil {
		t.Errorf("expected nil on error")
	}
	if !errors.Is(err, dbErr) {
		t.Errorf("expected wrapped dbErr, got: %v", err)
	}
}

// ─── Delete tests ─────────────────────────────────────────────────────────────

func TestDelete_CommentExists_ReturnsTrue(t *testing.T) {
	q := &commentQuerier{t: t, rowsAff: 1}
	repo := repository.NewCommentRepository(q)

	deleted, err := repo.Delete(context.Background(), "c1", "user-1")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !deleted {
		t.Errorf("expected deleted=true when 1 row affected")
	}
}

func TestDelete_CommentNotFoundOrNotOwned_ReturnsFalse(t *testing.T) {
	q := &commentQuerier{t: t, rowsAff: 0}
	repo := repository.NewCommentRepository(q)

	deleted, err := repo.Delete(context.Background(), "c1", "other-user")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if deleted {
		t.Errorf("expected deleted=false when 0 rows affected")
	}
}

func TestDelete_ExecError_ReturnsError(t *testing.T) {
	dbErr := errors.New("delete failed")
	q := &commentQuerier{t: t, execErr: dbErr}
	repo := repository.NewCommentRepository(q)

	deleted, err := repo.Delete(context.Background(), "c1", "user-1")

	if deleted {
		t.Errorf("expected deleted=false on error")
	}
	if !errors.Is(err, dbErr) {
		t.Errorf("expected wrapped dbErr, got: %v", err)
	}
}

// ─── Create tests ─────────────────────────────────────────────────────────────

func TestCreate_Success_ReturnsComment(t *testing.T) {
	now := time.Now().Truncate(time.Second)
	avatarURL := "https://example.com/avatar.png"
	expected := &repository.Comment{
		ID:              "c-new",
		Body:            "Hello!",
		AuthorID:        "user-1",
		AuthorUsername:  "alice",
		AuthorAvatarURL: &avatarURL,
		CreatedAt:       now,
	}
	q := &commentQuerier{t: t, comment: expected}
	repo := repository.NewCommentRepository(q)

	got, err := repo.Create(context.Background(), repository.CreateCommentParams{
		VideoID:  "video-1",
		AuthorID: "user-1",
		Body:     "Hello!",
	})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Fatal("expected non-nil comment")
	}
	if got.ID != "c-new" {
		t.Errorf("ID: got %q, want c-new", got.ID)
	}
	if got.Body != "Hello!" {
		t.Errorf("Body: got %q, want Hello!", got.Body)
	}
	if got.AuthorUsername != "alice" {
		t.Errorf("AuthorUsername: got %q, want alice", got.AuthorUsername)
	}
	if got.AuthorAvatarURL == nil || *got.AuthorAvatarURL != avatarURL {
		t.Errorf("AuthorAvatarURL: expected %q", avatarURL)
	}
}

func TestCreate_InsertError_ReturnsError(t *testing.T) {
	q := &commentQuerier{t: t, queryRowErr: true}
	repo := repository.NewCommentRepository(q)

	got, err := repo.Create(context.Background(), repository.CreateCommentParams{
		VideoID:  "video-1",
		AuthorID: "user-1",
		Body:     "Hello!",
	})

	if got != nil {
		t.Errorf("expected nil comment on error")
	}
	if err == nil {
		t.Error("expected error when insert returns no row, got nil")
	}
}
