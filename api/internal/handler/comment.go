package handler

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/ai-teammate/mytube/api/internal/middleware"
	"github.com/ai-teammate/mytube/api/internal/repository"
)

const (
	// maxCommentBodyLength is the maximum allowed comment length in runes.
	maxCommentBodyLength = 2000
)

// CommentStore is the data-access interface used by the comment handlers.
// Satisfied by *repository.CommentRepository and allows tests to inject a stub.
type CommentStore interface {
	Create(ctx context.Context, p repository.CreateCommentParams) (*repository.Comment, error)
	ListByVideoID(ctx context.Context, videoID string) ([]repository.Comment, error)
	Delete(ctx context.Context, commentID, ownerID string) (bool, error)
}

// CommentUserProvider resolves the internal user record for the authenticated caller.
// Satisfied by *repository.UserRepository and allows tests to inject a stub.
type CommentUserProvider interface {
	GetByFirebaseUID(ctx context.Context, firebaseUID string) (*repository.User, error)
}

// CommentVideoChecker checks whether a video exists.
// Satisfied by *repository.VideoRepository and allows tests to inject a stub.
type CommentVideoChecker interface {
	Exists(ctx context.Context, videoID string) (bool, error)
}

// CommentAuthorInfo is the nested author field in comment responses.
type CommentAuthorInfo struct {
	Username  string  `json:"username"`
	AvatarURL *string `json:"avatar_url"`
}

// CommentResponse is the JSON representation of a comment.
type CommentResponse struct {
	ID        string            `json:"id"`
	Body      string            `json:"body"`
	Author    CommentAuthorInfo `json:"author"`
	CreatedAt time.Time         `json:"created_at"`
}

// PostCommentRequest is the JSON body accepted by POST /api/videos/:id/comments.
type PostCommentRequest struct {
	Body string `json:"body"`
}

// NewVideoCommentsHandler returns an http.Handler for:
//   - GET  /api/videos/:id/comments  (public)
//   - POST /api/videos/:id/comments  (authenticated)
func NewVideoCommentsHandler(comments CommentStore, users CommentUserProvider, videos CommentVideoChecker) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		videoID := extractCommentVideoID(r.URL.Path)
		if videoID == "" || !isValidUUID(videoID) {
			writeJSONError(w, "invalid video id", http.StatusBadRequest)
			return
		}

		switch r.Method {
		case http.MethodGet:
			// Rate-limit only the public GET endpoint to guard against enumeration
			// and DB overload. POST is authenticated and not subject to this limit.
			if !middleware.RateLimitPublicAllow(r) {
				writeJSONError(w, "rate limit exceeded", http.StatusTooManyRequests)
				return
			}
			getCommentsHandler(comments, videos, videoID, w, r)
		case http.MethodPost:
			postCommentHandler(comments, users, videos, videoID, w, r)
		default:
			w.Header().Set("Allow", "GET, POST")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	})
}

// NewDeleteCommentHandler returns an http.Handler for DELETE /api/comments/:id.
// Requires authentication; only the comment owner may delete.
func NewDeleteCommentHandler(comments CommentStore, users CommentUserProvider) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodDelete {
			w.Header().Set("Allow", "DELETE")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		commentID := strings.TrimPrefix(r.URL.Path, "/api/comments/")
		commentID = strings.TrimRight(commentID, "/")
		if commentID == "" || !isValidUUID(commentID) {
			writeJSONError(w, "invalid comment id", http.StatusBadRequest)
			return
		}

		claims := middleware.ClaimsFromContext(r.Context())
		if claims == nil {
			writeJSONError(w, "unauthorized", http.StatusUnauthorized)
			return
		}

		user, err := users.GetByFirebaseUID(r.Context(), claims.UID)
		if err != nil {
			log.Printf("DELETE /api/comments/%s: get user %s: %v", commentID, claims.UID, err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}
		if user == nil {
			writeJSONError(w, "user not found", http.StatusNotFound)
			return
		}

		deleted, err := comments.Delete(r.Context(), commentID, user.ID)
		if err != nil {
			log.Printf("DELETE /api/comments/%s: delete: %v", commentID, err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}
		if !deleted {
			writeJSONError(w, "comment not found", http.StatusNotFound)
			return
		}

		w.WriteHeader(http.StatusNoContent)
	})
}

