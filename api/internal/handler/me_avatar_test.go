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

// ─── magic-byte helpers ───────────────────────────────────────────────────────

// minimalJPEG returns a byte slice whose first bytes are a valid JPEG magic
// header so that http.DetectContentType identifies it as "image/jpeg".
func minimalJPEG() []byte {
	return []byte{0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01}
}

// minimalPNG returns a byte slice whose first bytes are the PNG signature so
// that http.DetectContentType identifies it as "image/png".
func minimalPNG() []byte {
	return []byte{0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a}
}

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

// TestAvatarUpload_SpoofedMIMEType_Returns400 verifies that a file with a
// spoofed Content-Type header (declares image/jpeg but contains plain text) is
// rejected by the magic-byte check even though the header MIME check passes.
func TestAvatarUpload_SpoofedMIMEType_Returns400(t *testing.T) {
	users := &stubAvatarUserProvider{getUser: defaultAvatarUser()}
	h := avatarHandlerWithDefaults(users, &stubUploader{})

	claims := &auth.TokenClaims{UID: "uid1", Email: "alice@example.com"}
	// Header says image/jpeg but body is plain text — magic-byte sniff must reject it.
	req := withClaims(buildMultipartRequest(t, "avatar", "image/jpeg", []byte("this is not an image")), claims)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for spoofed MIME type, got %d", rec.Code)
	}
}

// ─── file size validation ─────────────────────────────────────────────────────

func TestAvatarUpload_FileTooLarge_Returns413(t *testing.T) {
	users := &stubAvatarUserProvider{getUser: defaultAvatarUser()}
	h := avatarHandlerWithDefaults(users, &stubUploader{})

	// 5 MB + 1 byte with a valid PNG magic header — the size check must reject it.
	oversized := make([]byte, 5*1024*1024+1)
	copy(oversized, minimalPNG())
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

	// Exactly 5 MB starting with a valid JPEG magic header — must be accepted.
	exactly5MB := make([]byte, 5*1024*1024)
	copy(exactly5MB, minimalJPEG())
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
	req := withClaims(buildMultipartRequest(t, "avatar", "image/jpeg", minimalJPEG()), claims)
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
	req := withClaims(buildMultipartRequest(t, "avatar", "image/jpeg", minimalJPEG()), claims)
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
	req := withClaims(buildMultipartRequest(t, "avatar", "image/jpeg", minimalJPEG()), claims)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d — body: %s", rec.Code, rec.Body.String())
	}

	// Validate response body.
	var resp handler.AvatarUploadResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	wantPrefix := "https://cdn.example.com/avatars/00000000-0000-0000-0000-000000000001/"
	wantSuffix := ".jpg"
	if !strings.HasPrefix(resp.AvatarURL, wantPrefix) || !strings.HasSuffix(resp.AvatarURL, wantSuffix) {
		t.Errorf("avatar_url: got %q, want prefix %q and suffix %q", resp.AvatarURL, wantPrefix, wantSuffix)
	}

	// Validate GCS upload arguments.
	if uploader.capturedBucket != "my-bucket" {
		t.Errorf("bucket: got %q, want %q", uploader.capturedBucket, "my-bucket")
	}
	wantObjectPrefix := "avatars/00000000-0000-0000-0000-000000000001/"
	wantObjectSuffix := ".jpg"
	if !strings.HasPrefix(uploader.capturedObject, wantObjectPrefix) || !strings.HasSuffix(uploader.capturedObject, wantObjectSuffix) {
		t.Errorf("object key: got %q, want prefix %q and suffix %q", uploader.capturedObject, wantObjectPrefix, wantObjectSuffix)
	}
	if uploader.capturedMIMEType != "image/jpeg" {
		t.Errorf("content-type: got %q, want %q", uploader.capturedMIMEType, "image/jpeg")
	}

	// Validate DB update call.
	if users.capturedUpdateUID != "firebase-uid-1" {
		t.Errorf("UpdateAvatarURL UID: got %q, want %q", users.capturedUpdateUID, "firebase-uid-1")
	}
	if users.capturedUpdateURL != resp.AvatarURL {
		t.Errorf("UpdateAvatarURL URL: got %q, want same as response %q", users.capturedUpdateURL, resp.AvatarURL)
	}
}

