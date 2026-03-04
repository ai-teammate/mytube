package middleware

import "net/http"

const allowedOrigin = "https://ai-teammate.github.io"

// CORS returns an http.Handler that adds the required Cross-Origin Resource
// Sharing headers to every response so that the frontend served from
// https://ai-teammate.github.io can call the API.
//
// Preflight OPTIONS requests are answered immediately with 204 No Content and
// the appropriate Access-Control-Allow-* headers; the next handler is not
// called for those requests.
func CORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", allowedOrigin)
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}

		next.ServeHTTP(w, r)
	})
}
