package handler_test

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/ai-teammate/mytube/api/internal/auth"
	"github.com/ai-teammate/mytube/api/internal/handler"
	"github.com/ai-teammate/mytube/api/internal/repository"
)

// ─── stubs ────────────────────────────────────────────────────────────────────

type stubVideoManager struct {
	updateResult *repository.VideoDetail
	updateErr    error
	deleteResult bool
	deleteErr    error
}

func (s *stubVideoManager) Update(_ context.Context, _ string, _ string, _ repository.UpdateVideoParams) (*repository.VideoDetail, error) {
	return s.updateResult, s.updateErr
}

func (s *stubVideoManager) SoftDelete(_ context.Context, _ string, _ string) (bool, error) {
	return s.deleteResult, s.deleteErr
}

// ─── helpers ──────────────────────────────────────────────────────────────────

const testManageVideoID = "00000000-0000-0000-0000-000000000042"
const testOwnerUserID = "00000000-0000-0000-0000-000000000099"

func makeOwnerUser() *repository.User {
	return &repository.User{ID: testOwnerUserID, Username: "owner", FirebaseUID: "firebase-owner"}
}

func makeUpdatedVideoDetail() *repository.VideoDetail {
	desc := "Updated description"
	now := time.Now().Truncate(time.Second)
	return &repository.VideoDetail{
		ID:               testManageVideoID,
		Title:            "Updated Title",
		Description:      &desc,
		Status:           "ready",
		ViewCount:        5,
		CreatedAt:        now,
		UploaderUsername: "owner",
	}
}

func serveManageVideo(h http.Handler, r *http.Request) *httptest.ResponseRecorder {
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, r)
	return rec
}

// ─── GET delegation tests ─────────────────────────────────────────────────────

func TestNewManageVideoHandler_GET_DelegatesToVideoHandler(t *testing.T) {
	// GET should be delegated to NewVideoHandler (existing behaviour).
	video := makeReadyVideo()
	videoProvider := &stubVideoProvider{video: video, tags: []string{"go"}}
	manager := &stubVideoManager{}
	users := &stubUserIDProvider{}

	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+testVideoID, nil)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("GET: expected 200, got %d", rec.Code)
	}
	var body handler.VideoResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if body.ID != testVideoID {
		t.Errorf("GET delegated: ID got %q, want %q", body.ID, testVideoID)
	}
}

func TestNewManageVideoHandler_UnsupportedMethod_Returns405(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{}
	users := &stubUserIDProvider{}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	req := httptest.NewRequest(http.MethodPatch, "/api/videos/"+testManageVideoID, nil)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
}

// ─── PUT /api/videos/:id tests ────────────────────────────────────────────────

func TestPutVideo_NoClaims_Returns401(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{}
	users := &stubUserIDProvider{}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	req := httptest.NewRequest(http.MethodPut, "/api/videos/"+testManageVideoID,
		bytes.NewBufferString(`{"title":"New Title"}`))
	// No claims in context.
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rec.Code)
	}
}

