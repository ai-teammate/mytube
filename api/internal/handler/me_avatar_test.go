package handler_test

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"net/textproto"
	"strings"
	"testing"

	"github.com/ai-teammate/mytube/api/internal/auth"
	"github.com/ai-teammate/mytube/api/internal/handler"
	"github.com/ai-teammate/mytube/api/internal/repository"
	"github.com/ai-teammate/mytube/api/internal/storage"
)

// ─── stubs ────────────────────────────────────────────────────────────────────

// stubAvatarUserProvider satisfies handler.AvatarUserProvider.
type stubAvatarUserProvider struct {
	getUser    *repository.User
	getErr     error
	updateUser *repository.User
	updateErr  error

	// captured arguments
	capturedUpdateUID string
	capturedUpdateURL string
}

func (s *stubAvatarUserProvider) GetByFirebaseUID(_ context.Context, _ string) (*repository.User, error) {
	return s.getUser, s.getErr
}

func (s *stubAvatarUserProvider) UpdateAvatarURL(_ context.Context, firebaseUID, avatarURL string) (*repository.User, error) {
	s.capturedUpdateUID = firebaseUID
	s.capturedUpdateURL = avatarURL
	return s.updateUser, s.updateErr
}

// stubUploader satisfies storage.Uploader.
type stubUploader struct {
	err              error
	capturedBucket   string
	capturedObject   string
	capturedMIMEType string
}

func (s *stubUploader) Upload(_ context.Context, bucket, object, contentType string, _ io.Reader) error {
	s.capturedBucket = bucket
	s.capturedObject = object
	s.capturedMIMEType = contentType
	return s.err
}

// Compile-time interface checks.
var _ storage.Uploader = (*stubUploader)(nil)

// ─── helpers ──────────────────────────────────────────────────────────────────

// buildMultipartRequest builds a multipart/form-data POST request containing a
// single "avatar" file part with the given MIME type and body.
func buildMultipartRequest(t *testing.T, fieldName, mimeType string, body []byte) *http.Request {
	t.Helper()
	var buf bytes.Buffer
	mw := multipart.NewWriter(&buf)

	h := make(textproto.MIMEHeader)
	h.Set("Content-Disposition", fmt.Sprintf(`form-data; name="%s"; filename="avatar.img"`, fieldName))
	h.Set("Content-Type", mimeType)
	pw, err := mw.CreatePart(h)
	if err != nil {
		t.Fatalf("create multipart part: %v", err)
	}
	if _, err := pw.Write(body); err != nil {
		t.Fatalf("write multipart part: %v", err)
	}
	mw.Close()

	req := httptest.NewRequest(http.MethodPost, "/api/me/avatar", &buf)
	req.Header.Set("Content-Type", mw.FormDataContentType())
	return req
}

// defaultUser returns a ready-to-use User stub.
func defaultAvatarUser() *repository.User {
	return &repository.User{
		ID:          "00000000-0000-0000-0000-000000000001",
		FirebaseUID: "firebase-uid-1",
		Username:    "alice",
	}
}

// serveAvatar runs the handler and returns the recorder.
func serveAvatar(h http.Handler, r *http.Request) *httptest.ResponseRecorder {
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, r)
	return rec
}

// avatarHandlerWithDefaults builds a handler with sensible defaults for
// tests that only care about one specific aspect.
func avatarHandlerWithDefaults(users handler.AvatarUserProvider, uploader storage.Uploader) http.Handler {
	return handler.NewAvatarUploadHandler(users, uploader, "test-bucket", "https://cdn.example.com")
}

// ─── method validation ────────────────────────────────────────────────────────

func TestAvatarUpload_WrongMethod_Returns405(t *testing.T) {
	users := &stubAvatarUserProvider{getUser: defaultAvatarUser()}
	h := avatarHandlerWithDefaults(users, &stubUploader{})

	req := httptest.NewRequest(http.MethodGet, "/api/me/avatar", nil)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", rec.Code)
	}
}

// ─── auth validation ──────────────────────────────────────────────────────────

