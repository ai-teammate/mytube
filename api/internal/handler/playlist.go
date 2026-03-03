package handler

import (
	"context"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/ai-teammate/mytube/api/internal/middleware"
	"github.com/ai-teammate/mytube/api/internal/repository"
)

// ─── Interfaces ───────────────────────────────────────────────────────────────

// PlaylistStore is the data-access interface used by the playlist handlers.
// Satisfied by *repository.PlaylistRepository and allows tests to inject a stub.
type PlaylistStore interface {
	Create(ctx context.Context, ownerID, title string) (*repository.PlaylistSummary, error)
	GetByID(ctx context.Context, playlistID string) (*repository.PlaylistDetail, error)
	ListByOwnerID(ctx context.Context, ownerID string) ([]repository.PlaylistSummary, error)
	ListByOwnerUsername(ctx context.Context, username string) ([]repository.PlaylistSummary, error)
	UpdateTitle(ctx context.Context, playlistID, ownerID, title string) (*repository.PlaylistSummary, error)
	Delete(ctx context.Context, playlistID, ownerID string) (bool, error)
	AddVideo(ctx context.Context, playlistID, ownerID, videoID string) (bool, error)
	RemoveVideo(ctx context.Context, playlistID, ownerID, videoID string) (bool, error)
}

// PlaylistUserProvider resolves the internal user record for the authenticated caller.
// Satisfied by *repository.UserRepository and allows tests to inject a stub.
type PlaylistUserProvider interface {
	GetByFirebaseUID(ctx context.Context, firebaseUID string) (*repository.User, error)
}

// ─── Response types ───────────────────────────────────────────────────────────

// PlaylistSummaryResponse is the JSON representation of a playlist in list endpoints.
type PlaylistSummaryResponse struct {
	ID            string    `json:"id"`
	Title         string    `json:"title"`
	OwnerUsername string    `json:"owner_username"`
	CreatedAt     time.Time `json:"created_at"`
}

// PlaylistVideoResponse is the JSON representation of a video inside a playlist.
type PlaylistVideoResponse struct {
	ID           string  `json:"id"`
	Title        string  `json:"title"`
	ThumbnailURL *string `json:"thumbnail_url"`
	Position     int     `json:"position"`
}

// PlaylistDetailResponse is the JSON representation of a full playlist with videos.
type PlaylistDetailResponse struct {
	ID            string                  `json:"id"`
	Title         string                  `json:"title"`
	OwnerUsername string                  `json:"owner_username"`
	Videos        []PlaylistVideoResponse `json:"videos"`
}

// ─── Request types ────────────────────────────────────────────────────────────

// CreatePlaylistRequest is the JSON body accepted by POST /api/playlists.
type CreatePlaylistRequest struct {
	Title string `json:"title"`
}

// UpdatePlaylistRequest is the JSON body accepted by PUT /api/playlists/:id.
type UpdatePlaylistRequest struct {
	Title string `json:"title"`
}

// AddVideoToPlaylistRequest is the JSON body accepted by POST /api/playlists/:id/videos.
type AddVideoToPlaylistRequest struct {
	VideoID string `json:"video_id"`
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

// extractPlaylistID extracts the playlist UUID from /api/playlists/<id>[/...].
func extractPlaylistID(path string) string {
	path = strings.TrimPrefix(path, "/api/playlists/")
	// Take only the first path segment (before any slash).
	if idx := strings.Index(path, "/"); idx >= 0 {
		path = path[:idx]
	}
	return strings.TrimRight(path, "/")
}

// extractVideoIDFromPlaylistPath extracts the video UUID from
// /api/playlists/<playlistID>/videos/<videoID>.
func extractVideoIDFromPlaylistPath(path string) string {
	path = strings.TrimPrefix(path, "/api/playlists/")
	// path is now "<playlistID>/videos/<videoID>"
	parts := strings.SplitN(path, "/videos/", 2)
	if len(parts) != 2 {
		return ""
	}
	return strings.TrimRight(parts[1], "/")
}

// requireUser extracts the authenticated user from context. Returns (nil, true) and
// writes a 401 if claims are missing; returns (nil, false) and writes a 404/500
// if the user row is not found.
func requireUser(store PlaylistUserProvider, w http.ResponseWriter, r *http.Request) (*repository.User, bool) {
	claims := middleware.ClaimsFromContext(r.Context())
	if claims == nil {
		writeJSONError(w, "unauthorized", http.StatusUnauthorized)
		return nil, false
	}
	user, err := store.GetByFirebaseUID(r.Context(), claims.UID)
	if err != nil {
		log.Printf("playlist handler: get user %s: %v", claims.UID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return nil, false
	}
	if user == nil {
		writeJSONError(w, "user not found", http.StatusNotFound)
		return nil, false
	}
	return user, true
}

func mapSummary(p repository.PlaylistSummary) PlaylistSummaryResponse {
	return PlaylistSummaryResponse{
		ID:            p.ID,
		Title:         p.Title,
		OwnerUsername: p.OwnerUsername,
		CreatedAt:     p.CreatedAt,
	}
}

// ─── POST /api/playlists ──────────────────────────────────────────────────────

// NewCreatePlaylistHandler returns an http.Handler for POST /api/playlists.
// Requires authentication.
func NewCreatePlaylistHandler(playlists PlaylistStore, users PlaylistUserProvider) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.Header().Set("Allow", "POST")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		user, ok := requireUser(users, w, r)
		if !ok {
			return
		}

		var req CreatePlaylistRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSONError(w, "invalid request body", http.StatusBadRequest)
			return
		}

		req.Title = strings.TrimSpace(req.Title)
		if req.Title == "" {
			writeJSONError(w, "title is required", http.StatusUnprocessableEntity)
			return
		}

		playlist, err := playlists.Create(r.Context(), user.ID, req.Title)
		if err != nil {
			log.Printf("POST /api/playlists: create: %v", err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		_ = json.NewEncoder(w).Encode(mapSummary(*playlist))
	})
}