func TestPutVideo_InvalidVideoID_Returns400(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{}
	users := &stubUserIDProvider{user: makeOwnerUser()}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	claims := &auth.TokenClaims{UID: "firebase-owner"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/videos/not-a-uuid",
			bytes.NewBufferString(`{"title":"New Title"}`)),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestPutVideo_UserNotFound_Returns404(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{}
	users := &stubUserIDProvider{user: nil}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	claims := &auth.TokenClaims{UID: "unknown-uid"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/videos/"+testManageVideoID,
			bytes.NewBufferString(`{"title":"New Title"}`)),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

func TestPutVideo_GetUserError_Returns500(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{}
	users := &stubUserIDProvider{err: errors.New("db error")}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	claims := &auth.TokenClaims{UID: "uid1"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/videos/"+testManageVideoID,
			bytes.NewBufferString(`{"title":"New Title"}`)),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

// TestPutVideo_VideoNotFound_Returns404 verifies that when Update() returns
// ErrNotFound (video does not exist), the handler returns 404.
func TestPutVideo_VideoNotFound_Returns404(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{updateErr: repository.ErrNotFound}
	users := &stubUserIDProvider{user: makeOwnerUser()}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	claims := &auth.TokenClaims{UID: "firebase-owner"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/videos/"+testManageVideoID,
			bytes.NewBufferString(`{"title":"New Title"}`)),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

// TestPutVideo_NonOwner_Returns403 is the regression test for MYTUBE-213.
// When Update() returns ErrForbidden (video exists but caller is not the owner),
// the handler must return 403 Forbidden — not 404.
func TestPutVideo_NonOwner_Returns403(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{updateErr: repository.ErrForbidden}
	users := &stubUserIDProvider{user: makeOwnerUser()}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	claims := &auth.TokenClaims{UID: "firebase-owner"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/videos/"+testManageVideoID,
			bytes.NewBufferString(`{"title":"Modified Title"}`)),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusForbidden {
		t.Errorf("expected 403, got %d", rec.Code)
	}
	var body map[string]string
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if body["error"] != "forbidden" {
		t.Errorf("error body: got %q, want \"forbidden\"", body["error"])
	}
}

func TestPutVideo_InvalidJSON_Returns400(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{}
	users := &stubUserIDProvider{user: makeOwnerUser()}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	claims := &auth.TokenClaims{UID: "firebase-owner"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/videos/"+testManageVideoID,
			bytes.NewBufferString("not-json")),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestPutVideo_EmptyTitle_Returns422(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{}
	users := &stubUserIDProvider{user: makeOwnerUser()}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	claims := &auth.TokenClaims{UID: "firebase-owner"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/videos/"+testManageVideoID,
			bytes.NewBufferString(`{"title":""}`)),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("expected 422, got %d", rec.Code)
	}
}

func TestPutVideo_TitleTooLong_Returns422(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{}
	users := &stubUserIDProvider{user: makeOwnerUser()}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	longTitle := make([]byte, 256)
	for i := range longTitle {
		longTitle[i] = 'a'
	}

	body, _ := json.Marshal(map[string]string{"title": string(longTitle)})
	claims := &auth.TokenClaims{UID: "firebase-owner"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/videos/"+testManageVideoID, bytes.NewBuffer(body)),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("expected 422, got %d", rec.Code)
	}
}

func TestPutVideo_TooManyTags_Returns422(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{}
	users := &stubUserIDProvider{user: makeOwnerUser()}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	tags := make([]string, 21)
	for i := range tags {
		tags[i] = fmt.Sprintf("tag%d", i) // unique tags so sanitiseTags doesn't deduplicate
	}
	body, _ := json.Marshal(map[string]interface{}{"title": "Valid", "tags": tags})
	claims := &auth.TokenClaims{UID: "firebase-owner"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/videos/"+testManageVideoID, bytes.NewBuffer(body)),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("expected 422, got %d", rec.Code)
	}
}

func TestPutVideo_UpdateError_Returns500(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{
		updateErr: errors.New("db error"),
	}
	users := &stubUserIDProvider{user: makeOwnerUser()}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	claims := &auth.TokenClaims{UID: "firebase-owner"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/videos/"+testManageVideoID,
			bytes.NewBufferString(`{"title":"New Title"}`)),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestPutVideo_Success_ReturnsUpdatedVideo(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{
		updateResult: makeUpdatedVideoDetail(),
	}
	users := &stubUserIDProvider{user: makeOwnerUser()}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	body, _ := json.Marshal(map[string]interface{}{
		"title":       "Updated Title",
		"description": "Updated description",
		"tags":        []string{"go", "tutorial"},
	})
	claims := &auth.TokenClaims{UID: "firebase-owner"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/videos/"+testManageVideoID, bytes.NewBuffer(body)),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("expected application/json, got %q", ct)
	}

	var resp handler.UpdateVideoResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if resp.ID != testManageVideoID {
		t.Errorf("ID: got %q, want %q", resp.ID, testManageVideoID)
	}
	if resp.Title != "Updated Title" {
		t.Errorf("Title: got %q, want Updated Title", resp.Title)
	}
	// Tags come directly from the validated request tags slice.
	if len(resp.Tags) != 2 {
		t.Errorf("Tags: expected 2, got %d", len(resp.Tags))
	}
}

// ─── DELETE /api/videos/:id tests ─────────────────────────────────────────────

func TestDeleteVideo_NoClaims_Returns401(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{}
	users := &stubUserIDProvider{}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	req := httptest.NewRequest(http.MethodDelete, "/api/videos/"+testManageVideoID, nil)
	// No claims.
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rec.Code)
	}
}

func TestDeleteVideo_InvalidVideoID_Returns400(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{}
	users := &stubUserIDProvider{user: makeOwnerUser()}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	claims := &auth.TokenClaims{UID: "firebase-owner"}
	req := withClaims(
		httptest.NewRequest(http.MethodDelete, "/api/videos/not-a-uuid", nil),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestDeleteVideo_UserNotFound_Returns404(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{}
	users := &stubUserIDProvider{user: nil}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	claims := &auth.TokenClaims{UID: "unknown"}
	req := withClaims(
		httptest.NewRequest(http.MethodDelete, "/api/videos/"+testManageVideoID, nil),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

func TestDeleteVideo_GetUserError_Returns500(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{}
	users := &stubUserIDProvider{err: errors.New("db error")}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	claims := &auth.TokenClaims{UID: "uid1"}
	req := withClaims(
		httptest.NewRequest(http.MethodDelete, "/api/videos/"+testManageVideoID, nil),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

// TestDeleteVideo_VideoNotFoundOrNotOwner_Returns404 verifies that when
// SoftDelete() returns false (video not found or caller is not the owner),
// the handler returns 404. Ownership is enforced atomically in the DB WHERE clause.
func TestDeleteVideo_VideoNotFoundOrNotOwner_Returns404(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{deleteResult: false}
	users := &stubUserIDProvider{user: makeOwnerUser()}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	claims := &auth.TokenClaims{UID: "firebase-owner"}
	req := withClaims(
		httptest.NewRequest(http.MethodDelete, "/api/videos/"+testManageVideoID, nil),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

func TestDeleteVideo_SoftDeleteError_Returns500(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{
		deleteErr: errors.New("db error"),
	}
	users := &stubUserIDProvider{user: makeOwnerUser()}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	claims := &auth.TokenClaims{UID: "firebase-owner"}
	req := withClaims(
		httptest.NewRequest(http.MethodDelete, "/api/videos/"+testManageVideoID, nil),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

// TestDeleteVideo_NonOwner_Returns403 verifies that when SoftDelete returns
// ErrForbidden (video exists but the caller is not the owner) the handler
// responds with HTTP 403 Forbidden and a JSON {"error":"forbidden"} body.
func TestDeleteVideo_NonOwner_Returns403(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{
		deleteErr: repository.ErrForbidden,
	}
	users := &stubUserIDProvider{user: makeOwnerUser()}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	claims := &auth.TokenClaims{UID: "firebase-non-owner"}
	req := withClaims(
		httptest.NewRequest(http.MethodDelete, "/api/videos/"+testManageVideoID, nil),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusForbidden {
		t.Errorf("expected 403, got %d", rec.Code)
	}
	var body map[string]string
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if body["error"] != "forbidden" {
		t.Errorf("expected error=forbidden, got %q", body["error"])
	}
}

func TestDeleteVideo_SoftDeleteReturnsFalse_Returns404(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{
		deleteResult: false, // no rows updated
	}
	users := &stubUserIDProvider{user: makeOwnerUser()}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	claims := &auth.TokenClaims{UID: "firebase-owner"}
	req := withClaims(
		httptest.NewRequest(http.MethodDelete, "/api/videos/"+testManageVideoID, nil),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

func TestDeleteVideo_Success_Returns204(t *testing.T) {
	videoProvider := &stubVideoProvider{}
	manager := &stubVideoManager{
		deleteResult: true,
	}
	users := &stubUserIDProvider{user: makeOwnerUser()}
	h := handler.NewManageVideoHandler(videoProvider, manager, users, "")

	claims := &auth.TokenClaims{UID: "firebase-owner"}
	req := withClaims(
		httptest.NewRequest(http.MethodDelete, "/api/videos/"+testManageVideoID, nil),
		claims,
	)
	rec := serveManageVideo(h, req)

	if rec.Code != http.StatusNoContent {
		t.Errorf("expected 204, got %d", rec.Code)
	}
}