func TestAvatarUpload_NoClaims_Returns401(t *testing.T) {
	users := &stubAvatarUserProvider{getUser: defaultAvatarUser()}
	h := avatarHandlerWithDefaults(users, &stubUploader{})

	// No claims injected — plain request without Authorization.
	req := buildMultipartRequest(t, "avatar", "image/jpeg", []byte("fake-jpeg"))
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rec.Code)
	}
}

// ─── user lookup ─────────────────────────────────────────────────────────────

func TestAvatarUpload_UserLookupError_Returns500(t *testing.T) {
	users := &stubAvatarUserProvider{getErr: errors.New("db error")}
	h := avatarHandlerWithDefaults(users, &stubUploader{})

	claims := &auth.TokenClaims{UID: "uid1", Email: "alice@example.com"}
	req := withClaims(buildMultipartRequest(t, "avatar", "image/jpeg", []byte("fake")), claims)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", rec.Code)
	}
}

func TestAvatarUpload_UserNotFound_Returns404(t *testing.T) {
	users := &stubAvatarUserProvider{getUser: nil}
	h := avatarHandlerWithDefaults(users, &stubUploader{})

	claims := &auth.TokenClaims{UID: "uid1", Email: "alice@example.com"}
	req := withClaims(buildMultipartRequest(t, "avatar", "image/jpeg", []byte("fake")), claims)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

// ─── MIME type validation ─────────────────────────────────────────────────────

func TestAvatarUpload_InvalidMIMEType_Returns400(t *testing.T) {
	users := &stubAvatarUserProvider{
		getUser:    defaultAvatarUser(),
		updateUser: defaultAvatarUser(),
	}
	h := avatarHandlerWithDefaults(users, &stubUploader{})

	claims := &auth.TokenClaims{UID: "uid1", Email: "alice@example.com"}
	req := withClaims(buildMultipartRequest(t, "avatar", "image/gif", []byte("fake-gif")), claims)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for gif, got %d", rec.Code)
	}
}

func TestAvatarUpload_VideoMIMEType_Returns400(t *testing.T) {
	users := &stubAvatarUserProvider{getUser: defaultAvatarUser()}
	h := avatarHandlerWithDefaults(users, &stubUploader{})

	claims := &auth.TokenClaims{UID: "uid1", Email: "alice@example.com"}
	req := withClaims(buildMultipartRequest(t, "avatar", "video/mp4", []byte("fake-video")), claims)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for video/mp4, got %d", rec.Code)
	}
}

func TestAvatarUpload_TextPlainMIMEType_Returns400(t *testing.T) {
	users := &stubAvatarUserProvider{getUser: defaultAvatarUser()}
	h := avatarHandlerWithDefaults(users, &stubUploader{})

	claims := &auth.TokenClaims{UID: "uid1", Email: "alice@example.com"}
	req := withClaims(buildMultipartRequest(t, "avatar", "text/plain", []byte("hello")), claims)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for text/plain, got %d", rec.Code)
	}
}

// ─── file size validation ─────────────────────────────────────────────────────

func TestAvatarUpload_FileTooLarge_Returns413(t *testing.T) {
	users := &stubAvatarUserProvider{getUser: defaultAvatarUser()}
	h := avatarHandlerWithDefaults(users, &stubUploader{})

	// 5 MB + 1 byte exceeds the limit.
	oversized := make([]byte, 5*1024*1024+1)
	claims := &auth.TokenClaims{UID: "uid1", Email: "alice@example.com"}
	req := withClaims(buildMultipartRequest(t, "avatar", "image/png", oversized), claims)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusRequestEntityTooLarge {
		t.Errorf("expected 413, got %d", rec.Code)
	}
}

func TestAvatarUpload_FileExactlyAtLimit_Returns200(t *testing.T) {
	users := &stubAvatarUserProvider{
		getUser:    defaultAvatarUser(),
		updateUser: defaultAvatarUser(),
	}
	h := avatarHandlerWithDefaults(users, &stubUploader{})

	// Exactly 5 MB — must be accepted.
	exactly5MB := make([]byte, 5*1024*1024)
	claims := &auth.TokenClaims{UID: "uid1", Email: "alice@example.com"}
	req := withClaims(buildMultipartRequest(t, "avatar", "image/jpeg", exactly5MB), claims)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200 for exactly 5 MB, got %d", rec.Code)
	}
}

