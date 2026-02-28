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
	t.Setenv("HEALTH_TOKEN", "")
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
	t.Setenv("HEALTH_TOKEN", "")
	dbErr := errors.New("dial tcp 10.0.0.5:5432: connect: connection refused")
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
	// Internal error details must NOT be leaked to the caller.
	if body.DB == dbErr.Error() {
		t.Errorf("internal error details leaked to client: got %q", body.DB)
	}
	if body.DB != "unavailable" {
		t.Errorf("expected db unavailable, got %q", body.DB)
	}
}

func TestNewHealthHandler_TokenRequired(t *testing.T) {
	t.Setenv("HEALTH_TOKEN", "supersecret")

	pinger := &mockPinger{err: nil}
	h := handler.NewHealthHandler(pinger)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	h(rec, req)

	if rec.Code != http.StatusForbidden {
		t.Fatalf("expected 403 when token missing, got %d", rec.Code)
	}
}

func TestNewHealthHandler_TokenCorrect(t *testing.T) {
	t.Setenv("HEALTH_TOKEN", "supersecret")

	pinger := &mockPinger{err: nil}
	h := handler.NewHealthHandler(pinger)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	req.Header.Set("X-Health-Token", "supersecret")
	rec := httptest.NewRecorder()

	h(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 with correct token, got %d", rec.Code)
	}
}

func TestNewHealthHandler_TokenWrong(t *testing.T) {
	t.Setenv("HEALTH_TOKEN", "supersecret")

	pinger := &mockPinger{err: nil}
	h := handler.NewHealthHandler(pinger)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	req.Header.Set("X-Health-Token", "wrongtoken")
	rec := httptest.NewRecorder()

	h(rec, req)

	if rec.Code != http.StatusForbidden {
		t.Fatalf("expected 403 with wrong token, got %d", rec.Code)
	}
}

func TestNewHealthHandler_NoTokenEnvSkipsCheck(t *testing.T) {
	t.Setenv("HEALTH_TOKEN", "")

	pinger := &mockPinger{err: nil}
	h := handler.NewHealthHandler(pinger)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	h(rec, req)

	// When HEALTH_TOKEN is unset, the auth check is skipped and request proceeds.
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 when HEALTH_TOKEN unset, got %d", rec.Code)
	}
}
