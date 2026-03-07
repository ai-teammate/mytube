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

// ─── stub PublicUserProvider ──────────────────────────────────────────────────

type stubPublicUserProvider struct {
	user      *repository.User
	userErr   error
	videos    []repository.Video
	videosErr error
}

func (s *stubPublicUserProvider) GetByUsername(_ context.Context, _ string) (*repository.User, error) {
	return s.user, s.userErr
}

func (s *stubPublicUserProvider) GetVideosByUserID(_ context.Context, _ string) ([]repository.Video, error) {
	return s.videos, s.videosErr
}

// serveUsers calls the users handler with the given request.
func serveUsers(h http.Handler, r *http.Request) *httptest.ResponseRecorder {
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, r)
	return rec
}

// ─── GET /api/users/:username tests ──────────────────────────────────────────

func TestNewUsersHandler_GET_UserNotFound_Returns404(t *testing.T) {
	p := &stubPublicUserProvider{user: nil, userErr: nil}
	h := handler.NewUsersHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/users/unknown", nil)
	rec := serveUsers(h, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

func TestNewUsersHandler_GET_GetByUsernameError_Returns500(t *testing.T) {
	dbErr := errors.New("database error")
	p := &stubPublicUserProvider{userErr: dbErr}
	h := handler.NewUsersHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/users/alice", nil)
	rec := serveUsers(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestNewUsersHandler_GET_GetVideosError_Returns500(t *testing.T) {
	user := &repository.User{ID: "u1", Username: "alice"}
	videosErr := errors.New("videos query failed")
	p := &stubPublicUserProvider{user: user, videosErr: videosErr}
	h := handler.NewUsersHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/users/alice", nil)
	rec := serveUsers(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestNewUsersHandler_GET_Success_ReturnsProfileJSON(t *testing.T) {
	avatarURL := "https://example.com/avatar.png"
	user := &repository.User{
		ID:        "00000000-0000-0000-0000-000000000001",
		Username:  "alice",
		AvatarURL: &avatarURL,
	}
	thumb := "https://example.com/thumb.jpg"
	now := time.Now().Truncate(time.Second)
	videos := []repository.Video{
		{ID: "v1", Title: "My Video", ThumbnailURL: &thumb, ViewCount: 42, CreatedAt: now},
	}

	p := &stubPublicUserProvider{user: user, videos: videos}
	h := handler.NewUsersHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/users/alice", nil)
	rec := serveUsers(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("expected Content-Type application/json, got %q", ct)
	}

	var body handler.UserProfileResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if body.Username != "alice" {
		t.Errorf("Username: got %q, want %q", body.Username, "alice")
	}
	if body.AvatarURL == nil || *body.AvatarURL != avatarURL {
		t.Errorf("AvatarURL: got %v, want %q", body.AvatarURL, avatarURL)
	}
	if len(body.Videos) != 1 {
		t.Fatalf("expected 1 video, got %d", len(body.Videos))
	}
	if body.Videos[0].ID != "v1" {
		t.Errorf("Videos[0].ID: got %q, want %q", body.Videos[0].ID, "v1")
	}
	if body.Videos[0].Title != "My Video" {
		t.Errorf("Videos[0].Title: got %q, want %q", body.Videos[0].Title, "My Video")
	}
	if body.Videos[0].ThumbnailURL == nil || *body.Videos[0].ThumbnailURL != thumb {
		t.Errorf("Videos[0].ThumbnailURL: got %v, want %q", body.Videos[0].ThumbnailURL, thumb)
	}
	if body.Videos[0].ViewCount != 42 {
		t.Errorf("Videos[0].ViewCount: got %d, want 42", body.Videos[0].ViewCount)
	}
}

func TestNewUsersHandler_GET_NilAvatarURL_SerializedAsNull(t *testing.T) {
	user := &repository.User{ID: "u2", Username: "bob", AvatarURL: nil}
	p := &stubPublicUserProvider{user: user, videos: nil}
	h := handler.NewUsersHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/users/bob", nil)
	rec := serveUsers(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var body handler.UserProfileResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if body.AvatarURL != nil {
		t.Errorf("expected null avatar_url, got %q", *body.AvatarURL)
	}
}

func TestNewUsersHandler_GET_EmptyVideoList(t *testing.T) {
	user := &repository.User{ID: "u3", Username: "carol"}
	p := &stubPublicUserProvider{user: user, videos: []repository.Video{}}
	h := handler.NewUsersHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/users/carol", nil)
	rec := serveUsers(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var body handler.UserProfileResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if len(body.Videos) != 0 {
		t.Errorf("expected 0 videos, got %d", len(body.Videos))
	}
}

func TestNewUsersHandler_GET_NilVideoSlice_SerializedAsEmptyArray(t *testing.T) {
	user := &repository.User{ID: "u4", Username: "dave"}
	p := &stubPublicUserProvider{user: user, videos: nil}
	h := handler.NewUsersHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/users/dave", nil)
	rec := serveUsers(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	// Decode as generic map to inspect videos field directly.
	var raw map[string]json.RawMessage
	if err := json.NewDecoder(rec.Body).Decode(&raw); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if string(raw["videos"]) != "[]" {
		t.Errorf("videos field: got %s, want []", string(raw["videos"]))
	}
}

func TestNewUsersHandler_GET_EmptyUsernamePathSegment_Returns400(t *testing.T) {
	p := &stubPublicUserProvider{}
	h := handler.NewUsersHandler(p)

	// Path "/api/users/" with nothing after
	req := httptest.NewRequest(http.MethodGet, "/api/users/", nil)
	rec := serveUsers(h, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}
}

func TestNewUsersHandler_UnsupportedMethod_Returns405(t *testing.T) {
	p := &stubPublicUserProvider{}
	h := handler.NewUsersHandler(p)

	req := httptest.NewRequest(http.MethodPost, "/api/users/alice", nil)
	rec := serveUsers(h, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
}

func TestNewUsersHandler_GET_PassesUsernameToGetByUsername(t *testing.T) {
	var gotUsername string
	recording := &recordingPublicUserProvider{
		onGetByUsername: func(username string) (*repository.User, error) {
			gotUsername = username
			return &repository.User{ID: "u5", Username: username}, nil
		},
	}

	h := handler.NewUsersHandler(recording)
	req := httptest.NewRequest(http.MethodGet, "/api/users/testuser", nil)
	serveUsers(h, req)

	if gotUsername != "testuser" {
		t.Errorf("GetByUsername called with %q, want %q", gotUsername, "testuser")
	}
}

func TestNewUsersHandler_GET_PassesUserIDToGetVideosByUserID(t *testing.T) {
	var gotUserID string
	recording := &recordingPublicUserProvider{
		onGetByUsername: func(_ string) (*repository.User, error) {
			return &repository.User{ID: "captured-user-id", Username: "alice"}, nil
		},
		onGetVideosByUserID: func(userID string) ([]repository.Video, error) {
			gotUserID = userID
			return nil, nil
		},
	}

	h := handler.NewUsersHandler(recording)
	req := httptest.NewRequest(http.MethodGet, "/api/users/alice", nil)
	serveUsers(h, req)

	if gotUserID != "captured-user-id" {
		t.Errorf("GetVideosByUserID called with %q, want %q", gotUserID, "captured-user-id")
	}
}

func TestNewUsersHandler_GET_VideoWithNilThumbnail(t *testing.T) {
	user := &repository.User{ID: "u6", Username: "eve"}
	videos := []repository.Video{
		{ID: "v10", Title: "No Thumb", ThumbnailURL: nil, ViewCount: 0},
	}
	p := &stubPublicUserProvider{user: user, videos: videos}
	h := handler.NewUsersHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/users/eve", nil)
	rec := serveUsers(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var body handler.UserProfileResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if len(body.Videos) != 1 {
		t.Fatalf("expected 1 video, got %d", len(body.Videos))
	}
	if body.Videos[0].ThumbnailURL != nil {
		t.Errorf("expected nil ThumbnailURL, got %q", *body.Videos[0].ThumbnailURL)
	}
}

// ─── recording stub ───────────────────────────────────────────────────────────

type recordingPublicUserProvider struct {
	onGetByUsername     func(username string) (*repository.User, error)
	onGetVideosByUserID func(userID string) ([]repository.Video, error)
}

func (r *recordingPublicUserProvider) GetByUsername(_ context.Context, username string) (*repository.User, error) {
	if r.onGetByUsername != nil {
		return r.onGetByUsername(username)
	}
	return &repository.User{ID: "default", Username: username}, nil
}

func (r *recordingPublicUserProvider) GetVideosByUserID(_ context.Context, userID string) ([]repository.Video, error) {
	if r.onGetVideosByUserID != nil {
		return r.onGetVideosByUserID(userID)
	}
	return nil, nil
}

func TestNewUsersHandler_GET_TooLongUsername_Returns400(t *testing.T) {
	p := &stubPublicUserProvider{}
	h := handler.NewUsersHandler(p)

	longUsername := strings.Repeat("a", 101)
	req := httptest.NewRequest(http.MethodGet, "/api/users/"+longUsername, nil)
	rec := serveUsers(h, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for oversized username, got %d", rec.Code)
	}
}

func TestNewUsersHandler_GET_InvalidUsernameChars_Returns400(t *testing.T) {
	p := &stubPublicUserProvider{}
	h := handler.NewUsersHandler(p)

	// Path traversal attempt
	req := httptest.NewRequest(http.MethodGet, "/api/users/../etc", nil)
	rec := serveUsers(h, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for invalid username chars, got %d", rec.Code)
	}
}

// TestNewUsersHandler_GET_HyphenatedUsername_Returns200 is the reproduction
// test for MYTUBE-304: the ci-test user has a hyphen in their username
// (derived from ci-test@mytube.test). The handler was rejecting the request
// with 400 because usernameRE did not allow hyphens.
func TestNewUsersHandler_GET_HyphenatedUsername_Returns200(t *testing.T) {
	user := &repository.User{ID: "ci-user-id", Username: "ci-test"}
	p := &stubPublicUserProvider{user: user, videos: []repository.Video{}}
	h := handler.NewUsersHandler(p)

	req := httptest.NewRequest(http.MethodGet, "/api/users/ci-test", nil)
	rec := serveUsers(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200 for hyphenated username ci-test, got %d", rec.Code)
	}
}
