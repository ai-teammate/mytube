// Package handler contains HTTP handler constructors.
package handler

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/google/uuid"

	"github.com/ai-teammate/mytube/api/internal/middleware"
	"github.com/ai-teammate/mytube/api/internal/repository"
	"github.com/ai-teammate/mytube/api/internal/storage"
)

const (
	// signedURLTTL is how long the GCS PUT signed URL remains valid.
	signedURLTTL = 15 * time.Minute

	// maxTitleLength is the maximum allowed title length in runes (matches the
	// VARCHAR(255) column constraint).
	maxTitleLength = 255

	// maxTags is the maximum number of tags allowed per video.
	maxTags = 20

	// maxTagLength is the maximum length of a single tag in runes.
	maxTagLength = 50
)

// allowedMIMETypes lists MIME types accepted for video uploads.
var allowedMIMETypes = map[string]bool{
	"video/mp4":       true,
	"video/quicktime": true, // MOV
	"video/x-msvideo": true, // AVI
	"video/webm":      true,
}

// VideoCreator is the data-access interface used by the videos handler.
// Satisfied by *repository.VideoRepository and allows tests to inject a stub.
type VideoCreator interface {
	Create(ctx context.Context, p repository.CreateVideoParams) (*repository.VideoRecord, error)
}

// CreateVideoRequest is the JSON body accepted by POST /api/videos.
type CreateVideoRequest struct {
	Title       string   `json:"title"`
	Description string   `json:"description"`
	CategoryID  *int     `json:"category_id"`
	Tags        []string `json:"tags"`
	// MIMEType is the MIME type of the file to be uploaded.
	// The client must send the same Content-Type header when PUTting to the signed URL.
	MIMEType string `json:"mime_type"`
}

// CreateVideoResponse is the JSON body returned by POST /api/videos.
type CreateVideoResponse struct {
	VideoID   string `json:"video_id"`
	UploadURL string `json:"upload_url"`
}

// UserIDProvider retrieves the internal user ID for the authenticated caller.
// Satisfied by *repository.UserRepository and allows tests to inject a stub.
type UserIDProvider interface {
	GetByFirebaseUID(ctx context.Context, firebaseUID string) (*repository.User, error)
}

// VideosHandler handles requests to /api/videos.
type VideosHandler struct {
	videos   VideoCreator
	users    UserIDProvider
	signer   storage.Signer
	bucket   string
}

// NewVideosHandler constructs a VideosHandler.
// bucket is the GCS raw-uploads bucket name (from RAW_UPLOADS_BUCKET env var).
func NewVideosHandler(videos VideoCreator, users UserIDProvider, signer storage.Signer) http.Handler {
	bucket := os.Getenv("RAW_UPLOADS_BUCKET")
	return newVideosHandlerWithBucket(videos, users, signer, bucket)
}

// newVideosHandlerWithBucket is the injectable constructor used in tests.
func newVideosHandlerWithBucket(videos VideoCreator, users UserIDProvider, signer storage.Signer, bucket string) http.Handler {
	h := &VideosHandler{
		videos: videos,
		users:  users,
		signer: signer,
		bucket: bucket,
	}
	return http.HandlerFunc(h.serveHTTP)
}

func (h *VideosHandler) serveHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.Header().Set("Allow", "POST")
		writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	claims := middleware.ClaimsFromContext(r.Context())
	if claims == nil {
		writeJSONError(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	var req CreateVideoRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSONError(w, "invalid request body", http.StatusBadRequest)
		return
	}

	// Validate title.
	req.Title = strings.TrimSpace(req.Title)
	if req.Title == "" {
		writeJSONError(w, "title is required", http.StatusUnprocessableEntity)
		return
	}
	if utf8.RuneCountInString(req.Title) > maxTitleLength {
		writeJSONError(w, fmt.Sprintf("title must be at most %d characters", maxTitleLength), http.StatusUnprocessableEntity)
		return
	}

	// Validate MIME type.
	req.MIMEType = strings.TrimSpace(req.MIMEType)
	if req.MIMEType == "" {
		writeJSONError(w, "mime_type is required", http.StatusUnprocessableEntity)
		return
	}
	// Normalise: strip parameters (e.g. "video/mp4; codecs=avc1" → "video/mp4").
	mimeBase := strings.SplitN(req.MIMEType, ";", 2)[0]
	mimeBase = strings.TrimSpace(strings.ToLower(mimeBase))
	if !allowedMIMETypes[mimeBase] {
		writeJSONError(w, "unsupported file type; accepted types: mp4, mov, avi, webm", http.StatusUnprocessableEntity)
		return
	}

	// Resolve the internal user ID from the Firebase UID in the token.
	user, err := h.users.GetByFirebaseUID(r.Context(), claims.UID)
	if err != nil {
		log.Printf("POST /api/videos: get user %s: %v", claims.UID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}
	if user == nil {
		writeJSONError(w, "user not found", http.StatusNotFound)
		return
	}

	// Sanitise tags: trim whitespace, drop empty strings, deduplicate.
	tags := sanitiseTags(req.Tags)

	// Validate tag count and per-tag length.
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

	// Pre-generate the video ID so the GCS object path is known before the DB
	// insert. This allows us to sign the URL first and only create the DB record
	// if signing succeeds — preventing orphaned pending rows when GCS is
	// unavailable or misconfigured.
	videoID := uuid.New().String()
	objectPath := fmt.Sprintf("raw/%s/%s", user.ID, videoID)

	uploadURL, err := h.signer.SignPutURL(r.Context(), storage.SignedURLOptions{
		Bucket:      h.bucket,
		Object:      objectPath,
		ContentType: mimeBase,
		Expires:     signedURLTTL,
	})
	if err != nil {
		log.Printf("POST /api/videos: sign URL for video %s: %v", videoID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}

	videoRecord, err := h.videos.Create(r.Context(), repository.CreateVideoParams{
		ID:          videoID,
		UploaderID:  user.ID,
		Title:       req.Title,
		Description: desc,
		CategoryID:  req.CategoryID,
		Tags:        tags,
		GCSRawPath:  objectPath,
	})
	if err != nil {
		log.Printf("POST /api/videos: create video for user %s: %v", user.ID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	_ = json.NewEncoder(w).Encode(CreateVideoResponse{
		VideoID:   videoRecord.ID,
		UploadURL: uploadURL,
	})
}

// sanitiseTags trims whitespace, drops empty strings, and deduplicates tags.
func sanitiseTags(raw []string) []string {
	seen := make(map[string]bool, len(raw))
	result := make([]string, 0, len(raw))
	for _, t := range raw {
		t = strings.TrimSpace(t)
		if t == "" || seen[t] {
			continue
		}
		seen[t] = true
		result = append(result, t)
	}
	return result
}
