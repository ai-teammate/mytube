package handler

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"time"

	"github.com/ai-teammate/mytube/api/internal/middleware"
	"github.com/ai-teammate/mytube/api/internal/repository"
)

// DashboardVideoProvider is the data-access interface used by GET /api/me/videos.
// Satisfied by *repository.VideoRepository and allows tests to inject a stub.
type DashboardVideoProvider interface {
	GetVideosByUploaderID(ctx context.Context, uploaderID string) ([]repository.DashboardVideo, error)
}

// DashboardVideoListItem is the JSON representation of a single video in the
// dashboard list response.
type DashboardVideoListItem struct {
	ID           string    `json:"id"`
	Title        string    `json:"title"`
	Status       string    `json:"status"`
	ThumbnailURL *string   `json:"thumbnail_url"`
	ViewCount    int64     `json:"view_count"`
	CreatedAt    time.Time `json:"created_at"`
	Description  *string   `json:"description"`
	CategoryID   *int      `json:"category_id"`
	Tags         []string  `json:"tags"`
}

// NewMeVideosHandler returns an http.Handler for GET /api/me/videos.
// It requires authentication (claims must be present in the request context).
func NewMeVideosHandler(videos DashboardVideoProvider, users UserIDProvider) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", "GET")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		claims := middleware.ClaimsFromContext(r.Context())
		if claims == nil {
			writeJSONError(w, "unauthorized", http.StatusUnauthorized)
			return
		}

		// Resolve internal user ID from Firebase UID.
		user, err := users.GetByFirebaseUID(r.Context(), claims.UID)
		if err != nil {
			log.Printf("GET /api/me/videos: get user %s: %v", claims.UID, err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}
		if user == nil {
			writeJSONError(w, "user not found", http.StatusNotFound)
			return
		}

		dbVideos, err := videos.GetVideosByUploaderID(r.Context(), user.ID)
		if err != nil {
			log.Printf("GET /api/me/videos: get videos for user %s: %v", user.ID, err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}

		items := make([]DashboardVideoListItem, len(dbVideos))
		for i, v := range dbVideos {
			items[i] = DashboardVideoListItem{
				ID:           v.ID,
				Title:        v.Title,
				Status:       v.Status,
				ThumbnailURL: v.ThumbnailURL,
				ViewCount:    v.ViewCount,
				CreatedAt:    v.CreatedAt,
				Description:  v.Description,
				CategoryID:   v.CategoryID,
				Tags:         v.Tags,
			}
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(items)
	})
}