// ─── GET /api/me/playlists ────────────────────────────────────────────────────

// NewMePlaylistsHandler returns an http.Handler for GET /api/me/playlists.
// Requires authentication.
func NewMePlaylistsHandler(playlists PlaylistStore, users PlaylistUserProvider) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", "GET")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		user, ok := requireUser(users, w, r)
		if !ok {
			return
		}

		list, err := playlists.ListByOwnerID(r.Context(), user.ID)
		if err != nil {
			log.Printf("GET /api/me/playlists: list: %v", err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}

		resp := make([]PlaylistSummaryResponse, len(list))
		for i, p := range list {
			resp[i] = mapSummary(p)
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	})
}

// ─── GET /api/users/:username/playlists ───────────────────────────────────────

// NewUserPlaylistsHandler returns an http.Handler for GET /api/users/:username/playlists.
// Public endpoint.
func NewUserPlaylistsHandler(playlists PlaylistStore) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", "GET")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		// Extract username from /api/users/<username>/playlists.
		path := strings.TrimPrefix(r.URL.Path, "/api/users/")
		path = strings.TrimSuffix(path, "/playlists")
		username := strings.TrimRight(path, "/")
		if username == "" {
			writeJSONError(w, "username is required", http.StatusBadRequest)
			return
		}

		list, err := playlists.ListByOwnerUsername(r.Context(), username)
		if err != nil {
			log.Printf("GET /api/users/%s/playlists: %v", username, err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}

		resp := make([]PlaylistSummaryResponse, len(list))
		for i, p := range list {
			resp[i] = mapSummary(p)
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	})
}

// ─── GET|PUT|DELETE /api/playlists/:id ───────────────────────────────────────

// NewPlaylistByIDHandler returns an http.Handler for:
//   - GET    /api/playlists/:id  (public)
//   - PUT    /api/playlists/:id  (owner only, auth required)
//   - DELETE /api/playlists/:id  (owner only, auth required)
func NewPlaylistByIDHandler(playlists PlaylistStore, users PlaylistUserProvider) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			getPlaylistHandler(playlists, w, r)
		case http.MethodPut:
			putPlaylistHandler(playlists, users, w, r)
		case http.MethodDelete:
			deletePlaylistHandler(playlists, users, w, r)
		default:
			w.Header().Set("Allow", "GET, PUT, DELETE")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	})
}

