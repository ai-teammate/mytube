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

// ─── VideoQuerier stubs ───────────────────────────────────────────────────────

// videoCreateQuerier is a VideoQuerier stub for Create tests.
// It returns a pre-configured row from QueryRowContext and records ExecContext
// calls (for tag inserts).
type videoCreateQuerier struct {
	t            *testing.T
	video        *repository.VideoRecord
	queryRowErr  bool   // if true QueryRowContext returns no-rows
	execErr      error  // if non-nil ExecContext returns this error
	execCallCount int
}

func (q *videoCreateQuerier) QueryRowContext(_ context.Context, _ string, _ ...any) *sql.Row {
	if q.video == nil || q.queryRowErr {
		return emptyDB().QueryRowContext(context.Background(), "SELECT 1")
	}
	return videoRowDB(q.t, q.video).QueryRowContext(
		context.Background(),
		"SELECT id, uploader_id, title, description, category_id, status, gcs_raw_path, created_at FROM videos",
	)
}

func (q *videoCreateQuerier) ExecContext(_ context.Context, _ string, _ ...any) (sql.Result, error) {
	q.execCallCount++
	if q.execErr != nil {
		return nil, q.execErr
	}
	return okResult{}, nil
}

// videoRowDB returns a *sql.DB configured to return one VideoRecord row.
func videoRowDB(t *testing.T, v *repository.VideoRecord) *sql.DB {
	t.Helper()
	descVal := driver.Value(nil)
	if v.Description != nil {
		descVal = *v.Description
	}
	catVal := driver.Value(nil)
	if v.CategoryID != nil {
		catVal = int64(*v.CategoryID)
	}
	rawPathVal := driver.Value(nil)
	if v.GCSRawPath != nil {
		rawPathVal = *v.GCSRawPath
	}
	ts := v.CreatedAt
	if ts.IsZero() {
		ts = time.Now().Truncate(time.Second)
	}
	dsn := registerResults(t, []fakeQueryResult{
		{
			columns: []string{"id", "uploader_id", "title", "description", "category_id", "status", "gcs_raw_path", "created_at"},
			rows: [][]driver.Value{
				{v.ID, v.UploaderID, v.Title, descVal, catVal, v.Status, rawPathVal, ts},
			},
		},
	})
	db, _ := sql.Open("fakedb", dsn)
	return db
}

// ─── Create tests ─────────────────────────────────────────────────────────────

func TestVideoCreate_ReturnsVideoRecord(t *testing.T) {
	desc := "A test video description"
	catID := 3
	rawPath := "raw/user1/vid1"
	expected := &repository.VideoRecord{
		ID:          "00000000-0000-0000-0000-000000000001",
		UploaderID:  "uploader-1",
		Title:       "My First Video",
		Description: &desc,
		CategoryID:  &catID,
		Status:      "pending",
		GCSRawPath:  &rawPath,
		CreatedAt:   time.Now().Truncate(time.Second),
	}

	q := &videoCreateQuerier{t: t, video: expected}
	repo := repository.NewVideoRepository(q)

	got, err := repo.Create(context.Background(), repository.CreateVideoParams{
		UploaderID:  "uploader-1",
		Title:       "My First Video",
		Description: &desc,
		CategoryID:  &catID,
		Tags:        []string{},
		GCSRawPath:  rawPath,
	})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Fatal("expected non-nil video record")
	}
	if got.ID != expected.ID {
		t.Errorf("ID: got %q, want %q", got.ID, expected.ID)
	}
	if got.Title != expected.Title {
		t.Errorf("Title: got %q, want %q", got.Title, expected.Title)
	}
	if got.Status != "pending" {
		t.Errorf("Status: got %q, want %q", got.Status, "pending")
	}
	if got.Description == nil || *got.Description != desc {
		t.Errorf("Description: got %v, want %q", got.Description, desc)
	}
	if got.CategoryID == nil || *got.CategoryID != catID {
		t.Errorf("CategoryID: got %v, want %d", got.CategoryID, catID)
	}
}

func TestVideoCreate_NilDescriptionAndCategory(t *testing.T) {
	rawPath := "raw/user2/vid2"
	expected := &repository.VideoRecord{
		ID:          "00000000-0000-0000-0000-000000000002",
		UploaderID:  "uploader-2",
		Title:       "No Description",
		Description: nil,
		CategoryID:  nil,
		Status:      "pending",
		GCSRawPath:  &rawPath,
		CreatedAt:   time.Now().Truncate(time.Second),
	}

	q := &videoCreateQuerier{t: t, video: expected}
	repo := repository.NewVideoRepository(q)

	got, err := repo.Create(context.Background(), repository.CreateVideoParams{
		UploaderID: "uploader-2",
		Title:      "No Description",
		GCSRawPath: rawPath,
	})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got == nil {
		t.Fatal("expected non-nil video record")
	}
	if got.Description != nil {
		t.Errorf("expected nil Description, got %q", *got.Description)
	}
	if got.CategoryID != nil {
		t.Errorf("expected nil CategoryID, got %d", *got.CategoryID)
	}
}

