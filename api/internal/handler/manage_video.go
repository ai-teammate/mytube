package handler

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"unicode/utf8"

	"github.com/ai-teammate/mytube/api/internal/middleware"
	"github.com/ai-teammate/mytube/api/internal/repository"
	"github.com/ai-teammate/mytube/api/internal/storage"
)

// VideoManager is the data-access interface used by PUT /api/videos/:id and
// DELETE /api/videos/:id.
// Satisfied by *repository.VideoRepository and allows tests to inject a stub.
type VideoManager interface {
	Update(ctx context.Context, videoID string, uploaderID string, p repository.UpdateVideoParams) (*repository.VideoDetail, error)
	SoftDelete(ctx context.Context, videoID string, uploaderID string) (bool, *repository.GCSPaths, error)
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
// deleter is used to remove GCS objects when a video is deleted; it may be nil
// (in which case GCS cleanup is skipped regardless of env vars).
func NewManageVideoHandler(videos VideoProvider, manager VideoManager, users UserIDProvider, cdnBaseURL string) http.Handler {
	deleter := storage.NewNopObjectDeleter()
	return newManageVideoHandlerWithDeleter(videos, manager, users, cdnBaseURL, deleter)
}

// NewManageVideoHandlerWithDeleter is like NewManageVideoHandler but accepts an
// explicit ObjectDeleter for GCS cleanup on video deletion. Use this in main.go
// when a real GCS client is available.
func NewManageVideoHandlerWithDeleter(videos VideoProvider, manager VideoManager, users UserIDProvider, cdnBaseURL string, deleter storage.ObjectDeleter) http.Handler {
	return newManageVideoHandlerWithDeleter(videos, manager, users, cdnBaseURL, deleter)
}

// newManageVideoHandlerWithDeleter is the injectable constructor used in tests
// and by NewManageVideoHandlerWithDeleter.
func newManageVideoHandlerWithDeleter(videos VideoProvider, manager VideoManager, users UserIDProvider, cdnBaseURL string, deleter storage.ObjectDeleter) http.Handler {
	deleteEnabled := os.Getenv("DELETE_ON_VIDEO_DELETE") != "false"
	rawBucket := os.Getenv("RAW_UPLOADS_BUCKET")
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			// Delegate to the existing GET handler logic.
			NewVideoHandler(videos, cdnBaseURL).ServeHTTP(w, r)
		case http.MethodPut:
			putVideoHandler(manager, users, w, r)
		case http.MethodDelete:
			deleteVideoHandler(manager, users, deleter, rawBucket, deleteEnabled, w, r)
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

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(UpdateVideoResponse{
		ID:           updated.ID,
		Title:        updated.Title,
		Description:  updated.Description,
		CategoryID:   updated.CategoryID,
		Status:       updated.Status,
		ThumbnailURL: updated.ThumbnailURL,
		ViewCount:    updated.ViewCount,
		Tags:         updated.Tags,
		Uploader: UploaderInfo{
			Username:  updated.UploaderUsername,
			AvatarURL: updated.UploaderAvatarURL,
		},
	})
}

// deleteVideoHandler handles DELETE /api/videos/:id.
func deleteVideoHandler(manager VideoManager, users UserIDProvider, deleter storage.ObjectDeleter, rawBucket string, deleteEnabled bool, w http.ResponseWriter, r *http.Request) {
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

	deleted, paths, err := manager.SoftDelete(r.Context(), videoID, user.ID)
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

	// Best-effort GCS cleanup; errors are logged but do not affect the HTTP response.
	if deleteEnabled && paths != nil {
		cleanupVideoGCSObjects(r.Context(), deleter, videoID, rawBucket, paths)
	}

	w.WriteHeader(http.StatusNoContent)
}

// cleanupVideoGCSObjects deletes GCS objects associated with a soft-deleted video.
// It logs errors but does not return them — cleanup is best-effort and must not
// affect the HTTP response after the DB record is already marked deleted.
//
// Safety: raw object deletion is only attempted when rawBucket is non-empty and
// the raw path does not start with "videos/" (i.e., it's an expected raw upload
// path). HLS objects are only deleted under the "videos/<videoID>/" prefix to
// prevent accidental deletion of unrelated objects.
func cleanupVideoGCSObjects(ctx context.Context, deleter storage.ObjectDeleter, videoID, rawBucket string, paths *repository.GCSPaths) {
	// Delete raw upload.
	if rawBucket != "" && paths.RawPath != nil && *paths.RawPath != "" {
		rawPath := *paths.RawPath
		if !strings.HasPrefix(rawPath, "videos/") {
			if err := deleter.DeleteObject(ctx, rawBucket, rawPath); err != nil {
				log.Printf("cleanup: delete raw gs://%s/%s: %v", rawBucket, rawPath, err)
			} else {
				log.Printf("cleanup: deleted raw gs://%s/%s", rawBucket, rawPath)
			}
		}
	}

	// Delete HLS output: parse bucket and prefix from gs:// URL.
	if paths.HLSManifestPath != nil && *paths.HLSManifestPath != "" {
		hlsBucket, hlsPrefix, ok := parseGCSPrefix(*paths.HLSManifestPath, videoID)
		if ok {
			if err := deleter.DeletePrefix(ctx, hlsBucket, hlsPrefix); err != nil {
				log.Printf("cleanup: delete HLS gs://%s/%s: %v", hlsBucket, hlsPrefix, err)
			} else {
				log.Printf("cleanup: deleted HLS prefix gs://%s/%s", hlsBucket, hlsPrefix)
			}
		}
	}
}

// parseGCSPrefix extracts the bucket name and safe object prefix from a GCS
// manifest URL of the form gs://<bucket>/videos/<videoID>/index.m3u8.
// The prefix is always restricted to "videos/<videoID>/" to prevent
// unintended deletions. Returns (bucket, prefix, true) on success.
func parseGCSPrefix(manifestURL, videoID string) (bucket, prefix string, ok bool) {
	s := strings.TrimPrefix(manifestURL, "gs://")
	if s == manifestURL {
		return "", "", false // not a gs:// URL
	}
	idx := strings.Index(s, "/")
	if idx < 0 {
		return "", "", false
	}
	bucket = s[:idx]
	// Regardless of what the stored path contains, only delete under the
	// expected prefix to guard against corrupt or crafted DB values.
	expectedPrefix := fmt.Sprintf("videos/%s/", videoID)
	return bucket, expectedPrefix, bucket != ""
}
