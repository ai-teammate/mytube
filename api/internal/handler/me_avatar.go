package handler

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"

	"github.com/google/uuid"

	"github.com/ai-teammate/mytube/api/internal/middleware"
	"github.com/ai-teammate/mytube/api/internal/repository"
	"github.com/ai-teammate/mytube/api/internal/storage"
)

const (
	// maxAvatarSize is the maximum accepted avatar file size (5 MB).
	maxAvatarSize = 5 * 1024 * 1024

	// avatarFormField is the multipart/form-data field name for the avatar file.
	avatarFormField = "avatar"

	// multipartOverhead is extra headroom added to the body size limit to
	// accommodate multipart boundaries and part headers.
	multipartOverhead = 1 << 20 // 1 MB
)

// allowedAvatarMIMETypes maps accepted MIME types to their canonical file extensions.
var allowedAvatarMIMETypes = map[string]string{
	"image/jpeg": "jpg",
	"image/png":  "png",
}

// AvatarUserProvider is the data-access interface required by the avatar handlers.
type AvatarUserProvider interface {
	GetByFirebaseUID(ctx context.Context, firebaseUID string) (*repository.User, error)
	UpdateAvatarURL(ctx context.Context, firebaseUID, avatarURL string) (*repository.User, error)
	ClearAvatarURL(ctx context.Context, firebaseUID string) (*repository.User, error)
}

// AvatarUploadResponse is the JSON body returned by POST /api/me/avatar.
type AvatarUploadResponse struct {
	AvatarURL string `json:"avatar_url"`
}

// avatarUploadHandler implements POST /api/me/avatar.
type avatarUploadHandler struct {
	users      AvatarUserProvider
	uploader   storage.Uploader
	bucket     string
	cdnBaseURL string
}

// NewAvatarUploadHandler returns an http.Handler for POST /api/me/avatar.
// bucket is the GCS bucket that stores avatar objects (e.g. "mytube-hls-output").
// cdnBaseURL is the public base URL for that bucket (e.g. "https://storage.googleapis.com/mytube-hls-output").
func NewAvatarUploadHandler(users AvatarUserProvider, uploader storage.Uploader, bucket, cdnBaseURL string) http.Handler {
	return &avatarUploadHandler{
		users:      users,
		uploader:   uploader,
		bucket:     bucket,
		cdnBaseURL: cdnBaseURL,
	}
}

func (h *avatarUploadHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
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

	user, err := h.users.GetByFirebaseUID(r.Context(), claims.UID)
	if err != nil {
		log.Printf("POST /api/me/avatar: lookup user %s: %v", claims.UID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}
	if user == nil {
		writeJSONError(w, "user not found", http.StatusNotFound)
		return
	}

	// Enforce an upper bound on the request body before parsing so that
	// oversized requests are rejected before any multipart work.
	r.Body = http.MaxBytesReader(w, r.Body, maxAvatarSize+multipartOverhead)
	if err := r.ParseMultipartForm(maxAvatarSize); err != nil {
		var maxBytesErr *http.MaxBytesError
		if errors.As(err, &maxBytesErr) {
			writeJSONError(w, "file too large; maximum size is 5 MB", http.StatusRequestEntityTooLarge)
			return
		}
		writeJSONError(w, "invalid multipart form", http.StatusBadRequest)
		return
	}

	file, fileHeader, err := r.FormFile(avatarFormField)
	if err != nil {
		writeJSONError(w, `form field "avatar" is required`, http.StatusBadRequest)
		return
	}
	defer file.Close()

	// Normalise MIME type: strip parameters (e.g. "image/jpeg; charset=utf-8" → "image/jpeg").
	rawCT := fileHeader.Header.Get("Content-Type")
	mimeBase := strings.TrimSpace(strings.ToLower(strings.SplitN(rawCT, ";", 2)[0]))
	ext, ok := allowedAvatarMIMETypes[mimeBase]
	if !ok {
		writeJSONError(w, "unsupported file type; accepted types: jpeg, png", http.StatusBadRequest)
		return
	}

	// Sniff the first 512 bytes to verify the file's actual content type
	// (defence-in-depth — the multipart Content-Type header is client-controlled).
	sniffBuf := make([]byte, 512)
	n, _ := file.Read(sniffBuf)
	detectedMIME := http.DetectContentType(sniffBuf[:n])
	detectedBase := strings.TrimSpace(strings.ToLower(strings.SplitN(detectedMIME, ";", 2)[0]))
	if _, ok := allowedAvatarMIMETypes[detectedBase]; !ok {
		writeJSONError(w, "unsupported file type; accepted types: jpeg, png", http.StatusBadRequest)
		return
	}
	// Reconstruct a reader that includes the already-consumed sniff bytes.
	fileReader := io.MultiReader(bytes.NewReader(sniffBuf[:n]), file)

	// Read up to maxAvatarSize+1 bytes so we can detect files that are exactly
	// at the boundary (MaxBytesReader only triggers above maxAvatarSize+multipartOverhead).
	limited := io.LimitReader(fileReader, maxAvatarSize+1)
	data, err := io.ReadAll(limited)
	if err != nil {
		log.Printf("POST /api/me/avatar: read file for user %s: %v", claims.UID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}
	if int64(len(data)) > maxAvatarSize {
		writeJSONError(w, "file too large; maximum size is 5 MB", http.StatusRequestEntityTooLarge)
		return
	}

	objectKey := fmt.Sprintf("avatars/%s/%s.%s", user.ID, uuid.New().String(), ext)
	if err := h.uploader.Upload(r.Context(), h.bucket, objectKey, mimeBase, bytes.NewReader(data)); err != nil {
		log.Printf("POST /api/me/avatar: upload for user %s: %v", claims.UID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}

	cdnURL := strings.TrimRight(h.cdnBaseURL, "/") + "/" + objectKey
	if _, err := h.users.UpdateAvatarURL(r.Context(), claims.UID, cdnURL); err != nil {
		log.Printf("POST /api/me/avatar: update avatar_url for user %s: %v", claims.UID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(AvatarUploadResponse{AvatarURL: cdnURL})
}