// extractCommentVideoID parses /api/videos/<id>/comments and returns the video ID.
func extractCommentVideoID(path string) string {
	path = strings.TrimPrefix(path, "/api/videos/")
	path = strings.TrimSuffix(path, "/comments")
	path = strings.TrimRight(path, "/")
	return path
}

// checkCommentVideoExists performs a lightweight video existence check and writes a
// 404 or 500 response when appropriate. Returns false if the caller should stop.
func checkCommentVideoExists(videos CommentVideoChecker, videoID string, w http.ResponseWriter, r *http.Request) bool {
	exists, err := videos.Exists(r.Context(), videoID)
	if err != nil {
		log.Printf("check video exists %s: %v", videoID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return false
	}
	if !exists {
		writeJSONError(w, "video not found", http.StatusNotFound)
		return false
	}
	return true
}

// getCommentsHandler handles GET /api/videos/:id/comments.
func getCommentsHandler(comments CommentStore, videos CommentVideoChecker, videoID string, w http.ResponseWriter, r *http.Request) {
	if !checkCommentVideoExists(videos, videoID, w, r) {
		return
	}

	list, err := comments.ListByVideoID(r.Context(), videoID)
	if err != nil {
		log.Printf("GET /api/videos/%s/comments: %v", videoID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}

	resp := make([]CommentResponse, len(list))
	for i, c := range list {
		resp[i] = CommentResponse{
			ID:   c.ID,
			Body: c.Body,
			Author: CommentAuthorInfo{
				Username:  c.AuthorUsername,
				AvatarURL: c.AuthorAvatarURL,
			},
			CreatedAt: c.CreatedAt,
		}
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(resp)
}

// postCommentHandler handles POST /api/videos/:id/comments.
// Requires authentication.
func postCommentHandler(comments CommentStore, users CommentUserProvider, videos CommentVideoChecker, videoID string, w http.ResponseWriter, r *http.Request) {
	claims := middleware.ClaimsFromContext(r.Context())
	if claims == nil {
		writeJSONError(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	var req PostCommentRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSONError(w, "invalid request body", http.StatusBadRequest)
		return
	}

	req.Body = strings.TrimSpace(req.Body)
	if req.Body == "" {
		writeJSONError(w, "body is required", http.StatusUnprocessableEntity)
		return
	}
	if utf8.RuneCountInString(req.Body) > maxCommentBodyLength {
		writeJSONError(w, "body exceeds maximum length of 2000 characters", http.StatusUnprocessableEntity)
		return
	}

	if !checkCommentVideoExists(videos, videoID, w, r) {
		return
	}

	user, err := users.GetByFirebaseUID(r.Context(), claims.UID)
	if err != nil {
		log.Printf("POST /api/videos/%s/comments: get user %s: %v", videoID, claims.UID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}
	if user == nil {
		writeJSONError(w, "user not found", http.StatusNotFound)
		return
	}

	comment, err := comments.Create(r.Context(), repository.CreateCommentParams{
		VideoID:  videoID,
		AuthorID: user.ID,
		Body:     req.Body,
	})
	if err != nil {
		log.Printf("POST /api/videos/%s/comments: create: %v", videoID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	_ = json.NewEncoder(w).Encode(CommentResponse{
		ID:   comment.ID,
		Body: comment.Body,
		Author: CommentAuthorInfo{
			Username:  comment.AuthorUsername,
			AvatarURL: comment.AuthorAvatarURL,
		},
		CreatedAt: comment.CreatedAt,
	})
}
