package handler

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"time"

	"github.com/ai-teammate/mytube/api/internal/repository"
)

// RecommendationProvider is the data-access interface used by the recommendations handler.
// Satisfied by *repository.VideoRepository and allows tests to inject a stub.
type RecommendationProvider interface {
	GetRecommendations(ctx context.Context, videoID string, limit int) ([]repository.RecommendationVideo, error)
}

// RecommendationItem is a single video in the recommendations JSON response.
type RecommendationItem struct {
	ID               string    `json:"id"`
	Title            string    `json:"title"`
	ThumbnailURL     *string   `json:"thumbnail_url"`
	ViewCount        int64     `json:"view_count"`
	UploaderUsername string    `json:"uploader_username"`
	CreatedAt        time.Time `json:"created_at"`
}

// RecommendationsResponse is the JSON body returned by GET /api/videos/{id}/recommendations.
type RecommendationsResponse struct {
	Recommendations []RecommendationItem `json:"recommendations"`
}

const recommendationsLimit = 8

// NewRecommendationsHandler returns an http.Handler for GET /api/videos/{id}/recommendations.
// The handler returns up to 8 videos that share the same category or tags as the
// given video, ordered by view_count DESC, created_at DESC.
// If fewer than 2 recommendations are found the response contains an empty slice.
func NewRecommendationsHandler(videos RecommendationProvider) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", "GET")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		videoID := r.PathValue("id")
		if videoID == "" {
			writeJSONError(w, "video id is required", http.StatusBadRequest)
			return
		}

		if !isValidUUID(videoID) {
			writeJSONError(w, "invalid video id", http.StatusBadRequest)
			return
		}

		recs, err := videos.GetRecommendations(r.Context(), videoID, recommendationsLimit)
		if err != nil {
			log.Printf("GET /api/videos/%s/recommendations: %v", videoID, err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}

		items := make([]RecommendationItem, 0, len(recs))
		for _, v := range recs {
			items = append(items, RecommendationItem{
				ID:               v.ID,
				Title:            v.Title,
				ThumbnailURL:     v.ThumbnailURL,
				ViewCount:        v.ViewCount,
				UploaderUsername: v.UploaderUsername,
				CreatedAt:        v.CreatedAt,
			})
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(RecommendationsResponse{Recommendations: items})
	})
}
