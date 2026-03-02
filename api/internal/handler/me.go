// Package handler contains HTTP handler constructors.
package handler

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"

	"github.com/ai-teammate/mytube/api/internal/middleware"
	"github.com/ai-teammate/mytube/api/internal/repository"
)

// writeJSONError writes a JSON-encoded error response with the correct
// Content-Type header. This avoids the text/plain MIME type set by http.Error.
func writeJSONError(w http.ResponseWriter, msg string, status int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = fmt.Fprintf(w, `{"error":%q}`, msg)
}

// UserProvider is the data-access interface used by the /api/me handlers.
// Satisfied by *repository.UserRepository and allows tests to inject a stub.
type UserProvider interface {
	Upsert(ctx context.Context, firebaseUID, email, pictureURL string) (*repository.User, error)
	UpdateProfile(ctx context.Context, firebaseUID, username string, avatarURL *string) (*repository.User, error)
}

// MeResponse is the JSON body returned by GET /api/me and PUT /api/me.
type MeResponse struct {
	ID        string  `json:"id"`
	Username  string  `json:"username"`
	AvatarURL *string `json:"avatar_url"`
}

// UpdateMeRequest is the JSON body accepted by PUT /api/me.
type UpdateMeRequest struct {
	Username  string  `json:"username"`
	AvatarURL *string `json:"avatar_url"`
}

// NewMeHandler returns an http.Handler that dispatches GET and PUT requests
// to the corresponding sub-handlers for /api/me.
func NewMeHandler(users UserProvider) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			getMeHandler(users, w, r)
		case http.MethodPut:
			putMeHandler(users, w, r)
		default:
			w.Header().Set("Allow", "GET, PUT")
			writeJSONError(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	})
}

// getMeHandler handles GET /api/me.
// It reads verified claims from the request context (injected by RequireAuth),
// upserts the user row on first call, and returns the user profile.
func getMeHandler(users UserProvider, w http.ResponseWriter, r *http.Request) {
	claims := middleware.ClaimsFromContext(r.Context())
	if claims == nil {
		writeJSONError(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	user, err := users.Upsert(r.Context(), claims.UID, claims.Email, claims.Picture)
	if err != nil {
		log.Printf("GET /api/me: provision user %s: %v", claims.UID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}

	if user == nil {
		// Provisioning succeeded but the row still isn't visible — treat as
		// a transient failure rather than a 404 to avoid confusing clients.
		log.Printf("GET /api/me: user row not found after upsert for uid %s", claims.UID)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(MeResponse{
		ID:        user.ID,
		Username:  user.Username,
		AvatarURL: user.AvatarURL,
	})
}

// putMeHandler handles PUT /api/me.
// It reads verified claims from the request context (injected by RequireAuth),
// decodes a JSON body containing username and avatar_url, validates the input,
// updates the user row, and returns the updated profile.
func putMeHandler(users UserProvider, w http.ResponseWriter, r *http.Request) {
	claims := middleware.ClaimsFromContext(r.Context())
	if claims == nil {
		writeJSONError(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	var req UpdateMeRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSONError(w, "invalid request body", http.StatusBadRequest)
		return
	}

	req.Username = strings.TrimSpace(req.Username)
	if req.Username == "" {
		writeJSONError(w, "username is required", http.StatusUnprocessableEntity)
		return
	}

	user, err := users.UpdateProfile(r.Context(), claims.UID, req.Username, req.AvatarURL)
	if err != nil {
		log.Printf("PUT /api/me: update profile %s: %v", claims.UID, err)
		writeJSONError(w, "internal server error", http.StatusInternalServerError)
		return
	}

	if user == nil {
		// The user row doesn't exist — should not normally occur after login,
		// but return 404 rather than a misleading 500.
		writeJSONError(w, "user not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(MeResponse{
		ID:        user.ID,
		Username:  user.Username,
		AvatarURL: user.AvatarURL,
	})
}
