package handler_test

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/ai-teammate/mytube/api/internal/handler"
	"github.com/ai-teammate/mytube/api/internal/repository"
)

// testVideoID is a valid UUID used as the video identifier throughout tests.
const testVideoID = "00000000-0000-0000-0000-000000000001"

// ─── stub VideoProvider ───────────────────────────────────────────────────────

type stubVideoProvider struct {
	video     *repository.VideoDetail
	videoErr  error
	incErr    error
	incCalled bool
	tags      []string
	tagsErr   error
}

func (s *stubVideoProvider) GetByID(_ context.Context, _ string) (*repository.VideoDetail, error) {
	return s.video, s.videoErr
}

func (s *stubVideoProvider) IncrementViewCount(_ context.Context, _ string) (bool, error) {
	s.incCalled = true
	return true, s.incErr
}

func (s *stubVideoProvider) GetTagsByVideoID(_ context.Context, _ string) ([]string, error) {
	return s.tags, s.tagsErr
}

// serveVideo calls the video handler with the given request.
func serveVideo(h http.Handler, r *http.Request) *httptest.ResponseRecorder {
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, r)
	return rec
}

// makeReadyVideo returns a minimal VideoDetail with status="ready".
func makeReadyVideo() *repository.VideoDetail {
	desc := "A great video"
	hls := "gs://mybucket/videos/v1/index.m3u8"
	thumb := "https://cdn.example.com/thumb.jpg"
	now := time.Now().Truncate(time.Second)
	return &repository.VideoDetail{
		ID:               testVideoID,
		Title:            "Test Video",
		Description:      &desc,
		HLSManifestPath:  &hls,
		ThumbnailURL:     &thumb,
		ViewCount:        42,
		CreatedAt:        now,
		Status:           "ready",
		UploaderUsername: "alice",
	}
}

// ─── GET /api/videos/:id tests ────────────────────────────────────────────────

