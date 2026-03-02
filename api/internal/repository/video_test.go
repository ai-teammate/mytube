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

// ─── videoDetailQuerier ───────────────────────────────────────────────────────
// Implements VideoQuerier and returns pre-configured results.

type videoDetailQuerier struct {
	t          *testing.T
	video      *repository.VideoDetail
	queryErr   error
	execErr    error
	rowsAff    int64
	tags       []string
	tagsErr    error
	queryCount int // tracks how many QueryContext calls have been made
}

func (q *videoDetailQuerier) ExecContext(_ context.Context, _ string, _ ...any) (sql.Result, error) {
	if q.execErr != nil {
		return nil, q.execErr
	}
	return rowsAffectedResult{n: q.rowsAff}, nil
}

func (q *videoDetailQuerier) QueryRowContext(_ context.Context, _ string, _ ...any) *sql.Row {
	if q.queryErr != nil {
		// Return an empty row that will trigger sql.ErrNoRows.
		return emptyDB().QueryRowContext(context.Background(), "SELECT 1")
	}
	if q.video == nil {
		return emptyDB().QueryRowContext(context.Background(), "SELECT 1")
	}

	avatarVal := driver.Value(nil)
	if q.video.UploaderAvatarURL != nil {
		avatarVal = *q.video.UploaderAvatarURL
	}
	thumbVal := driver.Value(nil)
	if q.video.ThumbnailURL != nil {
		thumbVal = *q.video.ThumbnailURL
	}
	descVal := driver.Value(nil)
	if q.video.Description != nil {
		descVal = *q.video.Description
	}
	hlsVal := driver.Value(nil)
	if q.video.HLSManifestPath != nil {
		hlsVal = *q.video.HLSManifestPath
	}

	dsn := registerResults(q.t, []fakeQueryResult{
		{
			columns: []string{
				"id", "title", "description", "hls_manifest_path",
				"thumbnail_url", "view_count", "created_at", "status",
				"username", "avatar_url",
			},
			rows: [][]driver.Value{{
				q.video.ID,
				q.video.Title,
				descVal,
				hlsVal,
				thumbVal,
				q.video.ViewCount,
				q.video.CreatedAt,
				q.video.Status,
				q.video.UploaderUsername,
				avatarVal,
			}},
		},
	})
	db, _ := sql.Open("fakedb", dsn)
	return db.QueryRowContext(context.Background(), "SELECT 1")
}

func (q *videoDetailQuerier) QueryContext(_ context.Context, _ string, _ ...any) (*sql.Rows, error) {
	q.queryCount++
	if q.tagsErr != nil {
		return nil, q.tagsErr
	}
	if len(q.tags) == 0 {
		return emptyDB().QueryContext(context.Background(), "SELECT 1 WHERE 1=0")
	}
	var rows [][]driver.Value
	for _, tag := range q.tags {
		rows = append(rows, []driver.Value{tag})
	}
	dsn := registerResults(q.t, []fakeQueryResult{
		{columns: []string{"tag"}, rows: rows},
	})
	db, _ := sql.Open("fakedb", dsn)
	return db.QueryContext(context.Background(), "SELECT tag FROM video_tags")
}

// ─── GetByID tests ────────────────────────────────────────────────────────────

func TestGetByID_NotFound(t *testing.T) {
	q := &videoDetailQuerier{t: t, video: nil}
	repo := repository.NewVideoRepository(q)

	video, err := repo.GetByID(context.Background(), "nonexistent-id")

	if err != nil {
		t.Fatalf("expected nil error for not-found, got: %v", err)
	}
	if video != nil {
		t.Errorf("expected nil video, got: %+v", video)
	}
}

func TestGetByID_Found_AllFields(t *testing.T) {
	now := time.Now().Truncate(time.Second)
	desc := "A test video description"
	hls := "gs://bucket/videos/v1/index.m3u8"
	thumb := "https://cdn.example.com/thumb.jpg"
	avatarURL := "https://example.com/avatar.png"

	expected := &repository.VideoDetail{
		ID:                "video-id-1",
		Title:             "Test Video",
		Description:       &desc,
		HLSManifestPath:   &hls,
		ThumbnailURL:      &thumb,
		ViewCount:         123,
		CreatedAt:         now,
		Status:            "ready",
		UploaderUsername:  "alice",
		UploaderAvatarURL: &avatarURL,
	}

	q := &videoDetailQuerier{t: t, video: expected}
	repo := repository.NewVideoRepository(q)

	got, err := repo.GetByID(context.Background(), "video-id-1")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Fatal("expected non-nil video")
	}
	if got.ID != expected.ID {
		t.Errorf("ID: got %q, want %q", got.ID, expected.ID)
	}
	if got.Title != expected.Title {
		t.Errorf("Title: got %q, want %q", got.Title, expected.Title)
	}
	if got.Description == nil || *got.Description != desc {
		t.Errorf("Description: got %v, want %q", got.Description, desc)
	}
	if got.HLSManifestPath == nil || *got.HLSManifestPath != hls {
		t.Errorf("HLSManifestPath: got %v, want %q", got.HLSManifestPath, hls)
	}
	if got.ThumbnailURL == nil || *got.ThumbnailURL != thumb {
		t.Errorf("ThumbnailURL: got %v, want %q", got.ThumbnailURL, thumb)
	}
	if got.ViewCount != 123 {
		t.Errorf("ViewCount: got %d, want 123", got.ViewCount)
	}
	if got.Status != "ready" {
		t.Errorf("Status: got %q, want %q", got.Status, "ready")
	}
	if got.UploaderUsername != "alice" {
		t.Errorf("UploaderUsername: got %q, want %q", got.UploaderUsername, "alice")
	}
	if got.UploaderAvatarURL == nil || *got.UploaderAvatarURL != avatarURL {
		t.Errorf("UploaderAvatarURL: got %v, want %q", got.UploaderAvatarURL, avatarURL)
	}
}