// ─── missing avatar field ─────────────────────────────────────────────────────

func TestAvatarUpload_MissingAvatarField_Returns400(t *testing.T) {
	users := &stubAvatarUserProvider{getUser: defaultAvatarUser()}
	h := avatarHandlerWithDefaults(users, &stubUploader{})

	// Build a multipart form without the "avatar" field.
	var buf bytes.Buffer
	mw := multipart.NewWriter(&buf)
	_ = mw.WriteField("other", "value")
	mw.Close()
	req := httptest.NewRequest(http.MethodPost, "/api/me/avatar", &buf)
	req.Header.Set("Content-Type", mw.FormDataContentType())

	claims := &auth.TokenClaims{UID: "uid1", Email: "alice@example.com"}
	req = withClaims(req, claims)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400 when avatar field missing, got %d", rec.Code)
	}
}

// ─── GCS upload error ────────────────────────────────────────────────────────

func TestAvatarUpload_UploaderError_Returns500(t *testing.T) {
	users := &stubAvatarUserProvider{getUser: defaultAvatarUser()}
	uploader := &stubUploader{err: errors.New("gcs unreachable")}
	h := avatarHandlerWithDefaults(users, uploader)

	claims := &auth.TokenClaims{UID: "uid1", Email: "alice@example.com"}
	req := withClaims(buildMultipartRequest(t, "avatar", "image/jpeg", []byte("fake-jpeg")), claims)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500 on uploader error, got %d", rec.Code)
	}
}

// ─── DB update error ─────────────────────────────────────────────────────────

func TestAvatarUpload_UpdateAvatarURLError_Returns500(t *testing.T) {
	users := &stubAvatarUserProvider{
		getUser:   defaultAvatarUser(),
		updateErr: errors.New("db write error"),
	}
	h := avatarHandlerWithDefaults(users, &stubUploader{})

	claims := &auth.TokenClaims{UID: "uid1", Email: "alice@example.com"}
	req := withClaims(buildMultipartRequest(t, "avatar", "image/jpeg", []byte("fake-jpeg")), claims)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500 on DB update error, got %d", rec.Code)
	}
}

// ─── successful JPEG upload ───────────────────────────────────────────────────

func TestAvatarUpload_JPEG_Success(t *testing.T) {
	user := defaultAvatarUser()
	users := &stubAvatarUserProvider{getUser: user, updateUser: user}
	uploader := &stubUploader{}
	h := handler.NewAvatarUploadHandler(users, uploader, "my-bucket", "https://cdn.example.com")

	claims := &auth.TokenClaims{UID: "firebase-uid-1", Email: "alice@example.com"}
	req := withClaims(buildMultipartRequest(t, "avatar", "image/jpeg", []byte("fake-jpeg-data")), claims)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d — body: %s", rec.Code, rec.Body.String())
	}

	// Validate response body.
	var resp handler.AvatarUploadResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	wantURL := "https://cdn.example.com/avatars/00000000-0000-0000-0000-000000000001.jpg"
	if resp.AvatarURL != wantURL {
		t.Errorf("avatar_url: got %q, want %q", resp.AvatarURL, wantURL)
	}

	// Validate GCS upload arguments.
	if uploader.capturedBucket != "my-bucket" {
		t.Errorf("bucket: got %q, want %q", uploader.capturedBucket, "my-bucket")
	}
	wantObject := "avatars/00000000-0000-0000-0000-000000000001.jpg"
	if uploader.capturedObject != wantObject {
		t.Errorf("object: got %q, want %q", uploader.capturedObject, wantObject)
	}
	if uploader.capturedMIMEType != "image/jpeg" {
		t.Errorf("content-type: got %q, want %q", uploader.capturedMIMEType, "image/jpeg")
	}

	// Validate DB update call.
	if users.capturedUpdateUID != "firebase-uid-1" {
		t.Errorf("UpdateAvatarURL UID: got %q, want %q", users.capturedUpdateUID, "firebase-uid-1")
	}
	if users.capturedUpdateURL != wantURL {
		t.Errorf("UpdateAvatarURL URL: got %q, want %q", users.capturedUpdateURL, wantURL)
	}
}

// ─── successful PNG upload ────────────────────────────────────────────────────

