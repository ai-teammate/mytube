package handler

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"strconv"
	"time"

	"github.com/ai-teammate/mytube/api/internal/repository"
)

// SearchProvider is the data-access interface used by the search and discovery
// handlers. Satisfied by *repository.SearchRepository.
type SearchProvider interface {
	Search(ctx context.Context, p repository.SearchParams) ([]repository.SearchVideo, error)
	GetRecent(ctx context.Context, limit int) ([]repository.SearchVideo, error)
	GetPopular(ctx context.Context, limit int) ([]repository.SearchVideo, error)
	GetAllCategories(ctx context.Context) ([]repository.Category, error)
	GetByCategory(ctx context.Context, categoryID, limit, offset int) ([]repository.SearchVideo, error)
}

// VideoCard is the JSON representation of a video in search/discovery responses.
type VideoCard struct {
	ID               string    `json:"id"`
	Title            string    `json:"title"`
	ThumbnailURL     *string   `json:"thumbnail_url"`
	ViewCount        int64     `json:"view_count"`
	UploaderUsername string    `json:"uploader_username"`
	CreatedAt        time.Time `json:"created_at"`
}

// CategoryResponse is the JSON representation of a category.
type CategoryResponse struct {
	ID   int    `json:"id"`
	Name string `json:"name"`
}

// toVideoCard converts a repository.SearchVideo to a VideoCard.
func toVideoCard(v repository.SearchVideo) VideoCard {
	return VideoCard{
		ID:               v.ID,
		Title:            v.Title,
		ThumbnailURL:     v.ThumbnailURL,
		ViewCount:        v.ViewCount,
		UploaderUsername: v.UploaderUsername,
		CreatedAt:        v.CreatedAt,
	}
}

// toVideoCards converts a slice of repository.SearchVideo to VideoCard slice.
func toVideoCards(vs []repository.SearchVideo) []VideoCard {
	cards := make([]VideoCard, len(vs))
	for i, v := range vs {
		cards[i] = toVideoCard(v)
	}
	return cards
}

// parseLimit parses and clamps the "limit" query parameter.
// Returns defaultVal when the parameter is absent or invalid.
func parseLimit(r *http.Request, defaultVal, maxVal int) int {
	s := r.URL.Query().Get("limit")
	if s == "" {
		return defaultVal
	}
	v, err := strconv.Atoi(s)
	if err != nil || v <= 0 {
		return defaultVal
	}
	if v > maxVal {
		return maxVal
	}
	return v
}

// parseOffset parses the "offset" query parameter.
// Returns 0 when the parameter is absent or invalid.
func parseOffset(r *http.Request) int {
	s := r.URL.Query().Get("offset")
	if s == "" {
		return 0
	}
	v, err := strconv.Atoi(s)
	if err != nil || v < 0 {
		return 0
	}
	return v
}

// NewSearchHandler returns an http.Handler for GET /api/search.
func NewSearchHandler(search SearchProvider) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", "GET")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		q := r.URL.Query().Get("q")
		limit := parseLimit(r, 20, 100)
		offset := parseOffset(r)

		var categoryID *int
		if catStr := r.URL.Query().Get("category_id"); catStr != "" {
			id, err := strconv.Atoi(catStr)
			if err != nil || id <= 0 {
				writeJSONError(w, "invalid category_id", http.StatusBadRequest)
				return
			}
			categoryID = &id
		}

		params := repository.SearchParams{
			Query:      q,
			CategoryID: categoryID,
			Limit:      limit,
			Offset:     offset,
		}

		videos, err := search.Search(r.Context(), params)
		if err != nil {
			log.Printf("GET /api/search: %v", err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(toVideoCards(videos))
	})
}

// NewRecentVideosHandler returns an http.Handler for GET /api/videos/recent.
func NewRecentVideosHandler(search SearchProvider) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", "GET")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		limit := parseLimit(r, 20, 100)

		videos, err := search.GetRecent(r.Context(), limit)
		if err != nil {
			log.Printf("GET /api/videos/recent: %v", err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(toVideoCards(videos))
	})
}

// NewPopularVideosHandler returns an http.Handler for GET /api/videos/popular.
func NewPopularVideosHandler(search SearchProvider) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", "GET")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		limit := parseLimit(r, 20, 100)

		videos, err := search.GetPopular(r.Context(), limit)
		if err != nil {
			log.Printf("GET /api/videos/popular: %v", err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(toVideoCards(videos))
	})
}

// NewCategoriesHandler returns an http.Handler for GET /api/categories.
func NewCategoriesHandler(search SearchProvider) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", "GET")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		cats, err := search.GetAllCategories(r.Context())
		if err != nil {
			log.Printf("GET /api/categories: %v", err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}

		resp := make([]CategoryResponse, len(cats))
		for i, c := range cats {
			resp[i] = CategoryResponse{ID: c.ID, Name: c.Name}
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	})
}

// NewBrowseVideosHandler returns an http.Handler for GET /api/videos?category_id=<id>.
// It handles category-browse requests. If no category_id is provided, it returns
// a 400 bad request, as plain /api/videos without category_id is not a valid
// browse endpoint (use /api/videos/recent or /api/videos/popular instead).
func NewBrowseVideosHandler(search SearchProvider) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", "GET")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		catStr := r.URL.Query().Get("category_id")
		if catStr == "" {
			writeJSONError(w, "category_id is required", http.StatusBadRequest)
			return
		}

		categoryID, err := strconv.Atoi(catStr)
		if err != nil || categoryID <= 0 {
			writeJSONError(w, "invalid category_id", http.StatusBadRequest)
			return
		}

		limit := parseLimit(r, 20, 100)
		offset := parseOffset(r)

		videos, err := search.GetByCategory(r.Context(), categoryID, limit, offset)
		if err != nil {
			log.Printf("GET /api/videos?category_id=%d: %v", categoryID, err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(toVideoCards(videos))
	})
}
