package handler_test

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/ai-teammate/mytube/api/internal/auth"
	"github.com/ai-teammate/mytube/api/internal/handler"
	"github.com/ai-teammate/mytube/api/internal/repository"
)

// ─── stubs ────────────────────────────────────────────────────────────────────

type stubDashboardVideoProvider struct {
	videos []repository.DashboardVideo
	err    error
}

func (s *stubDashboardVideoProvider) GetVideosByUploaderID(_ context.Context, _ string) ([]repository.DashboardVideo, error) {
	return s.videos, s.err
}

// ─── helpers ──────────────────────────────────────────────────────────────────

func serveMeVideos(h http.Handler, r *http.Request) *httptest.ResponseRecorder {
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, r)
	return rec
}

func makeDashboardVideo(id, title, status string) repository.DashboardVideo {
	thumb := "https://cdn.example.com/thumb.jpg"
	return repository.DashboardVideo{
		ID:           id,
		Title:        title,
		Status:       status,
		ThumbnailURL: &thumb,
		ViewCount:    10,
		CreatedAt:    time.Now().Truncate(time.Second),
		Tags:         []string{},
	}
}

// ─── GET /api/me/videos tests ─────────────────────────────────────────────────

func TestNewMeVideosHandler_NoClaims_Returns401(t *testing.T) {
	videos := &stubDashboardVideoProvider{}
	users := &stubUserIDProvider{user: &repository.User{ID: "u1", Username: "alice"}}
	h := handler.NewMeVideosHandler(videos, users)

	req := httptest.NewRequest(http.MethodGet, "/api/me/videos", nil)
	// No claims in context.
	rec := serveMeVideos(h, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rec.Code)
	}
}

