package handler

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"strings"

	"github.com/ai-teammate/mytube/api/internal/middleware"
	"github.com/ai-teammate/mytube/api/internal/repository"
)

// RatingStore is the data-access interface used by the rating handlers.
// Satisfied by *repository.RatingRepository and allows tests to inject a stub.
type RatingStore interface {
	UpsertRating(ctx context.Context, videoID, userID string, stars int) (*repository.RatingSummary, error)
	GetSummary(ctx context.Context, videoID string, userID *string) (*repository.RatingSummary, error)
}

// RatingUserProvider resolves the internal user record for the authenticated caller.
// Satisfied by *repository.UserRepository and allows tests to inject a stub.
type RatingUserProvider interface {
	GetByFirebaseUID(ctx context.Context, firebaseUID string) (*repository.User, error)
}

// RatingResponse is the JSON body returned by the rating endpoints.
type RatingResponse struct {
	AverageRating float64 `json:"average_rating"`
	RatingCount   int64   `json:"rating_count"`
	MyRating      *int    `json:"my_rating"`
}

// PostRatingRequest is the JSON body accepted by POST /api/videos/:id/rating.
type PostRatingRequest struct {
	Stars int `json:"stars"`
}

// NewRatingHandler returns an http.Handler that dispatches GET and POST to
// /api/videos/:id/rating.
//
// GET is unauthenticated; POST requires a valid Firebase token.
// authMiddleware wraps only the POST path.
func NewRatingHandler(ratings RatingStore, users RatingUserProvider) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Extract video ID from /api/videos/<id>/rating
		videoID := extractRatingVideoID(r.URL.Path)
		if videoID == "" || !isValidVideoID(videoID) {
			writeJSONError(w, "invalid video id", http.StatusBadRequest)
			return
		}

		switch r.Method {
		case http.MethodGet:
			getRatingHandler(ratings, videoID, w, r)
		case http.MethodPost:
			postRatingHandler(ratings, users, videoID, w, r)
		default:
			w.Header().Set("Allow", "GET, POST")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	})
}

// extractRatingVideoID parses /api/videos/<id>/rating and returns the video ID.
func extractRatingVideoID(path string) string {
	// path: /api/videos/<id>/rating
	path = strings.TrimPrefix(path, "/api/videos/")
	path = strings.TrimSuffix(path, "/rating")
	path = strings.TrimRight(path, "/")
	return path
}

// getRatingHandler handles GET /api/videos/:id/rating.
func getRatingHandler(ratings RatingStore, videoID string, w http.ResponseWriter, r *http.Request) {
	// Optionally resolve the caller's user ID for my_rating.
	var userID *string
	if claims := middleware.ClaimsFromContext(r.Context()); claims != nil {
		uid := claims.UID
		userID = &uid
	}

	summary, err := ratings.GetSummary(r.Context(), videoID, userID)
	if err != nil {
		log.Printf("GET /api/videos/%s/rating: %v", videoID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(RatingResponse{
		AverageRating: summary.AverageRating,
		RatingCount:   summary.RatingCount,
		MyRating:      summary.MyRating,
	})
}

// postRatingHandler handles POST /api/videos/:id/rating.
// Requires authentication.
func postRatingHandler(ratings RatingStore, users RatingUserProvider, videoID string, w http.ResponseWriter, r *http.Request) {
	claims := middleware.ClaimsFromContext(r.Context())
	if claims == nil {
		writeJSONError(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	var req PostRatingRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSONError(w, "invalid request body", http.StatusBadRequest)
		return
	}

	if req.Stars < 1 || req.Stars > 5 {
		writeJSONError(w, "stars must be between 1 and 5", http.StatusUnprocessableEntity)
		return
	}

	user, err := users.GetByFirebaseUID(r.Context(), claims.UID)
	if err != nil {
		log.Printf("POST /api/videos/%s/rating: get user %s: %v", videoID, claims.UID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}
	if user == nil {
		writeJSONError(w, "user not found", http.StatusNotFound)
		return
	}

	summary, err := ratings.UpsertRating(r.Context(), videoID, user.ID, req.Stars)
	if err != nil {
		log.Printf("POST /api/videos/%s/rating: upsert: %v", videoID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(RatingResponse{
		AverageRating: summary.AverageRating,
		RatingCount:   summary.RatingCount,
		MyRating:      summary.MyRating,
	})
}
