package handler_test

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/ai-teammate/mytube/api/internal/handler"
	"github.com/ai-teammate/mytube/api/internal/repository"
)

// ─── stub RecommendationProvider ─────────────────────────────────────────────

type stubRecommendationProvider struct {
	videos []repository.RecommendationVideo
	err    error
}

func (s *stubRecommendationProvider) GetRecommendations(_ context.Context, _ string, _ int) ([]repository.RecommendationVideo, error) {
	return s.videos, s.err
}

// serveRecommendations calls the recommendations handler with the given request.
func serveRecommendations(h http.Handler, r *http.Request) *httptest.ResponseRecorder {
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, r)
	return rec
}

// makeRecommendationRequest builds a GET request for the recommendations route
// with PathValue("id") set to videoID.
func makeRecommendationRequest(videoID string) *http.Request {
	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+videoID+"/recommendations", nil)
	// Simulate Go 1.22 ServeMux path value injection.
	req.SetPathValue("id", videoID)
	return req
}

// makeRecommendationVideo returns a minimal RecommendationVideo for use in tests.
func makeRecommendationVideo(id, title string) repository.RecommendationVideo {
	now := time.Now().Truncate(time.Second)
	thumb := "https://cdn.example.com/thumb.jpg"
	return repository.RecommendationVideo{
		ID:               id,
		Title:            title,
		ThumbnailURL:     &thumb,
		ViewCount:        100,
		UploaderUsername: "alice",
		CreatedAt:        now,
		Status:           "ready",
	}
}

// ─── GET /api/videos/{id}/recommendations ────────────────────────────────────

func TestRecommendationsHandler_GET_Success_ReturnsList(t *testing.T) {
	videos := []repository.RecommendationVideo{
		makeRecommendationVideo("vid-2", "Video 2"),
		makeRecommendationVideo("vid-3", "Video 3"),
	}
	p := &stubRecommendationProvider{videos: videos}
	h := handler.NewRecommendationsHandler(p)

	req := makeRecommendationRequest(testVideoID)
	rec := serveRecommendations(h, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}

	var body handler.RecommendationsResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if len(body.Recommendations) != 2 {
		t.Errorf("expected 2 recommendations, got %d", len(body.Recommendations))
	}
	if body.Recommendations[0].ID != "vid-2" {
		t.Errorf("Recommendations[0].ID: got %q, want %q", body.Recommendations[0].ID, "vid-2")
	}
	if body.Recommendations[1].ID != "vid-3" {
		t.Errorf("Recommendations[1].ID: got %q, want %q", body.Recommendations[1].ID, "vid-3")
	}
}

func TestRecommendationsHandler_GET_EmptySlice_WhenNoRecommendations(t *testing.T) {
	p := &stubRecommendationProvider{videos: []repository.RecommendationVideo{}}
	h := handler.NewRecommendationsHandler(p)

	req := makeRecommendationRequest(testVideoID)
	rec := serveRecommendations(h, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}

	var body handler.RecommendationsResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if len(body.Recommendations) != 0 {
		t.Errorf("expected 0 recommendations, got %d", len(body.Recommendations))
	}
}