func TestAvatarUpload_PNG_Success(t *testing.T) {
	user := defaultAvatarUser()
	users := &stubAvatarUserProvider{getUser: user, updateUser: user}
	uploader := &stubUploader{}
	h := handler.NewAvatarUploadHandler(users, uploader, "my-bucket", "https://cdn.example.com")

	claims := &auth.TokenClaims{UID: "firebase-uid-1", Email: "alice@example.com"}
	req := withClaims(buildMultipartRequest(t, "avatar", "image/png", []byte("fake-png-data")), claims)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var resp handler.AvatarUploadResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	wantURL := "https://cdn.example.com/avatars/00000000-0000-0000-0000-000000000001.png"
	if resp.AvatarURL != wantURL {
		t.Errorf("avatar_url: got %q, want %q", resp.AvatarURL, wantURL)
	}
	if uploader.capturedObject != "avatars/00000000-0000-0000-0000-000000000001.png" {
		t.Errorf("GCS object key: got %q", uploader.capturedObject)
	}
}

// ─── CDN URL trailing slash normalisation ─────────────────────────────────────

func TestAvatarUpload_CDNBaseURLTrailingSlash_IsNormalised(t *testing.T) {
	user := defaultAvatarUser()
	users := &stubAvatarUserProvider{getUser: user, updateUser: user}
	// cdnBaseURL has a trailing slash — the handler must strip it.
	h := handler.NewAvatarUploadHandler(users, &stubUploader{}, "bucket", "https://cdn.example.com/")

	claims := &auth.TokenClaims{UID: "firebase-uid-1", Email: "alice@example.com"}
	req := withClaims(buildMultipartRequest(t, "avatar", "image/jpeg", []byte("data")), claims)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}
	var resp handler.AvatarUploadResponse
	_ = json.NewDecoder(rec.Body).Decode(&resp)
	if strings.Contains(resp.AvatarURL, "//avatars") {
		t.Errorf("URL has double slash: %q", resp.AvatarURL)
	}
}

// ─── MIME type with parameters ────────────────────────────────────────────────

func TestAvatarUpload_MIMETypeWithParameters_IsAccepted(t *testing.T) {
	user := defaultAvatarUser()
	users := &stubAvatarUserProvider{getUser: user, updateUser: user}
	uploader := &stubUploader{}
	h := avatarHandlerWithDefaults(users, uploader)

	claims := &auth.TokenClaims{UID: "firebase-uid-1", Email: "alice@example.com"}
	// Content-Type includes a parameter — handler must strip it.
	req := withClaims(buildMultipartRequest(t, "avatar", "image/jpeg; charset=utf-8", []byte("data")), claims)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200 for MIME with params, got %d", rec.Code)
	}
	if uploader.capturedMIMEType != "image/jpeg" {
		t.Errorf("expected stripped MIME type 'image/jpeg', got %q", uploader.capturedMIMEType)
	}
}

// ─── Content-Type response header ─────────────────────────────────────────────

func TestAvatarUpload_Success_HasJSONContentType(t *testing.T) {
	user := defaultAvatarUser()
	users := &stubAvatarUserProvider{getUser: user, updateUser: user}
	h := avatarHandlerWithDefaults(users, &stubUploader{})

	claims := &auth.TokenClaims{UID: "firebase-uid-1", Email: "alice@example.com"}
	req := withClaims(buildMultipartRequest(t, "avatar", "image/jpeg", []byte("data")), claims)
	rec := serveAvatar(h, req)

	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type: got %q, want application/json", ct)
	}
}

// ─── non-multipart body ───────────────────────────────────────────────────────

func TestAvatarUpload_NonMultipartBody_Returns400(t *testing.T) {
	users := &stubAvatarUserProvider{getUser: defaultAvatarUser()}
	h := avatarHandlerWithDefaults(users, &stubUploader{})

	claims := &auth.TokenClaims{UID: "uid1", Email: "alice@example.com"}
	req := httptest.NewRequest(http.MethodPost, "/api/me/avatar", strings.NewReader("not-multipart"))
	req.Header.Set("Content-Type", "application/json")
	req = withClaims(req, claims)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for non-multipart body, got %d", rec.Code)
	}
}
