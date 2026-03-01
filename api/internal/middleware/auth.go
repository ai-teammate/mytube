// Package middleware provides reusable HTTP middleware constructors.
package middleware

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"

	"github.com/ai-teammate/mytube/api/internal/auth"
)

// contextKey is an unexported type used for context values set by this package
// to avoid collisions with other packages.
type contextKey int

const (
	// claimsKey is the context key under which *auth.TokenClaims is stored.
	claimsKey contextKey = iota
)

// ClaimsFromContext retrieves the verified *auth.TokenClaims injected by
// RequireAuth.  Returns nil if the middleware was not applied or the token was
// not verified.
func ClaimsFromContext(ctx context.Context) *auth.TokenClaims {
	v, _ := ctx.Value(claimsKey).(*auth.TokenClaims)
	return v
}

// RequireAuth returns a middleware that validates the Firebase ID token supplied
// in the "Authorization: Bearer <token>" header.
//
// On success the verified *auth.TokenClaims are stored in the request context
// (retrieve with ClaimsFromContext) and the next handler is called.
// On failure a 401 JSON response is returned and the chain is stopped.
//
// The verifier parameter accepts the auth.TokenVerifier interface so tests can
// inject a stub without calling Firebase.
func RequireAuth(verifier auth.TokenVerifier) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			token, ok := bearerToken(r)
			if !ok {
				writeUnauthorized(w, "missing or malformed Authorization header")
				return
			}

			claims, err := verifier.VerifyIDToken(r.Context(), token)
			if err != nil {
				writeUnauthorized(w, "invalid or expired token")
				return
			}

			ctx := context.WithValue(r.Context(), claimsKey, claims)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// bearerToken extracts the token from an "Authorization: Bearer <token>"
// header.  Returns ("", false) when the header is absent or not a Bearer
// scheme.
func bearerToken(r *http.Request) (string, bool) {
	h := r.Header.Get("Authorization")
	if h == "" {
		return "", false
	}
	parts := strings.SplitN(h, " ", 2)
	if len(parts) != 2 || !strings.EqualFold(parts[0], "Bearer") {
		return "", false
	}
	token := strings.TrimSpace(parts[1])
	if token == "" {
		return "", false
	}
	return token, true
}

// writeUnauthorized writes a 401 JSON error response.
func writeUnauthorized(w http.ResponseWriter, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusUnauthorized)
	_ = json.NewEncoder(w).Encode(map[string]string{"error": message})
}
