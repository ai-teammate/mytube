// Package handler contains HTTP handler constructors.
package handler

import (
	"encoding/json"
	"net/http"
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
func NewHealthHandler(db Pinger) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if err := db.Ping(); err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			_ = json.NewEncoder(w).Encode(HealthResponse{Status: "error", DB: err.Error()})
			return
		}
		_ = json.NewEncoder(w).Encode(HealthResponse{Status: "ok", DB: "connected"})
	}
}
