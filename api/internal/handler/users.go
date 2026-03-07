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

// PublicUserProvider is the data-access interface used by GET /api/users/:username.
// Satisfied by *repository.UserRepository and allows tests to inject a stub.
type PublicUserProvider interface {
	GetByUsername(ctx context.Context, username string) (*repository.User, error)
	GetVideosByUserID(ctx context.Context, userID string) ([]repository.Video, error)
}

// VideoSummary is the JSON representation of a video in the profile response.
type VideoSummary struct {
	ID           string    `json:"id"`
	Title        string    `json:"title"`
	ThumbnailURL *string   `json:"thumbnail_url"`
	ViewCount    int64     `json:"view_count"`
	CreatedAt    time.Time `json:"created_at"`
}

// UserProfileResponse is the JSON body returned by GET /api/users/:username.
type UserProfileResponse struct {
	Username  string         `json:"username"`
	AvatarURL *string        `json:"avatar_url"`
	Videos    []VideoSummary `json:"videos"`
}

// usernameRE matches valid usernames: alphanumerics, underscores, and hyphens.
// Hyphens are required because usernames are derived from email prefixes via
// emailPrefix() (e.g. "ci-test@example.com" → "ci-test"), and email local
// parts can legally contain hyphens.  The deduplication logic in migration
// 0005 appends numeric suffixes with underscores (e.g. "ci-test_2").
var usernameRE = regexp.MustCompile(`^[a-zA-Z0-9_-]+$`)

// isValidUsername returns true when username is non-empty, at most 100
// characters (matching the users.username VARCHAR(100) column), and contains
// only alphanumeric characters and underscores.
func isValidUsername(username string) bool {
	return len(username) > 0 && len(username) <= 100 && usernameRE.MatchString(username)
}

// NewUsersHandler returns an http.Handler for GET /api/users/:username.
// It resolves the username path segment, fetches the user and their ready
// videos, and returns the public profile JSON.  No authentication is required.
//
// NOTE: This endpoint requires no authentication and performs two DB queries per
// request.  Rate limiting is currently deferred to infrastructure-level controls
// (Cloud Run concurrency limits + Cloud Armor).  Username enumeration via
// 200/404 responses is inherent to the feature.
func NewUsersHandler(users PublicUserProvider) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", "GET")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		// Extract :username from the path.  The route is registered as
		// "/api/users/" so everything after that prefix is the username.
		username := strings.TrimPrefix(r.URL.Path, "/api/users/")
		username = strings.TrimRight(username, "/")
		if username == "" {
			writeJSONError(w, "username is required", http.StatusBadRequest)
			return
		}

		// Validate username format and length before hitting the database.
		// This prevents oversized inputs from causing DB errors and rejects
		// path segments that could not be valid usernames (e.g. "../..").
		if !isValidUsername(username) {
			writeJSONError(w, "invalid username", http.StatusBadRequest)
			return
		}

		user, err := users.GetByUsername(r.Context(), username)
		if err != nil {
			log.Printf("GET /api/users/%s: get user: %v", username, err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}
		if user == nil {
			writeJSONError(w, "user not found", http.StatusNotFound)
			return
		}

		rawVideos, err := users.GetVideosByUserID(r.Context(), user.ID)
		if err != nil {
			log.Printf("GET /api/users/%s: get videos: %v", username, err)
			writeJSONError(w, "internal server error", http.StatusInternalServerError)
			return
		}

		summaries := make([]VideoSummary, len(rawVideos))
		for i, v := range rawVideos {
			summaries[i] = VideoSummary{
				ID:           v.ID,
				Title:        v.Title,
				ThumbnailURL: v.ThumbnailURL,
				ViewCount:    v.ViewCount,
				CreatedAt:    v.CreatedAt,
			}
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(UserProfileResponse{
			Username:  user.Username,
			AvatarURL: user.AvatarURL,
			Videos:    summaries,
		})
	})
}
