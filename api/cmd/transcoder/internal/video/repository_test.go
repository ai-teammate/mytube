package video_test

import (
	"context"
	"database/sql"
	"errors"
	"testing"

	"github.com/ai-teammate/mytube/api/cmd/transcoder/internal/video"
)

// ── stubQuerier ───────────────────────────────────────────────────────────────

type stubQuerier struct {
	rowsAffected int64
	rowsErr      error
	execErr      error
	lastQuery    string
	lastArgs     []interface{}
}

func (s *stubQuerier) ExecContext(_ context.Context, query string, args ...interface{}) (sql.Result, error) {
	s.lastQuery = query
	s.lastArgs = args
	if s.execErr != nil {
		return nil, s.execErr
	}
	return &stubResult{rowsAffected: s.rowsAffected, err: s.rowsErr}, nil
}

type stubResult struct {
	rowsAffected int64
	err          error
}

func (r *stubResult) LastInsertId() (int64, error) { return 0, nil }
func (r *stubResult) RowsAffected() (int64, error) { return r.rowsAffected, r.err }

// ── NewRepository ─────────────────────────────────────────────────────────────

func TestNewRepository_NotNil(t *testing.T) {
	repo := video.NewRepository(&stubQuerier{})
	if repo == nil {
		t.Fatal("NewRepository() returned nil")
	}
}

// ── UpdateVideo ───────────────────────────────────────────────────────────────

func TestUpdateVideo_Success(t *testing.T) {
	q := &stubQuerier{rowsAffected: 1}
	repo := video.NewRepository(q)

	err := repo.UpdateVideo(context.Background(), "video-id", video.Update{
		HLSManifestPath: "gs://bucket/index.m3u8",
		ThumbnailURL:    "https://cdn.example.com/videos/id/thumbnail.jpg",
		Status:          video.StatusReady,
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestUpdateVideo_PassesHLSManifestPath(t *testing.T) {
	q := &stubQuerier{rowsAffected: 1}
	repo := video.NewRepository(q)

	_ = repo.UpdateVideo(context.Background(), "vid", video.Update{
		HLSManifestPath: "gs://hls-bucket/videos/vid/index.m3u8",
		ThumbnailURL:    "https://cdn/thumb.jpg",
		Status:          video.StatusReady,
	})

	if len(q.lastArgs) < 1 || q.lastArgs[0] != "gs://hls-bucket/videos/vid/index.m3u8" {
		t.Errorf("HLSManifestPath not passed correctly, args = %v", q.lastArgs)
	}
}

func TestUpdateVideo_PassesThumbnailURL(t *testing.T) {
	q := &stubQuerier{rowsAffected: 1}
	repo := video.NewRepository(q)

	_ = repo.UpdateVideo(context.Background(), "vid", video.Update{
		HLSManifestPath: "gs://b/index.m3u8",
		ThumbnailURL:    "https://cdn.example.com/videos/vid/thumbnail.jpg",
		Status:          video.StatusReady,
	})

	if len(q.lastArgs) < 2 || q.lastArgs[1] != "https://cdn.example.com/videos/vid/thumbnail.jpg" {
		t.Errorf("ThumbnailURL not passed correctly, args = %v", q.lastArgs)
	}
}

func TestUpdateVideo_PassesStatusReady(t *testing.T) {
	q := &stubQuerier{rowsAffected: 1}
	repo := video.NewRepository(q)

	_ = repo.UpdateVideo(context.Background(), "vid", video.Update{
		HLSManifestPath: "gs://b/i.m3u8",
		ThumbnailURL:    "https://cdn/t.jpg",
		Status:          video.StatusReady,
	})

	if len(q.lastArgs) < 3 || q.lastArgs[2] != "ready" {
		t.Errorf("Status not passed as 'ready', args = %v", q.lastArgs)
	}
}

func TestUpdateVideo_PassesVideoID(t *testing.T) {
	q := &stubQuerier{rowsAffected: 1}
	repo := video.NewRepository(q)

	_ = repo.UpdateVideo(context.Background(), "expected-id", video.Update{
		Status: video.StatusReady,
	})

	if len(q.lastArgs) < 4 || q.lastArgs[3] != "expected-id" {
		t.Errorf("video ID not passed as last arg, args = %v", q.lastArgs)
	}
}

func TestUpdateVideo_ExecError_ReturnedAsError(t *testing.T) {
	q := &stubQuerier{execErr: errors.New("db error")}
	repo := video.NewRepository(q)

	err := repo.UpdateVideo(context.Background(), "id", video.Update{})
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func TestUpdateVideo_ZeroRowsAffected_ReturnsNotFoundError(t *testing.T) {
	q := &stubQuerier{rowsAffected: 0}
	repo := video.NewRepository(q)

	err := repo.UpdateVideo(context.Background(), "missing-id", video.Update{})
	if err == nil {
		t.Fatal("expected error for 0 rows affected")
	}
}

func TestUpdateVideo_RowsAffectedError_ReturnsError(t *testing.T) {
	q := &stubQuerier{rowsAffected: 0, rowsErr: errors.New("rows affected error")}
	repo := video.NewRepository(q)

	err := repo.UpdateVideo(context.Background(), "vid", video.Update{})
	if err == nil {
		t.Fatal("expected error when RowsAffected fails")
	}
}

// ── MarkFailed ────────────────────────────────────────────────────────────────

func TestMarkFailed_Success(t *testing.T) {
	q := &stubQuerier{rowsAffected: 1}
	repo := video.NewRepository(q)

	if err := repo.MarkFailed(context.Background(), "vid"); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestMarkFailed_PassesStatusFailed(t *testing.T) {
	q := &stubQuerier{rowsAffected: 1}
	repo := video.NewRepository(q)

	_ = repo.MarkFailed(context.Background(), "vid")

	if len(q.lastArgs) < 1 || q.lastArgs[0] != "failed" {
		t.Errorf("status arg = %v, want 'failed'", q.lastArgs)
	}
}

func TestMarkFailed_PassesVideoID(t *testing.T) {
	q := &stubQuerier{rowsAffected: 1}
	repo := video.NewRepository(q)

	_ = repo.MarkFailed(context.Background(), "expected-id")

	if len(q.lastArgs) < 2 || q.lastArgs[1] != "expected-id" {
		t.Errorf("video ID arg = %v, want 'expected-id'", q.lastArgs)
	}
}

func TestMarkFailed_ExecError_ReturnsError(t *testing.T) {
	q := &stubQuerier{execErr: errors.New("db down")}
	repo := video.NewRepository(q)

	if err := repo.MarkFailed(context.Background(), "vid"); err == nil {
		t.Fatal("expected error, got nil")
	}
}

// ── Status constants ──────────────────────────────────────────────────────────

func TestStatusConstants(t *testing.T) {
	if string(video.StatusReady) != "ready" {
		t.Errorf("StatusReady = %q, want %q", video.StatusReady, "ready")
	}
	if string(video.StatusFailed) != "failed" {
		t.Errorf("StatusFailed = %q, want %q", video.StatusFailed, "failed")
	}
}
