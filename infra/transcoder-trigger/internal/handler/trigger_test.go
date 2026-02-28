package handler_test

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/ai-teammate/mytube/infra/transcoder-trigger/internal/handler"
	"github.com/ai-teammate/mytube/infra/transcoder-trigger/internal/jobs"
)

// ── mockExecutor ──────────────────────────────────────────────────────────────

type mockExecutor struct {
	err      error
	received jobs.ExecuteRequest
	called   bool
}

func (m *mockExecutor) Execute(_ context.Context, req jobs.ExecuteRequest) error {
	m.called = true
	m.received = req
	return m.err
}

// ── helpers ───────────────────────────────────────────────────────────────────

func validBody() string {
	return `{"bucket":"mytube-raw-uploads","name":"raw/abc123.mp4"}`
}

// ── Tests ─────────────────────────────────────────────────────────────────────

func TestTriggerHandler_Success(t *testing.T) {
	exec := &mockExecutor{}
	h := handler.NewTriggerHandler(exec, "mytube-hls-output")

	req := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(validBody()))
	rec := httptest.NewRecorder()

	h(rec, req)

	if rec.Code != http.StatusNoContent {
		t.Errorf("expected 204, got %d", rec.Code)
	}
	if !exec.called {
		t.Error("expected executor to be called")
	}
}

func TestTriggerHandler_PassesCorrectVideoID(t *testing.T) {
	exec := &mockExecutor{}
	h := handler.NewTriggerHandler(exec, "hls-bucket")

	body := `{"bucket":"mytube-raw-uploads","name":"raw/550e8400-e29b-41d4-a716-446655440000.mp4"}`
	req := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(body))
	rec := httptest.NewRecorder()

	h(rec, req)

	if rec.Code != http.StatusNoContent {
		t.Fatalf("expected 204, got %d", rec.Code)
	}
	if exec.received.VideoID != "550e8400-e29b-41d4-a716-446655440000" {
		t.Errorf("unexpected VIDEO_ID: %q", exec.received.VideoID)
	}
}

func TestTriggerHandler_PassesRawObjectPath(t *testing.T) {
	exec := &mockExecutor{}
	h := handler.NewTriggerHandler(exec, "hls-bucket")

	req := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(validBody()))
	rec := httptest.NewRecorder()

	h(rec, req)

	if exec.received.RawObjectPath != "raw/abc123.mp4" {
		t.Errorf("unexpected RawObjectPath: %q", exec.received.RawObjectPath)
	}
}

func TestTriggerHandler_PassesHLSBucket(t *testing.T) {
	exec := &mockExecutor{}
	h := handler.NewTriggerHandler(exec, "my-hls-bucket")

	req := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(validBody()))
	rec := httptest.NewRecorder()

	h(rec, req)

	if exec.received.HLSBucket != "my-hls-bucket" {
		t.Errorf("unexpected HLSBucket: %q", exec.received.HLSBucket)
	}
}

func TestTriggerHandler_InvalidJSON_Returns400(t *testing.T) {
	exec := &mockExecutor{}
	h := handler.NewTriggerHandler(exec, "hls-bucket")

	req := httptest.NewRequest(http.MethodPost, "/", strings.NewReader("not-json"))
	rec := httptest.NewRecorder()

	h(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
	if exec.called {
		t.Error("executor must not be called on bad request")
	}
}

func TestTriggerHandler_MissingBucket_Returns400(t *testing.T) {
	exec := &mockExecutor{}
	h := handler.NewTriggerHandler(exec, "hls-bucket")

	body := `{"name":"raw/abc.mp4"}`
	req := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(body))
	rec := httptest.NewRecorder()

	h(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestTriggerHandler_MissingName_Returns400(t *testing.T) {
	exec := &mockExecutor{}
	h := handler.NewTriggerHandler(exec, "hls-bucket")

	body := `{"bucket":"mytube-raw-uploads"}`
	req := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(body))
	rec := httptest.NewRecorder()

	h(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestTriggerHandler_UnextractableVideoID_Returns400(t *testing.T) {
	exec := &mockExecutor{}
	h := handler.NewTriggerHandler(exec, "hls-bucket")

	// Name with only an extension results in empty video ID.
	body := `{"bucket":"b","name":"raw/.mp4"}`
	req := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(body))
	rec := httptest.NewRecorder()

	h(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for unextractable video ID, got %d", rec.Code)
	}
}

func TestTriggerHandler_ExecutorError_Returns500(t *testing.T) {
	exec := &mockExecutor{err: errors.New("cloud run api error")}
	h := handler.NewTriggerHandler(exec, "hls-bucket")

	req := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(validBody()))
	rec := httptest.NewRecorder()

	h(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestTriggerHandler_EmptyBody_Returns400(t *testing.T) {
	exec := &mockExecutor{}
	h := handler.NewTriggerHandler(exec, "hls-bucket")

	req := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(""))
	rec := httptest.NewRecorder()

	h(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for empty body, got %d", rec.Code)
	}
}