func TestNewVideoHandler_GET_VideoNotFound_Returns404(t *testing.T) {
	p := &stubVideoProvider{video: nil}
	h := handler.NewVideoHandler(p, "https://cdn.example.com")

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+testVideoID, nil)
	rec := serveVideo(h, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

func TestNewVideoHandler_GET_GetByIDError_Returns500(t *testing.T) {
	p := &stubVideoProvider{videoErr: errors.New("db error")}
	h := handler.NewVideoHandler(p, "")

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+testVideoID, nil)
	rec := serveVideo(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestNewVideoHandler_GET_EmptyVideoID_Returns400(t *testing.T) {
	p := &stubVideoProvider{}
	h := handler.NewVideoHandler(p, "")

	req := httptest.NewRequest(http.MethodGet, "/api/videos/", nil)
	rec := serveVideo(h, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestNewVideoHandler_GET_InvalidVideoID_Returns400(t *testing.T) {
	p := &stubVideoProvider{}
	h := handler.NewVideoHandler(p, "")

	// Non-UUID strings must be rejected with 400 before hitting the DB.
	for _, id := range []string{"not-a-uuid", "v1", "video-id-1", "../secret", strings.Repeat("a", 200)} {
		req := httptest.NewRequest(http.MethodGet, "/api/videos/"+id, nil)
		rec := serveVideo(h, req)
		if rec.Code != http.StatusBadRequest {
			t.Errorf("id=%q: expected 400, got %d", id, rec.Code)
		}
		// DB must not be called for invalid IDs.
		if p.incCalled {
			t.Errorf("id=%q: IncrementViewCount was called for an invalid ID", id)
		}
	}
}

func TestNewVideoHandler_UnsupportedMethod_Returns405(t *testing.T) {
	p := &stubVideoProvider{}
	h := handler.NewVideoHandler(p, "")

	req := httptest.NewRequest(http.MethodPost, "/api/videos/"+testVideoID, nil)
	rec := serveVideo(h, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
}

func TestNewVideoHandler_GET_Success_ReturnsVideoJSON(t *testing.T) {
	video := makeReadyVideo()
	avatarURL := "https://example.com/avatar.png"
	video.UploaderAvatarURL = &avatarURL
	p := &stubVideoProvider{
		video: video,
		tags:  []string{"go", "programming"},
	}
	h := handler.NewVideoHandler(p, "https://cdn.example.com")

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+testVideoID, nil)
	rec := serveVideo(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("expected Content-Type application/json, got %q", ct)
	}

	var body handler.VideoResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if body.ID != testVideoID {
		t.Errorf("ID: got %q, want %q", body.ID, testVideoID)
	}
	if body.Title != "Test Video" {
		t.Errorf("Title: got %q, want %q", body.Title, "Test Video")
	}
	if body.Status != "ready" {
		t.Errorf("Status: got %q, want %q", body.Status, "ready")
	}
	if body.Uploader.Username != "alice" {
		t.Errorf("Uploader.Username: got %q, want %q", body.Uploader.Username, "alice")
	}
	if body.Uploader.AvatarURL == nil || *body.Uploader.AvatarURL != avatarURL {
		t.Errorf("Uploader.AvatarURL: got %v, want %q", body.Uploader.AvatarURL, avatarURL)
	}
	if len(body.Tags) != 2 {
		t.Fatalf("expected 2 tags, got %d", len(body.Tags))
	}
	if body.Tags[0] != "go" || body.Tags[1] != "programming" {
		t.Errorf("Tags: got %v, want [go programming]", body.Tags)
	}
}

func TestNewVideoHandler_GET_HLSManifestURL_CDNConversion(t *testing.T) {
	hls := "gs://mybucket/videos/v1/index.m3u8"
	video := &repository.VideoDetail{
		ID:               testVideoID,
		Title:            "CDN Test",
		HLSManifestPath:  &hls,
		Status:           "ready",
		UploaderUsername: "alice",
	}
	p := &stubVideoProvider{video: video, tags: []string{}}
	h := handler.NewVideoHandler(p, "https://cdn.example.com")

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+testVideoID, nil)
	rec := serveVideo(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var body handler.VideoResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if body.HLSManifestURL == nil {
		t.Fatal("expected non-nil hls_manifest_url")
	}
	want := "https://cdn.example.com/videos/v1/index.m3u8"
	if *body.HLSManifestURL != want {
		t.Errorf("HLSManifestURL: got %q, want %q", *body.HLSManifestURL, want)
	}
}

func TestNewVideoHandler_GET_HLSManifestURL_NilWhenNoCDNConfig(t *testing.T) {
	hls := "gs://mybucket/videos/v1/index.m3u8"
	video := &repository.VideoDetail{
		ID:               testVideoID,
		Title:            "No CDN",
		HLSManifestPath:  &hls,
		Status:           "ready",
		UploaderUsername: "alice",
	}
	p := &stubVideoProvider{video: video, tags: []string{}}
	// Pass empty cdnBaseURL
	h := handler.NewVideoHandler(p, "")

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+testVideoID, nil)
	rec := serveVideo(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var body handler.VideoResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	// When no CDN configured, should fall back to raw path
	if body.HLSManifestURL == nil || *body.HLSManifestURL != hls {
		t.Errorf("HLSManifestURL: got %v, want %q", body.HLSManifestURL, hls)
	}
}

func TestNewVideoHandler_GET_NilHLSPath_ReturnsNullURL(t *testing.T) {
	video := &repository.VideoDetail{
		ID:               testVideoID,
		Title:            "No HLS",
		HLSManifestPath:  nil,
		Status:           "ready",
		UploaderUsername: "alice",
	}
	p := &stubVideoProvider{video: video, tags: []string{}}
	h := handler.NewVideoHandler(p, "https://cdn.example.com")

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+testVideoID, nil)
	rec := serveVideo(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var raw map[string]json.RawMessage
	if err := json.NewDecoder(rec.Body).Decode(&raw); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if string(raw["hls_manifest_url"]) != "null" {
		t.Errorf("hls_manifest_url: got %s, want null", string(raw["hls_manifest_url"]))
	}
}

func TestNewVideoHandler_GET_IncrementViewCount_Called(t *testing.T) {
	video := makeReadyVideo()
	p := &stubVideoProvider{video: video, tags: []string{}}
	h := handler.NewVideoHandler(p, "")

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+testVideoID, nil)
	serveVideo(h, req)

	if !p.incCalled {
		t.Errorf("expected IncrementViewCount to be called")
	}
}

func TestNewVideoHandler_GET_IncrementViewCountError_StillReturns200(t *testing.T) {
	// View count increment errors should not fail the request
	video := makeReadyVideo()
	p := &stubVideoProvider{
		video:  video,
		incErr: errors.New("increment failed"),
		tags:   []string{},
	}
	h := handler.NewVideoHandler(p, "")

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+testVideoID, nil)
	rec := serveVideo(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200 despite increment error, got %d", rec.Code)
	}
}

func TestNewVideoHandler_GET_TagsError_Returns500(t *testing.T) {
	video := makeReadyVideo()
	p := &stubVideoProvider{
		video:   video,
		tagsErr: errors.New("tags query failed"),
	}
	h := handler.NewVideoHandler(p, "")

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+testVideoID, nil)
	rec := serveVideo(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500 on tags error, got %d", rec.Code)
	}
}

func TestNewVideoHandler_GET_EmptyTagsReturnedAsEmptyArray(t *testing.T) {
	video := makeReadyVideo()
	p := &stubVideoProvider{video: video, tags: []string{}}
	h := handler.NewVideoHandler(p, "")

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+testVideoID, nil)
	rec := serveVideo(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var raw map[string]json.RawMessage
	if err := json.NewDecoder(rec.Body).Decode(&raw); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if string(raw["tags"]) != "[]" {
		t.Errorf("tags: got %s, want []", string(raw["tags"]))
	}
}

func TestNewVideoHandler_GET_NilDescription_SerializedAsNull(t *testing.T) {
	video := makeReadyVideo()
	video.Description = nil
	p := &stubVideoProvider{video: video, tags: []string{}}
	h := handler.NewVideoHandler(p, "")

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+testVideoID, nil)
	rec := serveVideo(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var raw map[string]json.RawMessage
	if err := json.NewDecoder(rec.Body).Decode(&raw); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if string(raw["description"]) != "null" {
		t.Errorf("description: got %s, want null", string(raw["description"]))
	}
}

func TestNewVideoHandler_GET_NilUploaderAvatar_SerializedAsNull(t *testing.T) {
	video := makeReadyVideo()
	video.UploaderAvatarURL = nil
	p := &stubVideoProvider{video: video, tags: []string{}}
	h := handler.NewVideoHandler(p, "")

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+testVideoID, nil)
	rec := serveVideo(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var body handler.VideoResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if body.Uploader.AvatarURL != nil {
		t.Errorf("Uploader.AvatarURL: expected null, got %q", *body.Uploader.AvatarURL)
	}
}

func TestNewVideoHandler_GET_ViewCount_IncrementedInResponse(t *testing.T) {
	// ViewCount in the DB is 9999; IncrementViewCount succeeds (returns true, nil),
	// so the response should return 10000 (post-increment value).
	video := makeReadyVideo()
	video.ViewCount = 9999
	p := &stubVideoProvider{video: video, tags: []string{}}
	h := handler.NewVideoHandler(p, "")

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+testVideoID, nil)
	rec := serveVideo(h, req)

	var body handler.VideoResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	// Expect 10000: pre-increment value (9999) + 1 because IncrementViewCount succeeded.
	if body.ViewCount != 10000 {
		t.Errorf("ViewCount: got %d, want 10000", body.ViewCount)
	}
}

