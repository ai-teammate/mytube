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

// ─── stub SearchProvider ───────────────────────────────────────────────────────

type stubSearchProvider struct {
	videos    []repository.SearchVideo
	searchErr error
	cats      []repository.Category
	catsErr   error
}

func (s *stubSearchProvider) Search(_ context.Context, _ repository.SearchParams) ([]repository.SearchVideo, error) {
	return s.videos, s.searchErr
}

func (s *stubSearchProvider) GetRecent(_ context.Context, _ int) ([]repository.SearchVideo, error) {
	return s.videos, s.searchErr
}

func (s *stubSearchProvider) GetPopular(_ context.Context, _ int) ([]repository.SearchVideo, error) {
	return s.videos, s.searchErr
}

func (s *stubSearchProvider) GetAllCategories(_ context.Context) ([]repository.Category, error) {
	return s.cats, s.catsErr
}

func (s *stubSearchProvider) GetByCategory(_ context.Context, _ int, _ int, _ int) ([]repository.SearchVideo, error) {
	return s.videos, s.searchErr
}

// ─── helpers ──────────────────────────────────────────────────────────────────

func makeTestSearchVideos() []repository.SearchVideo {
	thumb := "https://cdn.example.com/thumb.jpg"
	return []repository.SearchVideo{
		{
			ID:               "00000000-0000-0000-0000-000000000001",
			Title:            "Go Tutorial",
			ThumbnailURL:     &thumb,
			ViewCount:        42,
			UploaderUsername: "alice",
			CreatedAt:        time.Now().Truncate(time.Second),
			Status:           "ready",
		},
		{
			ID:               "00000000-0000-0000-0000-000000000002",
			Title:            "Python Intro",
			ThumbnailURL:     nil,
			ViewCount:        100,
			UploaderUsername: "bob",
			CreatedAt:        time.Now().Truncate(time.Second),
			Status:           "ready",
		},
	}
}

// ─── GET /api/search tests ─────────────────────────────────────────────────────

func TestSearchHandler_GET_ReturnsVideoCards(t *testing.T) {
	p := &stubSearchProvider{videos: makeTestSearchVideos()}
	h := handler.NewSearchHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/search?q=go", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("expected application/json, got %q", ct)
	}

	var cards []handler.VideoCard
	if err := json.NewDecoder(rec.Body).Decode(&cards); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if len(cards) != 2 {
		t.Errorf("expected 2 cards, got %d", len(cards))
	}
	if cards[0].Title != "Go Tutorial" {
		t.Errorf("cards[0].Title: got %q, want Go Tutorial", cards[0].Title)
	}
}

func TestSearchHandler_GET_EmptyResults_ReturnsEmptyArray(t *testing.T) {
	p := &stubSearchProvider{videos: []repository.SearchVideo{}}
	h := handler.NewSearchHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/search?q=nothing", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var raw json.RawMessage
	if err := json.NewDecoder(rec.Body).Decode(&raw); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if string(raw) != "[]" {
		t.Errorf("expected [], got %s", string(raw))
	}
}

