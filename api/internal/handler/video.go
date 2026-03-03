package handler

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/ai-teammate/mytube/api/internal/repository"
)

// VideoProvider is the data-access interface used by GET /api/videos/:id.
// Satisfied by *repository.VideoRepository and allows tests to inject a stub.
type VideoProvider interface {
	GetByID(ctx context.Context, videoID string) (*repository.VideoDetail, error)
	IncrementViewCount(ctx context.Context, videoID string) (bool, error)
	GetTagsByVideoID(ctx context.Context, videoID string) ([]string, error)
}

// UploaderInfo is the JSON representation of the uploader in the video response.
type UploaderInfo struct {
	Username  string  `json:"username"`
	AvatarURL *string `json:"avatar_url"`
}

// VideoResponse is the JSON body returned by GET /api/videos/:id.
type VideoResponse struct {
	ID             string       `json:"id"`
	Title          string       `json:"title"`
	Description    *string      `json:"description"`
	HLSManifestURL *string      `json:"hls_manifest_url"`
	ThumbnailURL   *string      `json:"thumbnail_url"`
	ViewCount      int64        `json:"view_count"`
	CreatedAt      time.Time    `json:"created_at"`
	Status         string       `json:"status"`
	Uploader       UploaderInfo `json:"uploader"`
	Tags           []string     `json:"tags"`
}

// uuidRE matches UUID format (RFC 4122, case-insensitive):
// xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
var uuidRE = regexp.MustCompile(`(?i)^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`)

// isValidUUID returns true when id matches the UUID format (RFC 4122).
// This guards against non-UUID garbage reaching the DB for any resource whose
// primary key is a UUID (videos, comments, users, etc.).
func isValidUUID(id string) bool {
	return uuidRE.MatchString(id)
}

// cdnURLFromGCSPath converts a GCS path like gs://bucket/path/to/file
// into a CDN URL by prepending cdnBaseURL after stripping the gs://bucket prefix.
// If hlsManifestPath is nil or cdnBaseURL is empty the function returns nil.
func cdnURLFromGCSPath(hlsManifestPath *string, cdnBaseURL string) *string {
	if hlsManifestPath == nil || cdnBaseURL == "" {
		return hlsManifestPath
	}

	path := *hlsManifestPath
	// Strip gs://bucket-name prefix: find the third '/' (after "gs://")
	if strings.HasPrefix(path, "gs://") {
		withoutScheme := path[5:] // strip "gs://"
		slashIdx := strings.Index(withoutScheme, "/")
		if slashIdx >= 0 {
			objectPath := withoutScheme[slashIdx:] // includes leading "/"
			cdnURL := strings.TrimRight(cdnBaseURL, "/") + objectPath
			return &cdnURL
		}
	}
	// Fallback: return the path as-is if it doesn't look like a GCS path
	return hlsManifestPath
}

// NewVideoHandler returns an http.Handler for GET /api/videos/:id.
// cdnBaseURL is the Cloud CDN base URL used to construct the public
// hls_manifest_url from the stored GCS path (e.g. "https://cdn.example.com").
// If cdnBaseURL is empty the raw hls_manifest_path is returned as-is.
func NewVideoHandler(videos VideoProvider, cdnBaseURL string) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", "GET")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		// Extract :id from the path. The route is registered as "/api/videos/"
		// so everything after that prefix is the video ID.
		videoID := strings.TrimPrefix(r.URL.Path, "/api/videos/")
		videoID = strings.TrimRight(videoID, "/")
		if videoID == "" {
			writeJSONError(w, "video id is required", http.StatusBadRequest)
			return
		}

		if !isValidUUID(videoID) {
			writeJSONError(w, "invalid video id", http.StatusBadRequest)
			return
		}

		video, err := videos.GetByID(r.Context(), videoID)
		if err != nil {
			log.Printf("GET /api/videos/%s: get video: %v", videoID, err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}
		if video == nil {
			writeJSONError(w, "video not found", http.StatusNotFound)
			return
		}

		// Increment view count atomically; log failures but do not fail the request.
		// Use the pre-fetch count as the baseline and add 1 when the increment succeeds
		// so the response reflects the post-increment value rather than the stale count.
		viewCountInResponse := video.ViewCount
		if ok, err := videos.IncrementViewCount(r.Context(), videoID); err != nil {
			log.Printf("GET /api/videos/%s: increment view count: %v", videoID, err)
		} else if ok {
			viewCountInResponse++
		}

		tags, err := videos.GetTagsByVideoID(r.Context(), videoID)
		if err != nil {
			log.Printf("GET /api/videos/%s: get tags: %v", videoID, err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}

		hlsURL := cdnURLFromGCSPath(video.HLSManifestPath, cdnBaseURL)

		resp := VideoResponse{
			ID:             video.ID,
			Title:          video.Title,
			Description:    video.Description,
			HLSManifestURL: hlsURL,
			ThumbnailURL:   video.ThumbnailURL,
			ViewCount:      viewCountInResponse,
			CreatedAt:      video.CreatedAt,
			Status:         video.Status,
			Uploader: UploaderInfo{
				Username:  video.UploaderUsername,
				AvatarURL: video.UploaderAvatarURL,
			},
			Tags: tags,
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	})
}
