package handler_test

import (
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/ai-teammate/mytube/api/internal/handler"
)

// mockPinger implements handler.Pinger for unit tests.
type mockPinger struct {
	err error
}

func (m *mockPinger) Ping() error { return m.err }

func TestNewHealthHandler_OK(t *testing.T) {
	pinger := &mockPinger{err: nil}
	h := handler.NewHealthHandler(pinger)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	h(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Fatalf("expected Content-Type application/json, got %s", ct)
	}

	var body handler.HealthResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode body: %v", err)
	}
	if body.Status != "ok" {
		t.Errorf("expected status ok, got %s", body.Status)
	}
	if body.DB != "connected" {
		t.Errorf("expected db connected, got %s", body.DB)
	}
}

func TestNewHealthHandler_DBError(t *testing.T) {
	dbErr := errors.New("connection refused")
	pinger := &mockPinger{err: dbErr}
	h := handler.NewHealthHandler(pinger)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	h(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Fatalf("expected 500, got %d", rec.Code)
	}

	var body handler.HealthResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode body: %v", err)
	}
	if body.Status != "error" {
		t.Errorf("expected status error, got %s", body.Status)
	}
	if body.DB != dbErr.Error() {
		t.Errorf("expected db %q, got %q", dbErr.Error(), body.DB)
	}
}
