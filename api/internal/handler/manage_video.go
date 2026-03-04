package handler

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"strings"
	"unicode/utf8"

	"github.com/ai-teammate/mytube/api/internal/middleware"
	"github.com/ai-teammate/mytube/api/internal/repository"
)

// VideoManager is the data-access interface used by PUT /api/videos/:id and
// DELETE /api/videos/:id.
// Satisfied by *repository.VideoRepository and allows tests to inject a stub.
type VideoManager interface {
	Update(ctx context.Context, videoID string, uploaderID string, p repository.UpdateVideoParams) (*repository.VideoDetail, error)
	SoftDelete(ctx context.Context, videoID string, uploaderID string) (bool, error)
}

// UpdateVideoRequest is the JSON body accepted by PUT /api/videos/:id.
type UpdateVideoRequest struct {
	Title       string   `json:"title"`
	Description string   `json:"description"`
	CategoryID  *int     `json:"category_id"`
	Tags        []string `json:"tags"`
}

// UpdateVideoResponse is the JSON body returned by PUT /api/videos/:id.
type UpdateVideoResponse struct {
	ID           string       `json:"id"`
	Title        string       `json:"title"`
	Description  *string      `json:"description"`
	CategoryID   *int         `json:"category_id"`
	Status       string       `json:"status"`
	ThumbnailURL *string      `json:"thumbnail_url"`
	ViewCount    int64        `json:"view_count"`
	Tags         []string     `json:"tags"`
	Uploader     UploaderInfo `json:"uploader"`
}

// NewManageVideoHandler returns an http.Handler for PUT and DELETE /api/videos/:id.
// It dispatches to putVideoHandler or deleteVideoHandler based on the HTTP method.
// The GET method is delegated to the provided VideoProvider (existing watch handler logic).
// cdnBaseURL is forwarded to the GET handler for CDN URL rewriting.
func NewManageVideoHandler(videos VideoProvider, manager VideoManager, users UserIDProvider, cdnBaseURL string) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			// Delegate to the existing GET handler logic.
			NewVideoHandler(videos, cdnBaseURL).ServeHTTP(w, r)
		case http.MethodPut:
			putVideoHandler(manager, users, w, r)
		case http.MethodDelete:
			deleteVideoHandler(manager, users, w, r)
		default:
			w.Header().Set("Allow", "GET, PUT, DELETE")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	})
}

// putVideoHandler handles PUT /api/videos/:id.
func putVideoHandler(manager VideoManager, users UserIDProvider, w http.ResponseWriter, r *http.Request) {
	claims := middleware.ClaimsFromContext(r.Context())
	if claims == nil {
		writeJSONError(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	videoID := strings.TrimPrefix(r.URL.Path, "/api/videos/")
	videoID = strings.TrimRight(videoID, "/")
	if videoID == "" || !isValidUUID(videoID) {
		writeJSONError(w, "invalid video id", http.StatusBadRequest)
		return
	}

	// Resolve the caller's internal user ID.
	user, err := users.GetByFirebaseUID(r.Context(), claims.UID)
	if err != nil {
		log.Printf("PUT /api/videos/%s: get user %s: %v", videoID, claims.UID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}
	if user == nil {
		writeJSONError(w, "user not found", http.StatusNotFound)
		return
	}

	var req UpdateVideoRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSONError(w, "invalid request body", http.StatusBadRequest)
		return
	}

	req.Title = strings.TrimSpace(req.Title)
	if req.Title == "" {
		writeJSONError(w, "title is required", http.StatusUnprocessableEntity)
		return
	}
	if utf8.RuneCountInString(req.Title) > maxTitleLength {
		writeJSONError(w, fmt.Sprintf("title must be at most %d characters", maxTitleLength), http.StatusUnprocessableEntity)
		return
	}

	tags := sanitiseTags(req.Tags)
	if len(tags) > maxTags {
		writeJSONError(w, fmt.Sprintf("too many tags; maximum is %d", maxTags), http.StatusUnprocessableEntity)
		return
	}
	for _, tag := range tags {
		if utf8.RuneCountInString(tag) > maxTagLength {
			writeJSONError(w, fmt.Sprintf("tag %q exceeds maximum length of %d characters", tag, maxTagLength), http.StatusUnprocessableEntity)
			return
		}
	}

	var desc *string
	if d := strings.TrimSpace(req.Description); d != "" {
		desc = &d
	}

	// Ownership is enforced atomically inside Update via the WHERE clause.
	updated, err := manager.Update(r.Context(), videoID, user.ID, repository.UpdateVideoParams{
		Title:       req.Title,
		Description: desc,
		CategoryID:  req.CategoryID,
		Tags:        tags,
	})
	if err != nil {
		if errors.Is(err, repository.ErrForbidden) {
			writeJSONError(w, "forbidden", http.StatusForbidden)
			return
		}
		if errors.Is(err, repository.ErrNotFound) {
			writeJSONError(w, "video not found", http.StatusNotFound)
			return
		}
		log.Printf("PUT /api/videos/%s: update: %v", videoID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}

	// Use the validated tags slice directly — no extra DB round-trip needed.
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(UpdateVideoResponse{
		ID:           updated.ID,
		Title:        updated.Title,
		Description:  updated.Description,
		CategoryID:   updated.CategoryID,
		Status:       updated.Status,
		ThumbnailURL: updated.ThumbnailURL,
		ViewCount:    updated.ViewCount,
		Tags:         tags,
		Uploader: UploaderInfo{
			Username:  updated.UploaderUsername,
			AvatarURL: updated.UploaderAvatarURL,
		},
	})
}

// deleteVideoHandler handles DELETE /api/videos/:id.
func deleteVideoHandler(manager VideoManager, users UserIDProvider, w http.ResponseWriter, r *http.Request) {
	claims := middleware.ClaimsFromContext(r.Context())
	if claims == nil {
		writeJSONError(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	videoID := strings.TrimPrefix(r.URL.Path, "/api/videos/")
	videoID = strings.TrimRight(videoID, "/")
	if videoID == "" || !isValidUUID(videoID) {
		writeJSONError(w, "invalid video id", http.StatusBadRequest)
		return
	}

	// Resolve the caller's internal user ID.
	user, err := users.GetByFirebaseUID(r.Context(), claims.UID)
	if err != nil {
		log.Printf("DELETE /api/videos/%s: get user %s: %v", videoID, claims.UID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}
	if user == nil {
		writeJSONError(w, "user not found", http.StatusNotFound)
		return
	}

	deleted, err := manager.SoftDelete(r.Context(), videoID, user.ID)
	if errors.Is(err, repository.ErrForbidden) {
		writeJSONError(w, "forbidden", http.StatusForbidden)
		return
	}
	if err != nil {
		log.Printf("DELETE /api/videos/%s: soft delete: %v", videoID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}
	if !deleted {
		writeJSONError(w, "video not found", http.StatusNotFound)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}