func TestRecommendationsHandler_GET_RepositoryError_Returns500(t *testing.T) {
	p := &stubRecommendationProvider{err: errors.New("db error")}
	h := handler.NewRecommendationsHandler(p)

	req := makeRecommendationRequest(testVideoID)
	rec := serveRecommendations(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestRecommendationsHandler_UnsupportedMethod_Returns405(t *testing.T) {
	p := &stubRecommendationProvider{}
	h := handler.NewRecommendationsHandler(p)

	req := httptest.NewRequest(http.MethodPost, "/api/videos/"+testVideoID+"/recommendations", nil)
	req.SetPathValue("id", testVideoID)
	rec := serveRecommendations(h, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
}

func TestRecommendationsHandler_EmptyVideoID_Returns400(t *testing.T) {
	p := &stubRecommendationProvider{}
	h := handler.NewRecommendationsHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/videos//recommendations", nil)
	req.SetPathValue("id", "")
	rec := serveRecommendations(h, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestRecommendationsHandler_InvalidVideoID_Returns400(t *testing.T) {
	p := &stubRecommendationProvider{}
	h := handler.NewRecommendationsHandler(p)

	for _, id := range []string{"not-a-uuid", "v1", "../secret"} {
		req := httptest.NewRequest(http.MethodGet, "/api/videos/"+id+"/recommendations", nil)
		req.SetPathValue("id", id)
		rec := serveRecommendations(h, req)

		if rec.Code != http.StatusBadRequest {
			t.Errorf("id=%q: expected 400, got %d", id, rec.Code)
		}
	}
}

func TestRecommendationsHandler_GET_ContentTypeIsJSON(t *testing.T) {
	p := &stubRecommendationProvider{videos: []repository.RecommendationVideo{}}
	h := handler.NewRecommendationsHandler(p)

	req := makeRecommendationRequest(testVideoID)
	rec := serveRecommendations(h, req)

	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type: got %q, want %q", ct, "application/json")
	}
}

func TestRecommendationsHandler_GET_NilThumbnailSerializedAsNull(t *testing.T) {
	v := makeRecommendationVideo("vid-2", "No Thumb")
	v.ThumbnailURL = nil
	p := &stubRecommendationProvider{videos: []repository.RecommendationVideo{v}}
	h := handler.NewRecommendationsHandler(p)

	req := makeRecommendationRequest(testVideoID)
	rec := serveRecommendations(h, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}

	var body handler.RecommendationsResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if len(body.Recommendations) != 1 {
		t.Fatalf("expected 1 recommendation, got %d", len(body.Recommendations))
	}
	if body.Recommendations[0].ThumbnailURL != nil {
		t.Errorf("ThumbnailURL: expected nil, got %q", *body.Recommendations[0].ThumbnailURL)
	}
}

func TestRecommendationsHandler_GET_AllFieldsMappedCorrectly(t *testing.T) {
	thumb := "https://cdn.example.com/thumb.jpg"
	now := time.Date(2024, 1, 15, 10, 0, 0, 0, time.UTC)
	v := repository.RecommendationVideo{
		ID:               "vid-abc",
		Title:            "Mapped Video",
		ThumbnailURL:     &thumb,
		ViewCount:        999,
		UploaderUsername: "bob",
		CreatedAt:        now,
		Status:           "ready",
	}
	p := &stubRecommendationProvider{videos: []repository.RecommendationVideo{v}}
	h := handler.NewRecommendationsHandler(p)

	req := makeRecommendationRequest(testVideoID)
	rec := serveRecommendations(h, req)

	var body handler.RecommendationsResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if len(body.Recommendations) != 1 {
		t.Fatalf("expected 1 recommendation, got %d", len(body.Recommendations))
	}
	item := body.Recommendations[0]
	if item.ID != "vid-abc" {
		t.Errorf("ID: got %q, want %q", item.ID, "vid-abc")
	}
	if item.Title != "Mapped Video" {
		t.Errorf("Title: got %q, want %q", item.Title, "Mapped Video")
	}
	if item.ThumbnailURL == nil || *item.ThumbnailURL != thumb {
		t.Errorf("ThumbnailURL: got %v, want %q", item.ThumbnailURL, thumb)
	}
	if item.ViewCount != 999 {
		t.Errorf("ViewCount: got %d, want 999", item.ViewCount)
	}
	if item.UploaderUsername != "bob" {
		t.Errorf("UploaderUsername: got %q, want %q", item.UploaderUsername, "bob")
	}
	if !item.CreatedAt.Equal(now) {
		t.Errorf("CreatedAt: got %v, want %v", item.CreatedAt, now)
	}
}

func TestRecommendationsHandler_GET_AllowHeaderOn405(t *testing.T) {
	p := &stubRecommendationProvider{}
	h := handler.NewRecommendationsHandler(p)

	req := httptest.NewRequest(http.MethodDelete, "/api/videos/"+testVideoID+"/recommendations", nil)
	req.SetPathValue("id", testVideoID)
	rec := serveRecommendations(h, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("expected 405, got %d", rec.Code)
	}
	if allow := rec.Header().Get("Allow"); allow != "GET" {
		t.Errorf("Allow header: got %q, want %q", allow, "GET")
	}
}
