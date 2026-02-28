// Package handler contains HTTP handler constructors.
package handler

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
)

// Pinger is satisfied by *sql.DB and allows tests to inject a mock.
type Pinger interface {
	Ping() error
}

// HealthResponse is the JSON body returned by the health endpoint.
type HealthResponse struct {
	Status string `json:"status"`
	DB     string `json:"db"`
}

// NewHealthHandler returns an http.HandlerFunc for GET /health.
// It calls db.Ping() and reports the result as JSON.
//
// The endpoint is protected by a shared secret token: callers must supply the
// value of the HEALTH_TOKEN environment variable in the X-Health-Token header.
// When HEALTH_TOKEN is unset the check is skipped (suitable for local dev).
//
// Internal database error details are logged server-side only; the response
// body always returns the generic string "unavailable" to avoid leaking
// infrastructure information to callers (OWASP A05).
func NewHealthHandler(db Pinger) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		token := os.Getenv("HEALTH_TOKEN")
		if token != "" && r.Header.Get("X-Health-Token") != token {
			http.Error(w, "forbidden", http.StatusForbidden)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		if err := db.Ping(); err != nil {
			log.Printf("health check: db ping failed: %v", err)
			w.WriteHeader(http.StatusInternalServerError)
			_ = json.NewEncoder(w).Encode(HealthResponse{Status: "error", DB: "unavailable"})
			return
		}
		_ = json.NewEncoder(w).Encode(HealthResponse{Status: "ok", DB: "connected"})
	}
}
