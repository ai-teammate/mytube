package handler_test

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/ai-teammate/mytube/api/internal/auth"
	"github.com/ai-teammate/mytube/api/internal/handler"
	"github.com/ai-teammate/mytube/api/internal/repository"
)

// ─── stub RatingStore ─────────────────────────────────────────────────────────

type stubRatingStore struct {
	summary    *repository.RatingSummary
	summaryErr error
	upsertErr  error
}

func (s *stubRatingStore) UpsertRating(_ context.Context, _, _ string, _ int) (*repository.RatingSummary, error) {
	return s.summary, s.upsertErr
}

func (s *stubRatingStore) GetSummary(_ context.Context, _ string, _ *string) (*repository.RatingSummary, error) {
	return s.summary, s.summaryErr
}

// ─── stub RatingUserProvider ──────────────────────────────────────────────────

type stubRatingUserProvider struct {
	user    *repository.User
	userErr error
}

func (s *stubRatingUserProvider) GetByFirebaseUID(_ context.Context, _ string) (*repository.User, error) {
	return s.user, s.userErr
}

// ─── helpers ──────────────────────────────────────────────────────────────────

func makeRatingSummary(avg float64, count int64, myRating *int) *repository.RatingSummary {
	return &repository.RatingSummary{
		AverageRating: avg,
		RatingCount:   count,
		MyRating:      myRating,
	}
}

const ratingTestVideoID = "00000000-0000-0000-0000-000000000001"

// authRequest injects claims and returns a request with auth context set.
func authRequest(r *http.Request) *http.Request {
	claims := &auth.TokenClaims{UID: "firebase-uid-1"}
	return withClaims(r, claims)
}

// ─── GET /api/videos/:id/rating tests ────────────────────────────────────────

func TestRatingHandler_GET_ReturnsSummary(t *testing.T) {
	myRating := 3
	store := &stubRatingStore{summary: makeRatingSummary(3.5, 10, &myRating)}
	users := &stubRatingUserProvider{}
	h := handler.NewRatingHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+ratingTestVideoID+"/rating", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var body handler.RatingResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if body.AverageRating != 3.5 {
		t.Errorf("AverageRating: got %v, want 3.5", body.AverageRating)
	}
	if body.RatingCount != 10 {
		t.Errorf("RatingCount: got %d, want 10", body.RatingCount)
	}
	if body.MyRating == nil || *body.MyRating != 3 {
		t.Errorf("MyRating: got %v, want 3", body.MyRating)
	}
}

func TestRatingHandler_GET_StoreError_Returns500(t *testing.T) {
	store := &stubRatingStore{summaryErr: errors.New("db error")}
	users := &stubRatingUserProvider{}
	h := handler.NewRatingHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+ratingTestVideoID+"/rating", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestRatingHandler_GET_InvalidVideoID_Returns400(t *testing.T) {
	store := &stubRatingStore{}
	users := &stubRatingUserProvider{}
	h := handler.NewRatingHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/not-a-uuid/rating", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestRatingHandler_GET_EmptyVideoID_Returns400(t *testing.T) {
	store := &stubRatingStore{}
	users := &stubRatingUserProvider{}
	h := handler.NewRatingHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/videos//rating", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestRatingHandler_UnsupportedMethod_Returns405(t *testing.T) {
	store := &stubRatingStore{}
	users := &stubRatingUserProvider{}
	h := handler.NewRatingHandler(store, users)

	req := httptest.NewRequest(http.MethodDelete, "/api/videos/"+ratingTestVideoID+"/rating", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
	if allow := rec.Header().Get("Allow"); !strings.Contains(allow, "GET") {
		t.Errorf("Allow header: got %q, want to contain GET", allow)
	}
}

// ─── POST /api/videos/:id/rating tests ───────────────────────────────────────

func TestRatingHandler_POST_NoAuth_Returns401(t *testing.T) {
	store := &stubRatingStore{}
	users := &stubRatingUserProvider{}
	h := handler.NewRatingHandler(store, users)

	body := strings.NewReader(`{"stars":4}`)
	req := httptest.NewRequest(http.MethodPost, "/api/videos/"+ratingTestVideoID+"/rating", body)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rec.Code)
	}
}

func TestRatingHandler_POST_InvalidStars_Returns422(t *testing.T) {
	store := &stubRatingStore{}
	user := &repository.User{ID: "user-1", FirebaseUID: "firebase-uid-1", Username: "alice"}
	users := &stubRatingUserProvider{user: user}
	h := handler.NewRatingHandler(store, users)

	for _, stars := range []int{0, 6, -1} {
		bodyBytes, _ := json.Marshal(map[string]int{"stars": stars})
		req := httptest.NewRequest(http.MethodPost, "/api/videos/"+ratingTestVideoID+"/rating", bytes.NewReader(bodyBytes))
		req = authRequest(req)
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)

		if rec.Code != http.StatusUnprocessableEntity {
			t.Errorf("stars=%d: expected 422, got %d", stars, rec.Code)
		}
	}
}