func TestNewVideoHandler_GET_ViewCount_NotIncrementedWhenIncrementFails(t *testing.T) {
	// When IncrementViewCount returns an error, the response should return the
	// pre-increment value (not incremented).
	video := makeReadyVideo()
	video.ViewCount = 9999
	p := &stubVideoProvider{
		video:  video,
		incErr: errors.New("increment failed"),
		tags:   []string{},
	}
	h := handler.NewVideoHandler(p, "")

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+testVideoID, nil)
	rec := serveVideo(h, req)

	var body handler.VideoResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if body.ViewCount != 9999 {
		t.Errorf("ViewCount: got %d, want 9999 (no increment on error)", body.ViewCount)
	}
}

// ─── cdnURLFromGCSPath tests ──────────────────────────────────────────────────
// We test this via the public handler, but also validate edge cases directly
// through the handler's behavior.

func TestNewVideoHandler_CDNConversion_TrailingSlashOnBaseURL(t *testing.T) {
	hls := "gs://mybucket/videos/v1/index.m3u8"
	video := &repository.VideoDetail{
		ID:               testVideoID,
		Title:            "CDN Trailing Slash",
		HLSManifestPath:  &hls,
		Status:           "ready",
		UploaderUsername: "alice",
	}
	p := &stubVideoProvider{video: video, tags: []string{}}
	// CDN base URL with trailing slash
	h := handler.NewVideoHandler(p, "https://cdn.example.com/")

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+testVideoID, nil)
	rec := serveVideo(h, req)

	var body handler.VideoResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	want := "https://cdn.example.com/videos/v1/index.m3u8"
	if body.HLSManifestURL == nil || *body.HLSManifestURL != want {
		t.Errorf("HLSManifestURL: got %v, want %q", body.HLSManifestURL, want)
	}
}