// ─── successful PNG upload ────────────────────────────────────────────────────

func TestAvatarUpload_PNG_Success(t *testing.T) {
	user := defaultAvatarUser()
	users := &stubAvatarUserProvider{getUser: user, updateUser: user}
	uploader := &stubUploader{}
	h := handler.NewAvatarUploadHandler(users, uploader, "my-bucket", "https://cdn.example.com")

	claims := &auth.TokenClaims{UID: "firebase-uid-1", Email: "alice@example.com"}
	req := withClaims(buildMultipartRequest(t, "avatar", "image/png", minimalPNG()), claims)
	rec := serveAvatar(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var resp handler.AvatarUploadResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	wantPrefix := "https://cdn.example.com/avatars/00000000-0000-0000-0000-000000000001/"
	wantSuffix := ".png"
	if !strings.HasPrefix(resp.AvatarURL, wantPrefix) || !strings.HasSuffix(resp.AvatarURL, wantSuffix) {
		t.Errorf("avatar_url: got %q, want prefix %q and suffix %q", resp.AvatarURL, wantPrefix, wantSuffix)
	}
	if !strings.HasPrefix(uploader.capturedObject, "avatars/00000000-0000-0000-0000-000000000001/") ||
		!strings.HasSuffix(uploader.capturedObject, ".png") {
		t.Errorf("GCS object key: got %q — expected prefix avatars/<id>/ and suffix .png", uploader.capturedObject)
	}
}

// ─── CDN URL trailing slash normalisation ─────────────────────────────────────

func TestAvatarUpload_CDNBaseURLTrailingSlash_IsNormalised(t *testing.T) {
	user := defaultAvatarUser()
	users := &stubAvatarUserProvider{getUser: user, updateUser: user}
	// cdnBaseURL has a trailing slash — the handler must strip it.
	h := handler.NewAvatarUploadHandler(users, &stubUploader{}, "bucket", "https://cdn.example.com/")

	claims := &auth.TokenClaims{UID: "firebase-uid-1", Email: "alice@example.com"}
	req := withClaims(buildMultipartRequest(t, "avatar", "image/jpeg", minimalJPEG()), claims)
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
	req := withClaims(buildMultipartRequest(t, "avatar", "image/jpeg; charset=utf-8", minimalJPEG()), claims)
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
	req := withClaims(buildMultipartRequest(t, "avatar", "image/jpeg", minimalJPEG()), claims)
	rec := serveAvatar(h, req)

	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type: got %q, want application/json", ct)
	}
}

// ─── cache-busting: unique object key per upload ─────────────────────────────

// TestAvatarUpload_ObjectKeyIsUniquePerUpload verifies that two consecutive
// uploads of the same file type produce different GCS object keys (and thus
// different CDN URLs), preventing browser/CDN cache hits on the old image.
func TestAvatarUpload_ObjectKeyIsUniquePerUpload(t *testing.T) {
	user := defaultAvatarUser()
	users := &stubAvatarUserProvider{getUser: user, updateUser: user}

	uploader1 := &stubUploader{}
	h1 := handler.NewAvatarUploadHandler(users, uploader1, "my-bucket", "https://cdn.example.com")
	claims := &auth.TokenClaims{UID: "firebase-uid-1", Email: "alice@example.com"}
	req1 := withClaims(buildMultipartRequest(t, "avatar", "image/jpeg", minimalJPEG()), claims)
	rec1 := serveAvatar(h1, req1)
	if rec1.Code != http.StatusOK {
		t.Fatalf("first upload: expected 200, got %d", rec1.Code)
	}

	uploader2 := &stubUploader{}
	h2 := handler.NewAvatarUploadHandler(users, uploader2, "my-bucket", "https://cdn.example.com")
	req2 := withClaims(buildMultipartRequest(t, "avatar", "image/jpeg", minimalJPEG()), claims)
	rec2 := serveAvatar(h2, req2)
	if rec2.Code != http.StatusOK {
		t.Fatalf("second upload: expected 200, got %d", rec2.Code)
	}

	if uploader1.capturedObject == uploader2.capturedObject {
		t.Errorf("two uploads of the same type produced identical GCS object keys %q — cache busting broken",
			uploader1.capturedObject)
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