func TestNewMeVideosHandler_WrongMethod_Returns405(t *testing.T) {
	videos := &stubDashboardVideoProvider{}
	users := &stubUserIDProvider{user: &repository.User{ID: "u1", Username: "alice"}}
	h := handler.NewMeVideosHandler(videos, users)

	claims := &auth.TokenClaims{UID: "uid1", Email: "alice@example.com"}
	req := withClaims(httptest.NewRequest(http.MethodPost, "/api/me/videos", nil), claims)
	rec := serveMeVideos(h, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
}

func TestNewMeVideosHandler_UserNotFound_Returns404(t *testing.T) {
	videos := &stubDashboardVideoProvider{}
	users := &stubUserIDProvider{user: nil}
	h := handler.NewMeVideosHandler(videos, users)

	claims := &auth.TokenClaims{UID: "uid-unknown"}
	req := withClaims(httptest.NewRequest(http.MethodGet, "/api/me/videos", nil), claims)
	rec := serveMeVideos(h, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

func TestNewMeVideosHandler_GetUserError_Returns500(t *testing.T) {
	videos := &stubDashboardVideoProvider{}
	users := &stubUserIDProvider{err: errors.New("db error")}
	h := handler.NewMeVideosHandler(videos, users)

	claims := &auth.TokenClaims{UID: "uid1"}
	req := withClaims(httptest.NewRequest(http.MethodGet, "/api/me/videos", nil), claims)
	rec := serveMeVideos(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestNewMeVideosHandler_GetVideosError_Returns500(t *testing.T) {
	videos := &stubDashboardVideoProvider{err: errors.New("db error")}
	users := &stubUserIDProvider{user: &repository.User{ID: "u1", Username: "alice"}}
	h := handler.NewMeVideosHandler(videos, users)

	claims := &auth.TokenClaims{UID: "uid1"}
	req := withClaims(httptest.NewRequest(http.MethodGet, "/api/me/videos", nil), claims)
	rec := serveMeVideos(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestNewMeVideosHandler_EmptyList_ReturnsEmptyArray(t *testing.T) {
	videos := &stubDashboardVideoProvider{videos: []repository.DashboardVideo{}}
	users := &stubUserIDProvider{user: &repository.User{ID: "u1", Username: "alice"}}
	h := handler.NewMeVideosHandler(videos, users)

	claims := &auth.TokenClaims{UID: "uid1"}
	req := withClaims(httptest.NewRequest(http.MethodGet, "/api/me/videos", nil), claims)
	rec := serveMeVideos(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("expected application/json, got %q", ct)
	}

	var items []handler.DashboardVideoListItem
	if err := json.NewDecoder(rec.Body).Decode(&items); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if len(items) != 0 {
		t.Errorf("expected empty array, got %d items", len(items))
	}
}

func TestNewMeVideosHandler_ReturnsAllStatuses(t *testing.T) {
	vids := []repository.DashboardVideo{
		makeDashboardVideo("vid-1", "Ready Video", "ready"),
		makeDashboardVideo("vid-2", "Processing Video", "processing"),
		makeDashboardVideo("vid-3", "Pending Video", "pending"),
		makeDashboardVideo("vid-4", "Failed Video", "failed"),
	}
	videos := &stubDashboardVideoProvider{videos: vids}
	users := &stubUserIDProvider{user: &repository.User{ID: "u1", Username: "alice"}}
	h := handler.NewMeVideosHandler(videos, users)

	claims := &auth.TokenClaims{UID: "uid1"}
	req := withClaims(httptest.NewRequest(http.MethodGet, "/api/me/videos", nil), claims)
	rec := serveMeVideos(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var items []handler.DashboardVideoListItem
	if err := json.NewDecoder(rec.Body).Decode(&items); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if len(items) != 4 {
		t.Fatalf("expected 4 items, got %d", len(items))
	}

	statusMap := make(map[string]bool)
	for _, item := range items {
		statusMap[item.Status] = true
	}
	for _, s := range []string{"ready", "processing", "pending", "failed"} {
		if !statusMap[s] {
			t.Errorf("expected status %q in response", s)
		}
	}
}

func TestNewMeVideosHandler_Success_ResponseFields(t *testing.T) {
	now := time.Now().Truncate(time.Second)
	thumb := "https://cdn.example.com/thumb.jpg"
	vids := []repository.DashboardVideo{
		{
			ID:           "00000000-0000-0000-0000-000000000001",
			Title:        "My Test Video",
			Status:       "ready",
			ThumbnailURL: &thumb,
			ViewCount:    42,
			CreatedAt:    now,
		},
	}
	videos := &stubDashboardVideoProvider{videos: vids}
	users := &stubUserIDProvider{user: &repository.User{ID: "u1", Username: "alice"}}
	h := handler.NewMeVideosHandler(videos, users)

	claims := &auth.TokenClaims{UID: "uid1"}
	req := withClaims(httptest.NewRequest(http.MethodGet, "/api/me/videos", nil), claims)
	rec := serveMeVideos(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var items []handler.DashboardVideoListItem
	if err := json.NewDecoder(rec.Body).Decode(&items); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(items) != 1 {
		t.Fatalf("expected 1 item, got %d", len(items))
	}
	item := items[0]
	if item.ID != "00000000-0000-0000-0000-000000000001" {
		t.Errorf("ID: got %q, want %q", item.ID, "00000000-0000-0000-0000-000000000001")
	}
	if item.Title != "My Test Video" {
		t.Errorf("Title: got %q, want My Test Video", item.Title)
	}
	if item.Status != "ready" {
		t.Errorf("Status: got %q, want ready", item.Status)
	}
	if item.ThumbnailURL == nil || *item.ThumbnailURL != thumb {
		t.Errorf("ThumbnailURL: got %v, want %q", item.ThumbnailURL, thumb)
	}
	if item.ViewCount != 42 {
		t.Errorf("ViewCount: got %d, want 42", item.ViewCount)
	}
}

func TestNewMeVideosHandler_NilThumbnail_SerializedAsNull(t *testing.T) {
	vids := []repository.DashboardVideo{
		{ID: "vid-1", Title: "No Thumb", Status: "processing", ThumbnailURL: nil},
	}
	videos := &stubDashboardVideoProvider{videos: vids}
	users := &stubUserIDProvider{user: &repository.User{ID: "u1", Username: "alice"}}
	h := handler.NewMeVideosHandler(videos, users)

	claims := &auth.TokenClaims{UID: "uid1"}
	req := withClaims(httptest.NewRequest(http.MethodGet, "/api/me/videos", nil), claims)
	rec := serveMeVideos(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var raw []map[string]json.RawMessage
	if err := json.NewDecoder(rec.Body).Decode(&raw); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(raw) != 1 {
		t.Fatalf("expected 1 item, got %d", len(raw))
	}
	if string(raw[0]["thumbnail_url"]) != "null" {
		t.Errorf("thumbnail_url: got %s, want null", string(raw[0]["thumbnail_url"]))
	}
}

// Note: stubUserIDProvider is defined in videos_test.go and shared across handler tests.