func TestRatingHandler_POST_ValidStars_ReturnsUpdatedSummary(t *testing.T) {
	myRating := 4
	store := &stubRatingStore{summary: makeRatingSummary(4.0, 5, &myRating)}
	user := &repository.User{ID: "user-1", FirebaseUID: "firebase-uid-1", Username: "alice"}
	users := &stubRatingUserProvider{user: user}
	h := handler.NewRatingHandler(store, users)

	bodyBytes, _ := json.Marshal(map[string]int{"stars": 4})
	req := httptest.NewRequest(http.MethodPost, "/api/videos/"+ratingTestVideoID+"/rating", bytes.NewReader(bodyBytes))
	req = authRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var resp handler.RatingResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if resp.AverageRating != 4.0 {
		t.Errorf("AverageRating: got %v, want 4.0", resp.AverageRating)
	}
	if resp.MyRating == nil || *resp.MyRating != 4 {
		t.Errorf("MyRating: got %v, want 4", resp.MyRating)
	}
}

func TestRatingHandler_POST_UserNotFound_Returns404(t *testing.T) {
	store := &stubRatingStore{}
	users := &stubRatingUserProvider{user: nil}
	h := handler.NewRatingHandler(store, users)

	bodyBytes, _ := json.Marshal(map[string]int{"stars": 3})
	req := httptest.NewRequest(http.MethodPost, "/api/videos/"+ratingTestVideoID+"/rating", bytes.NewReader(bodyBytes))
	req = authRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

func TestRatingHandler_POST_UserProviderError_Returns500(t *testing.T) {
	store := &stubRatingStore{}
	users := &stubRatingUserProvider{userErr: errors.New("db error")}
	h := handler.NewRatingHandler(store, users)

	bodyBytes, _ := json.Marshal(map[string]int{"stars": 3})
	req := httptest.NewRequest(http.MethodPost, "/api/videos/"+ratingTestVideoID+"/rating", bytes.NewReader(bodyBytes))
	req = authRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestRatingHandler_POST_UpsertError_Returns500(t *testing.T) {
	store := &stubRatingStore{upsertErr: errors.New("upsert failed")}
	user := &repository.User{ID: "user-1", FirebaseUID: "firebase-uid-1", Username: "alice"}
	users := &stubRatingUserProvider{user: user}
	h := handler.NewRatingHandler(store, users)

	bodyBytes, _ := json.Marshal(map[string]int{"stars": 3})
	req := httptest.NewRequest(http.MethodPost, "/api/videos/"+ratingTestVideoID+"/rating", bytes.NewReader(bodyBytes))
	req = authRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestRatingHandler_POST_InvalidJSON_Returns400(t *testing.T) {
	store := &stubRatingStore{}
	user := &repository.User{ID: "user-1"}
	users := &stubRatingUserProvider{user: user}
	h := handler.NewRatingHandler(store, users)

	req := httptest.NewRequest(http.MethodPost, "/api/videos/"+ratingTestVideoID+"/rating", strings.NewReader("not-json"))
	req = authRequest(req)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestRatingHandler_POST_AllValidStarValues(t *testing.T) {
	for _, stars := range []int{1, 2, 3, 4, 5} {
		s := stars
		myRating := s
		store := &stubRatingStore{summary: makeRatingSummary(float64(s), 1, &myRating)}
		user := &repository.User{ID: "user-1"}
		users := &stubRatingUserProvider{user: user}
		h := handler.NewRatingHandler(store, users)

		bodyBytes, _ := json.Marshal(map[string]int{"stars": stars})
		req := httptest.NewRequest(http.MethodPost, "/api/videos/"+ratingTestVideoID+"/rating", bytes.NewReader(bodyBytes))
		req = authRequest(req)
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)

		if rec.Code != http.StatusOK {
			t.Errorf("stars=%d: expected 200, got %d", stars, rec.Code)
		}
	}
}

func TestRatingHandler_GET_ContentType_IsJSON(t *testing.T) {
	store := &stubRatingStore{summary: makeRatingSummary(0, 0, nil)}
	users := &stubRatingUserProvider{}
	h := handler.NewRatingHandler(store, users)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+ratingTestVideoID+"/rating", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type: got %q, want application/json", ct)
	}
}