func getPlaylistHandler(playlists PlaylistStore, w http.ResponseWriter, r *http.Request) {
	playlistID := extractPlaylistID(r.URL.Path)
	if playlistID == "" || !isValidUUID(playlistID) {
		writeJSONError(w, "invalid playlist id", http.StatusBadRequest)
		return
	}

	playlist, err := playlists.GetByID(r.Context(), playlistID)
	if err != nil {
		log.Printf("GET /api/playlists/%s: %v", playlistID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}
	if playlist == nil {
		writeJSONError(w, "playlist not found", http.StatusNotFound)
		return
	}

	videos := make([]PlaylistVideoResponse, len(playlist.Videos))
	for i, v := range playlist.Videos {
		videos[i] = PlaylistVideoResponse{
			ID:           v.ID,
			Title:        v.Title,
			ThumbnailURL: v.ThumbnailURL,
			Position:     v.Position,
		}
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(PlaylistDetailResponse{
		ID:            playlist.ID,
		Title:         playlist.Title,
		OwnerUsername: playlist.OwnerUsername,
		Videos:        videos,
	})
}

func putPlaylistHandler(playlists PlaylistStore, users PlaylistUserProvider, w http.ResponseWriter, r *http.Request) {
	playlistID := extractPlaylistID(r.URL.Path)
	if playlistID == "" || !isValidUUID(playlistID) {
		writeJSONError(w, "invalid playlist id", http.StatusBadRequest)
		return
	}

	user, ok := requireUser(users, w, r)
	if !ok {
		return
	}

	var req UpdatePlaylistRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSONError(w, "invalid request body", http.StatusBadRequest)
		return
	}

	req.Title = strings.TrimSpace(req.Title)
	if req.Title == "" {
		writeJSONError(w, "title is required", http.StatusUnprocessableEntity)
		return
	}

	updated, err := playlists.UpdateTitle(r.Context(), playlistID, user.ID, req.Title)
	if err != nil {
		log.Printf("PUT /api/playlists/%s: %v", playlistID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}
	if updated == nil {
		writeJSONError(w, "playlist not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(mapSummary(*updated))
}

func deletePlaylistHandler(playlists PlaylistStore, users PlaylistUserProvider, w http.ResponseWriter, r *http.Request) {
	playlistID := extractPlaylistID(r.URL.Path)
	if playlistID == "" || !isValidUUID(playlistID) {
		writeJSONError(w, "invalid playlist id", http.StatusBadRequest)
		return
	}

	user, ok := requireUser(users, w, r)
	if !ok {
		return
	}

	deleted, err := playlists.Delete(r.Context(), playlistID, user.ID)
	if err != nil {
		if errors.Is(err, repository.ErrForbidden) {
			writeJSONError(w, "forbidden", http.StatusForbidden)
			return
		}
		log.Printf("DELETE /api/playlists/%s: %v", playlistID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}
	if !deleted {
		writeJSONError(w, "playlist not found", http.StatusNotFound)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// ─── POST /api/playlists/:id/videos ──────────────────────────────────────────

// NewAddVideoToPlaylistHandler returns an http.Handler for POST /api/playlists/:id/videos.
// Requires authentication and ownership.
func NewAddVideoToPlaylistHandler(playlists PlaylistStore, users PlaylistUserProvider) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.Header().Set("Allow", "POST")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		playlistID := extractPlaylistID(r.URL.Path)
		if playlistID == "" || !isValidUUID(playlistID) {
			writeJSONError(w, "invalid playlist id", http.StatusBadRequest)
			return
		}

		user, ok := requireUser(users, w, r)
		if !ok {
			return
		}

		var req AddVideoToPlaylistRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSONError(w, "invalid request body", http.StatusBadRequest)
			return
		}

		req.VideoID = strings.TrimSpace(req.VideoID)
		if req.VideoID == "" || !isValidUUID(req.VideoID) {
			writeJSONError(w, "invalid video_id", http.StatusBadRequest)
			return
		}

		added, err := playlists.AddVideo(r.Context(), playlistID, user.ID, req.VideoID)
		if err != nil {
			if errors.Is(err, repository.ErrForbidden) {
				writeJSONError(w, "forbidden", http.StatusForbidden)
				return
			}
			log.Printf("POST /api/playlists/%s/videos: %v", playlistID, err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}
		if !added {
			writeJSONError(w, "playlist not found", http.StatusNotFound)
			return
		}

		w.WriteHeader(http.StatusNoContent)
	})
}

// ─── DELETE /api/playlists/:id/videos/:video_id ───────────────────────────────

// NewRemoveVideoFromPlaylistHandler returns an http.Handler for
// DELETE /api/playlists/:id/videos/:video_id. Requires authentication and ownership.
func NewRemoveVideoFromPlaylistHandler(playlists PlaylistStore, users PlaylistUserProvider) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodDelete {
			w.Header().Set("Allow", "DELETE")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		playlistID := extractPlaylistID(r.URL.Path)
		if playlistID == "" || !isValidUUID(playlistID) {
			writeJSONError(w, "invalid playlist id", http.StatusBadRequest)
			return
		}

		videoID := extractVideoIDFromPlaylistPath(r.URL.Path)
		if videoID == "" || !isValidUUID(videoID) {
			writeJSONError(w, "invalid video id", http.StatusBadRequest)
			return
		}

		user, ok := requireUser(users, w, r)
		if !ok {
			return
		}

		removed, err := playlists.RemoveVideo(r.Context(), playlistID, user.ID, videoID)
		if err != nil {
			if errors.Is(err, repository.ErrForbidden) {
				writeJSONError(w, "forbidden", http.StatusForbidden)
				return
			}
			log.Printf("DELETE /api/playlists/%s/videos/%s: %v", playlistID, videoID, err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}
		if !removed {
			writeJSONError(w, "not found", http.StatusNotFound)
			return
		}

		w.WriteHeader(http.StatusNoContent)
	})
}
