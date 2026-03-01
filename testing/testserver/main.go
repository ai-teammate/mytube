// testserver is a minimal HTTP server for integration testing the auth middleware
// header-format validation logic (MYTUBE-65).
//
// It re-implements the exact bearerToken() and RequireAuth logic from
// api/internal/middleware/auth.go using only the Go standard library, so it can
// run in CI without Firebase credentials or a live database.
//
// The tested behaviour: the middleware rejects any request whose Authorization
// header does not match "Bearer <non-empty-token>" by returning HTTP 401.  This
// rejection happens purely on header format — no token verification is attempted
// for malformed headers.
//
// Usage:
//
//	go run . -port 18650
//
// Endpoints:
//
//	GET /health  — always 200 (readiness probe)
//	GET /api/me  — protected by requireAuth; returns 200 only for a properly
//	               formed "Bearer <token>" header (token value is not validated)
package main

import (
	"encoding/json"
	"flag"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
)

// bearerToken mirrors api/internal/middleware/auth.go bearerToken().
// It extracts the token from "Authorization: Bearer <token>".
// Returns ("", false) when the header is absent, uses a non-Bearer scheme, or
// has an empty token after trimming whitespace.
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

// requireAuth mirrors api/internal/middleware/auth.go RequireAuth().
// For any properly-formed Bearer header it calls next; otherwise it writes a
// 401 JSON response.  Token value is not validated — this server is only for
// testing the header-format rejection path.
func requireAuth(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, ok := bearerToken(r)
		if !ok {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			_ = json.NewEncoder(w).Encode(map[string]string{"error": "missing or malformed Authorization header"})
			return
		}
		next.ServeHTTP(w, r)
	})
}

func main() {
	port := flag.String("port", "18650", "TCP port to listen on")
	flag.Parse()

	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	})
	mux.Handle("/api/me", requireAuth(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	})))

	addr := "127.0.0.1:" + *port
	srv := &http.Server{Addr: addr, Handler: mux}

	go func() {
		log.Printf("testserver listening on %s", addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %v", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGTERM, syscall.SIGINT)
	<-quit
	log.Println("testserver shutting down")
}