func TestNewVideoHandler_GET_PassesVideoIDToGetByID(t *testing.T) {
	var gotID string
	recording := &recordingVideoProvider{
		onGetByID: func(id string) (*repository.VideoDetail, error) {
			gotID = id
			return makeReadyVideo(), nil
		},
	}
	h := handler.NewVideoHandler(recording, "")
	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+testVideoID, nil)
	serveVideo(h, req)

	if gotID != testVideoID {
		t.Errorf("GetByID called with %q, want %q", gotID, testVideoID)
	}
}

// ─── recording stub ───────────────────────────────────────────────────────────

type recordingVideoProvider struct {
	onGetByID            func(id string) (*repository.VideoDetail, error)
	onIncrementViewCount func(id string) (bool, error)
	onGetTagsByVideoID   func(id string) ([]string, error)
}

func (r *recordingVideoProvider) GetByID(_ context.Context, id string) (*repository.VideoDetail, error) {
	if r.onGetByID != nil {
		return r.onGetByID(id)
	}
	return makeReadyVideo(), nil
}

func (r *recordingVideoProvider) IncrementViewCount(_ context.Context, id string) (bool, error) {
	if r.onIncrementViewCount != nil {
		return r.onIncrementViewCount(id)
	}
	return true, nil
}

func (r *recordingVideoProvider) GetTagsByVideoID(_ context.Context, id string) ([]string, error) {
	if r.onGetTagsByVideoID != nil {
		return r.onGetTagsByVideoID(id)
	}
	return []string{}, nil
}

func TestNewVideoHandler_GET_NonGCSPath_ReturnedAsIs(t *testing.T) {
	// If hls_manifest_path doesn't start with gs://, return as-is
	rawPath := "https://storage.googleapis.com/mybucket/videos/v1/index.m3u8"
	video := &repository.VideoDetail{
		ID:               testVideoID,
		Title:            "Non-GCS",
		HLSManifestPath:  &rawPath,
		Status:           "ready",
		UploaderUsername: "alice",
	}
	p := &stubVideoProvider{video: video, tags: []string{}}
	h := handler.NewVideoHandler(p, "https://cdn.example.com")

	req := httptest.NewRequest(http.MethodGet, "/api/videos/"+testVideoID, nil)
	rec := serveVideo(h, req)

	var body handler.VideoResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	// Non-GCS path should be returned unchanged
	if body.HLSManifestURL == nil || *body.HLSManifestURL != rawPath {
		t.Errorf("HLSManifestURL: got %v, want %q", body.HLSManifestURL, rawPath)
	}
}

func TestNewVideoHandler_GET_AllowMethod_SetOn405(t *testing.T) {
	p := &stubVideoProvider{}
	h := handler.NewVideoHandler(p, "")

	req := httptest.NewRequest(http.MethodDelete, "/api/videos/"+testVideoID, nil)
	rec := serveVideo(h, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
	if allow := rec.Header().Get("Allow"); !strings.Contains(allow, "GET") {
		t.Errorf("Allow header: got %q, expected to contain GET", allow)
	}
}