func TestSearchHandler_GET_RepositoryError_Returns500(t *testing.T) {
	p := &stubSearchProvider{searchErr: errors.New("db error")}
	h := handler.NewSearchHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/search?q=go", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestSearchHandler_GET_InvalidCategoryID_Returns400(t *testing.T) {
	p := &stubSearchProvider{}
	h := handler.NewSearchHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/search?category_id=notanint", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestSearchHandler_GET_ZeroCategoryID_Returns400(t *testing.T) {
	p := &stubSearchProvider{}
	h := handler.NewSearchHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/search?category_id=0", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestSearchHandler_UnsupportedMethod_Returns405(t *testing.T) {
	p := &stubSearchProvider{}
	h := handler.NewSearchHandler(p)

	req := httptest.NewRequest(http.MethodPost, "/api/search", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
}

func TestSearchHandler_GET_NilThumbnailURL_SerializedAsNull(t *testing.T) {
	videos := []repository.SearchVideo{{
		ID:               "v1",
		Title:            "No Thumb",
		ThumbnailURL:     nil,
		ViewCount:        0,
		UploaderUsername: "carol",
		CreatedAt:        time.Now(),
	}}
	p := &stubSearchProvider{videos: videos}
	h := handler.NewSearchHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/search", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	var cards []map[string]json.RawMessage
	if err := json.NewDecoder(rec.Body).Decode(&cards); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(cards) != 1 {
		t.Fatalf("expected 1, got %d", len(cards))
	}
	if string(cards[0]["thumbnail_url"]) != "null" {
		t.Errorf("thumbnail_url: got %s, want null", string(cards[0]["thumbnail_url"]))
	}
}

func TestSearchHandler_GET_ValidCategoryID_CallsSearch(t *testing.T) {
	p := &stubSearchProvider{videos: []repository.SearchVideo{}}
	h := handler.NewSearchHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/search?category_id=3", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}
}

// ─── GET /api/videos/recent tests ─────────────────────────────────────────────

func TestRecentVideosHandler_GET_ReturnsVideoCards(t *testing.T) {
	p := &stubSearchProvider{videos: makeTestSearchVideos()}
	h := handler.NewRecentVideosHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/recent", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var cards []handler.VideoCard
	if err := json.NewDecoder(rec.Body).Decode(&cards); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(cards) != 2 {
		t.Errorf("expected 2, got %d", len(cards))
	}
}

func TestRecentVideosHandler_GET_RepositoryError_Returns500(t *testing.T) {
	p := &stubSearchProvider{searchErr: errors.New("db error")}
	h := handler.NewRecentVideosHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/recent", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestRecentVideosHandler_UnsupportedMethod_Returns405(t *testing.T) {
	p := &stubSearchProvider{}
	h := handler.NewRecentVideosHandler(p)

	req := httptest.NewRequest(http.MethodPost, "/api/videos/recent", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
}

func TestRecentVideosHandler_GET_EmptyResults_ReturnsEmptyArray(t *testing.T) {
	p := &stubSearchProvider{videos: []repository.SearchVideo{}}
	h := handler.NewRecentVideosHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/recent", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	var raw json.RawMessage
	if err := json.NewDecoder(rec.Body).Decode(&raw); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if string(raw) != "[]" {
		t.Errorf("expected [], got %s", string(raw))
	}
}

func TestRecentVideosHandler_GET_CustomLimit(t *testing.T) {
	p := &stubSearchProvider{videos: makeTestSearchVideos()}
	h := handler.NewRecentVideosHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/recent?limit=5", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}
}

// ─── GET /api/videos/popular tests ────────────────────────────────────────────

func TestPopularVideosHandler_GET_ReturnsVideoCards(t *testing.T) {
	p := &stubSearchProvider{videos: makeTestSearchVideos()}
	h := handler.NewPopularVideosHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/popular", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var cards []handler.VideoCard
	if err := json.NewDecoder(rec.Body).Decode(&cards); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(cards) != 2 {
		t.Errorf("expected 2, got %d", len(cards))
	}
}

func TestPopularVideosHandler_GET_RepositoryError_Returns500(t *testing.T) {
	p := &stubSearchProvider{searchErr: errors.New("db error")}
	h := handler.NewPopularVideosHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/popular", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestPopularVideosHandler_UnsupportedMethod_Returns405(t *testing.T) {
	p := &stubSearchProvider{}
	h := handler.NewPopularVideosHandler(p)

	req := httptest.NewRequest(http.MethodDelete, "/api/videos/popular", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
}

func TestPopularVideosHandler_GET_EmptyResults_ReturnsEmptyArray(t *testing.T) {
	p := &stubSearchProvider{videos: []repository.SearchVideo{}}
	h := handler.NewPopularVideosHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/popular", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	var raw json.RawMessage
	if err := json.NewDecoder(rec.Body).Decode(&raw); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if string(raw) != "[]" {
		t.Errorf("expected [], got %s", string(raw))
	}
}

// ─── GET /api/categories tests ─────────────────────────────────────────────────

func TestCategoriesHandler_GET_ReturnsCategories(t *testing.T) {
	cats := []repository.Category{
		{ID: 1, Name: "Education"},
		{ID: 2, Name: "Gaming"},
		{ID: 3, Name: "Music"},
	}
	p := &stubSearchProvider{cats: cats}
	h := handler.NewCategoriesHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/categories", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var resp []handler.CategoryResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(resp) != 3 {
		t.Errorf("expected 3, got %d", len(resp))
	}
	if resp[0].Name != "Education" {
		t.Errorf("resp[0].Name: got %q, want Education", resp[0].Name)
	}
	if resp[0].ID != 1 {
		t.Errorf("resp[0].ID: got %d, want 1", resp[0].ID)
	}
}

func TestCategoriesHandler_GET_EmptyCategories_ReturnsEmptyArray(t *testing.T) {
	p := &stubSearchProvider{cats: []repository.Category{}}
	h := handler.NewCategoriesHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/categories", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	var raw json.RawMessage
	if err := json.NewDecoder(rec.Body).Decode(&raw); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if string(raw) != "[]" {
		t.Errorf("expected [], got %s", string(raw))
	}
}

func TestCategoriesHandler_GET_RepositoryError_Returns500(t *testing.T) {
	p := &stubSearchProvider{catsErr: errors.New("db error")}
	h := handler.NewCategoriesHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/categories", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestCategoriesHandler_UnsupportedMethod_Returns405(t *testing.T) {
	p := &stubSearchProvider{}
	h := handler.NewCategoriesHandler(p)

	req := httptest.NewRequest(http.MethodPost, "/api/categories", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
}

// ─── GET /api/videos?category_id= tests ───────────────────────────────────────

func TestBrowseVideosHandler_GET_WithCategoryID_ReturnsVideos(t *testing.T) {
	p := &stubSearchProvider{videos: makeTestSearchVideos()}
	h := handler.NewBrowseVideosHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/videos?category_id=1", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var cards []handler.VideoCard
	if err := json.NewDecoder(rec.Body).Decode(&cards); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(cards) != 2 {
		t.Errorf("expected 2, got %d", len(cards))
	}
}

func TestBrowseVideosHandler_GET_MissingCategoryID_Returns400(t *testing.T) {
	p := &stubSearchProvider{}
	h := handler.NewBrowseVideosHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/videos", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestBrowseVideosHandler_GET_InvalidCategoryID_Returns400(t *testing.T) {
	p := &stubSearchProvider{}
	h := handler.NewBrowseVideosHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/videos?category_id=abc", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestBrowseVideosHandler_GET_ZeroCategoryID_Returns400(t *testing.T) {
	p := &stubSearchProvider{}
	h := handler.NewBrowseVideosHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/videos?category_id=0", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestBrowseVideosHandler_GET_RepositoryError_Returns500(t *testing.T) {
	p := &stubSearchProvider{searchErr: errors.New("db error")}
	h := handler.NewBrowseVideosHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/videos?category_id=1", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestBrowseVideosHandler_UnsupportedMethod_Returns405(t *testing.T) {
	p := &stubSearchProvider{}
	h := handler.NewBrowseVideosHandler(p)

	req := httptest.NewRequest(http.MethodPut, "/api/videos?category_id=1", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
}

func TestBrowseVideosHandler_GET_WithOffsetAndLimit(t *testing.T) {
	p := &stubSearchProvider{videos: []repository.SearchVideo{}}
	h := handler.NewBrowseVideosHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/videos?category_id=2&limit=10&offset=5", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}
}

// ─── parseLimit and parseOffset tests (via handler behavior) ──────────────────

func TestSearchHandler_ParseLimit_InvalidString_UsesDefault(t *testing.T) {
	p := &stubSearchProvider{videos: []repository.SearchVideo{}}
	h := handler.NewSearchHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/search?limit=invalid", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	// Should not error, just uses default limit.
	if rec.Code != http.StatusOK {
		t.Errorf("expected 200 with invalid limit, got %d", rec.Code)
	}
}

func TestSearchHandler_ParseOffset_InvalidString_UsesZero(t *testing.T) {
	p := &stubSearchProvider{videos: []repository.SearchVideo{}}
	h := handler.NewSearchHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/search?offset=invalid", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200 with invalid offset, got %d", rec.Code)
	}
}

func TestSearchHandler_AllowHeader_SetOn405(t *testing.T) {
	p := &stubSearchProvider{}
	h := handler.NewSearchHandler(p)

	req := httptest.NewRequest(http.MethodDelete, "/api/search", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if allow := rec.Header().Get("Allow"); allow != "GET" {
		t.Errorf("Allow header: got %q, want GET", allow)
	}
}

// ─── status field regression tests ────────────────────────────────────────────

// TestRecentVideosHandler_GET_ResponseIncludesStatusReady verifies that each
// VideoCard in the /api/videos/recent response contains a "status" field set
// to "ready".  This is the reproduction test for MYTUBE-224.
func TestRecentVideosHandler_GET_ResponseIncludesStatusReady(t *testing.T) {
	p := &stubSearchProvider{videos: makeTestSearchVideos()}
	h := handler.NewRecentVideosHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/recent?limit=20", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}

	var cards []map[string]json.RawMessage
	if err := json.NewDecoder(rec.Body).Decode(&cards); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if len(cards) == 0 {
		t.Fatal("expected at least one video card in the response")
	}
	for i, card := range cards {
		statusRaw, ok := card["status"]
		if !ok {
			t.Errorf("cards[%d]: missing 'status' field in response", i)
			continue
		}
		var status string
		if err := json.Unmarshal(statusRaw, &status); err != nil {
			t.Errorf("cards[%d]: cannot unmarshal status: %v", i, err)
			continue
		}
		if status != "ready" {
			t.Errorf("cards[%d]: expected status='ready', got %q", i, status)
		}
	}
}

// TestPopularVideosHandler_GET_ResponseIncludesStatusReady verifies that each
// VideoCard in the /api/videos/popular response contains a "status" field set
// to "ready".  This is the reproduction test for MYTUBE-224.
func TestPopularVideosHandler_GET_ResponseIncludesStatusReady(t *testing.T) {
	p := &stubSearchProvider{videos: makeTestSearchVideos()}
	h := handler.NewPopularVideosHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/popular?limit=20", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}

	var cards []map[string]json.RawMessage
	if err := json.NewDecoder(rec.Body).Decode(&cards); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if len(cards) == 0 {
		t.Fatal("expected at least one video card in the response")
	}
	for i, card := range cards {
		statusRaw, ok := card["status"]
		if !ok {
			t.Errorf("cards[%d]: missing 'status' field in response", i)
			continue
		}
		var status string
		if err := json.Unmarshal(statusRaw, &status); err != nil {
			t.Errorf("cards[%d]: cannot unmarshal status: %v", i, err)
			continue
		}
		if status != "ready" {
			t.Errorf("cards[%d]: expected status='ready', got %q", i, status)
		}
	}
}

// TestBrowseVideosHandler_GET_WithCategoryID_ValidatesCategoryFiltering verifies that
// the search provider's GetByCategory method receives the correct categoryID, limit, and offset
// parameters. This ensures category filtering is properly wired through the handler.
func TestBrowseVideosHandler_GET_WithCategoryID_ValidatesCategoryFiltering(t *testing.T) {
// Create a spy stub that tracks which parameters it was called with
spy := &spySearchProvider{
videos: makeTestSearchVideos(),
}

h := handler.NewBrowseVideosHandler(spy)

// Request category 5 with specific limit and offset
req := httptest.NewRequest(http.MethodGet, "/api/videos?category_id=5&limit=10&offset=2", nil)
rec := httptest.NewRecorder()
h.ServeHTTP(rec, req)

if rec.Code != http.StatusOK {
t.Errorf("expected 200, got %d", rec.Code)
}

// Verify the stub was called with the correct parameters
if spy.lastCategoryID != 5 {
t.Errorf("expected categoryID=5, got %d", spy.lastCategoryID)
}
if spy.lastLimit != 10 {
t.Errorf("expected limit=10, got %d", spy.lastLimit)
}
if spy.lastOffset != 2 {
t.Errorf("expected offset=2, got %d", spy.lastOffset)
}
}

// spySearchProvider tracks the arguments passed to GetByCategory
type spySearchProvider struct {
videos         []repository.SearchVideo
searchErr      error
cats           []repository.Category
catsErr        error
lastCategoryID int
lastLimit      int
lastOffset     int
}

func (s *spySearchProvider) Search(_ context.Context, _ repository.SearchParams) ([]repository.SearchVideo, error) {
return s.videos, s.searchErr
}

func (s *spySearchProvider) GetRecent(_ context.Context, _ int) ([]repository.SearchVideo, error) {
return s.videos, s.searchErr
}

func (s *spySearchProvider) GetPopular(_ context.Context, _ int) ([]repository.SearchVideo, error) {
return s.videos, s.searchErr
}

func (s *spySearchProvider) GetAllCategories(_ context.Context) ([]repository.Category, error) {
return s.cats, s.catsErr
}

func (s *spySearchProvider) GetByCategory(_ context.Context, categoryID, limit, offset int) ([]repository.SearchVideo, error) {
s.lastCategoryID = categoryID
s.lastLimit = limit
s.lastOffset = offset
return s.videos, s.searchErr
}