func TestGetByID_NilOptionalFields(t *testing.T) {
	now := time.Now().Truncate(time.Second)
	expected := &repository.VideoDetail{
		ID:               "video-id-2",
		Title:            "No Optional Fields",
		Description:      nil,
		HLSManifestPath:  nil,
		ThumbnailURL:     nil,
		ViewCount:        0,
		CreatedAt:        now,
		Status:           "ready",
		UploaderUsername: "bob",
		UploaderAvatarURL: nil,
	}

	q := &videoDetailQuerier{t: t, video: expected}
	repo := repository.NewVideoRepository(q)

	got, err := repo.GetByID(context.Background(), "video-id-2")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Fatal("expected non-nil video")
	}
	if got.Description != nil {
		t.Errorf("expected nil Description, got %v", got.Description)
	}
	if got.HLSManifestPath != nil {
		t.Errorf("expected nil HLSManifestPath, got %v", got.HLSManifestPath)
	}
	if got.ThumbnailURL != nil {
		t.Errorf("expected nil ThumbnailURL, got %v", got.ThumbnailURL)
	}
	if got.UploaderAvatarURL != nil {
		t.Errorf("expected nil UploaderAvatarURL, got %v", got.UploaderAvatarURL)
	}
}

// ─── IncrementViewCount tests ─────────────────────────────────────────────────

func TestIncrementViewCount_Success(t *testing.T) {
	q := &videoDetailQuerier{t: t, rowsAff: 1}
	repo := repository.NewVideoRepository(q)

	updated, err := repo.IncrementViewCount(context.Background(), "video-id-1")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !updated {
		t.Errorf("expected updated=true when 1 row affected")
	}
}

func TestIncrementViewCount_VideoNotFound(t *testing.T) {
	q := &videoDetailQuerier{t: t, rowsAff: 0}
	repo := repository.NewVideoRepository(q)

	updated, err := repo.IncrementViewCount(context.Background(), "nonexistent")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if updated {
		t.Errorf("expected updated=false when 0 rows affected")
	}
}

func TestIncrementViewCount_ExecError(t *testing.T) {
	dbErr := errors.New("db error")
	q := &videoDetailQuerier{t: t, execErr: dbErr}
	repo := repository.NewVideoRepository(q)

	updated, err := repo.IncrementViewCount(context.Background(), "video-id-1")

	if updated {
		t.Errorf("expected updated=false on error")
	}
	if !errors.Is(err, dbErr) {
		t.Errorf("expected wrapped dbErr, got: %v", err)
	}
}

// ─── GetTagsByVideoID tests ───────────────────────────────────────────────────

func TestGetTagsByVideoID_EmptyTags(t *testing.T) {
	q := &videoDetailQuerier{t: t, tags: nil}
	repo := repository.NewVideoRepository(q)

	tags, err := repo.GetTagsByVideoID(context.Background(), "video-id-1")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(tags) != 0 {
		t.Errorf("expected 0 tags, got %d", len(tags))
	}
}

func TestGetTagsByVideoID_ReturnsTags(t *testing.T) {
	q := &videoDetailQuerier{t: t, tags: []string{"go", "programming", "tutorial"}}
	repo := repository.NewVideoRepository(q)

	tags, err := repo.GetTagsByVideoID(context.Background(), "video-id-1")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(tags) != 3 {
		t.Fatalf("expected 3 tags, got %d", len(tags))
	}
	if tags[0] != "go" {
		t.Errorf("tags[0]: got %q, want %q", tags[0], "go")
	}
	if tags[1] != "programming" {
		t.Errorf("tags[1]: got %q, want %q", tags[1], "programming")
	}
	if tags[2] != "tutorial" {
		t.Errorf("tags[2]: got %q, want %q", tags[2], "tutorial")
	}
}

func TestGetTagsByVideoID_QueryError(t *testing.T) {
	dbErr := errors.New("tags query failed")
	q := &videoDetailQuerier{t: t, tagsErr: dbErr}
	repo := repository.NewVideoRepository(q)

	tags, err := repo.GetTagsByVideoID(context.Background(), "video-id-1")

	if tags != nil {
		t.Errorf("expected nil tags on error")
	}
	if !errors.Is(err, dbErr) {
		t.Errorf("expected wrapped dbErr, got: %v", err)
	}
}

func TestGetTagsByVideoID_ReturnsEmptySliceNotNil(t *testing.T) {
	q := &videoDetailQuerier{t: t, tags: nil}
	repo := repository.NewVideoRepository(q)

	tags, err := repo.GetTagsByVideoID(context.Background(), "video-id-1")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// Must return empty slice, not nil, so JSON serializes as [] not null.
	if tags == nil {
		t.Errorf("expected empty slice, got nil")
	}
}
