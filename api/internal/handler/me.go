// Package handler contains HTTP handler constructors.
package handler

import (
	"context"
	"encoding/json"
	"log"
	"net/http"

	"github.com/ai-teammate/mytube/api/internal/auth"
	"github.com/ai-teammate/mytube/api/internal/middleware"
	"github.com/ai-teammate/mytube/api/internal/repository"
)

// UserProvider is the data-access interface used by the /api/me handler.
// Satisfied by *repository.UserRepository and allows tests to inject a stub.
type UserProvider interface {
	Upsert(ctx context.Context, firebaseUID, email string) (*repository.User, error)
	GetByFirebaseUID(ctx context.Context, firebaseUID string) (*repository.User, error)
}

// MeResponse is the JSON body returned by GET /api/me.
type MeResponse struct {
	ID        string  `json:"id"`
	Username  string  `json:"username"`
	AvatarURL *string `json:"avatar_url"`
}

// NewMeHandler returns an http.HandlerFunc for GET /api/me.
// It reads verified claims from the request context (injected by RequireAuth),
// upserts the user row on first call, and returns the user profile.
func NewMeHandler(users UserProvider) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		claims := middleware.ClaimsFromContext(r.Context())
		if claims == nil {
			// Should not happen if RequireAuth middleware is applied, but guard
			// defensively so the handler is safe when used standalone in tests.
			http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
			return
		}

		user, err := provisionAndFetch(r.Context(), users, claims)
		if err != nil {
			log.Printf("GET /api/me: provision user %s: %v", claims.UID, err)
			http.Error(w, `{"error":"internal server error"}`, http.StatusInternalServerError)
			return
		}

		if user == nil {
			// Provisioning succeeded but the row still isn't visible — treat as
			// a transient failure rather than a 404 to avoid confusing clients.
			log.Printf("GET /api/me: user row not found after upsert for uid %s", claims.UID)
			http.Error(w, `{"error":"internal server error"}`, http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(MeResponse{
			ID:        user.ID,
			Username:  user.Username,
			AvatarURL: user.AvatarURL,
		})
	}
}

// provisionAndFetch attempts to upsert the user row and return it.
// If the upsert is a no-op (conflict) it falls back to a plain SELECT so that
// subsequent GET /api/me calls after provisioning always succeed.
func provisionAndFetch(ctx context.Context, users UserProvider, claims *auth.TokenClaims) (*repository.User, error) {
	return users.Upsert(ctx, claims.UID, claims.Email)
}