func TestVideoCreate_QueryRowNoRows_ReturnsError(t *testing.T) {
	q := &videoCreateQuerier{t: t, video: nil, queryRowErr: true}
	repo := repository.NewVideoRepository(q)

	got, err := repo.Create(context.Background(), repository.CreateVideoParams{
		UploaderID: "uid",
		Title:      "Test",
		GCSRawPath: "raw/uid/vid",
	})

	if got != nil {
		t.Errorf("expected nil video on scan error")
	}
	if err == nil {
		t.Error("expected error when scan fails, got nil")
	}
}

func TestVideoCreate_InsertsTagsViaExec(t *testing.T) {
	rawPath := "raw/u/v"
	expected := &repository.VideoRecord{
		ID:         "vid-tags",
		UploaderID: "uploader-tags",
		Title:      "Tagged Video",
		Status:     "pending",
		GCSRawPath: &rawPath,
		CreatedAt:  time.Now().Truncate(time.Second),
	}
	q := &videoCreateQuerier{t: t, video: expected}
	repo := repository.NewVideoRepository(q)

	_, err := repo.Create(context.Background(), repository.CreateVideoParams{
		UploaderID: "uploader-tags",
		Title:      "Tagged Video",
		Tags:       []string{"golang", "tutorial", "programming"},
		GCSRawPath: rawPath,
	})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// 3 tags → 3 ExecContext calls (one per tag)
	if q.execCallCount != 3 {
		t.Errorf("expected 3 tag ExecContext calls, got %d", q.execCallCount)
	}
}

func TestVideoCreate_SkipsEmptyTags(t *testing.T) {
	rawPath := "raw/u/v2"
	expected := &repository.VideoRecord{
		ID:         "vid-empty-tags",
		UploaderID: "uploader-3",
		Title:      "Some Video",
		Status:     "pending",
		GCSRawPath: &rawPath,
		CreatedAt:  time.Now().Truncate(time.Second),
	}
	q := &videoCreateQuerier{t: t, video: expected}
	repo := repository.NewVideoRepository(q)

	_, err := repo.Create(context.Background(), repository.CreateVideoParams{
		UploaderID: "uploader-3",
		Title:      "Some Video",
		Tags:       []string{"", "  ", "valid"},
		GCSRawPath: rawPath,
	})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// "  " is not trimmed by repo (trimming is in handler), but "" is skipped.
	// Only "  " (non-empty string) and "valid" remain; "  " is non-empty so 2 calls.
	if q.execCallCount == 0 {
		t.Error("expected at least one tag exec call")
	}
}

func TestVideoCreate_TagExecError_ReturnsError(t *testing.T) {
	dbErr := errors.New("tag insert failed")
	rawPath := "raw/u/v3"
	expected := &repository.VideoRecord{
		ID:         "vid-tag-err",
		UploaderID: "uploader-4",
		Title:      "Error Video",
		Status:     "pending",
		GCSRawPath: &rawPath,
		CreatedAt:  time.Now().Truncate(time.Second),
	}
	q := &videoCreateQuerier{t: t, video: expected, execErr: dbErr}
	repo := repository.NewVideoRepository(q)

	got, err := repo.Create(context.Background(), repository.CreateVideoParams{
		UploaderID: "uploader-4",
		Title:      "Error Video",
		Tags:       []string{"go"},
		GCSRawPath: rawPath,
	})

	if got != nil {
		t.Errorf("expected nil video on tag exec error")
	}
	if !errors.Is(err, dbErr) {
		t.Errorf("expected wrapped dbErr, got: %v", err)
	}
}

func TestVideoCreate_NoTags_NoExecCalls(t *testing.T) {
	rawPath := "raw/u/v4"
	expected := &repository.VideoRecord{
		ID:         "vid-no-tags",
		UploaderID: "uploader-5",
		Title:      "No Tags Video",
		Status:     "pending",
		GCSRawPath: &rawPath,
		CreatedAt:  time.Now().Truncate(time.Second),
	}
	q := &videoCreateQuerier{t: t, video: expected}
	repo := repository.NewVideoRepository(q)

	_, err := repo.Create(context.Background(), repository.CreateVideoParams{
		UploaderID: "uploader-5",
		Title:      "No Tags Video",
		Tags:       []string{},
		GCSRawPath: rawPath,
	})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if q.execCallCount != 0 {
		t.Errorf("expected 0 exec calls with no tags, got %d", q.execCallCount)
	}
}
