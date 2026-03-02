package handler_test

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/ai-teammate/mytube/api/internal/auth"
	"github.com/ai-teammate/mytube/api/internal/handler"
	"github.com/ai-teammate/mytube/api/internal/repository"
	"github.com/ai-teammate/mytube/api/internal/storage"
)

// ─── stubs ────────────────────────────────────────────────────────────────────

// stubVideoCreator is a VideoCreator stub.
type stubVideoCreator struct {
	record *repository.VideoRecord
	err    error
}

func (s *stubVideoCreator) Create(_ context.Context, _ repository.CreateVideoParams) (*repository.VideoRecord, error) {
	return s.record, s.err
}

// stubUserIDProvider is a UserIDProvider stub.
type stubUserIDProvider struct {
	user *repository.User
	err  error
}

func (s *stubUserIDProvider) GetByFirebaseUID(_ context.Context, _ string) (*repository.User, error) {
	return s.user, s.err
}

// stubStorageSigner is a storage.Signer stub.
type stubStorageSigner struct {
	url string
	err error
	// capturedOpts records the last call's options.
	capturedOpts storage.SignedURLOptions
}

func (s *stubStorageSigner) SignPutURL(_ context.Context, opts storage.SignedURLOptions) (string, error) {
	s.capturedOpts = opts
	return s.url, s.err
}

// ─── helper ───────────────────────────────────────────────────────────────────

// defaultUser returns a typical authenticated user.
func defaultUser() *repository.User {
	return &repository.User{
		ID:          "00000000-0000-0000-0000-000000000001",
		FirebaseUID: "firebase-uid-1",
		Username:    "alice",
	}
}

// defaultVideoRecord returns a typical created video.
func defaultVideoRecord() *repository.VideoRecord {
	return &repository.VideoRecord{
		ID:         "00000000-0000-0000-0000-000000000099",
		UploaderID: "00000000-0000-0000-0000-000000000001",
		Title:      "My Video",
		Status:     "pending",
		CreatedAt:  time.Now(),
	}
}

// buildVideosHandler wires the injectable constructor so tests bypass
// os.Getenv("RAW_UPLOADS_BUCKET").
func buildVideosHandler(videos handler.VideoCreator, users handler.UserIDProvider, signer storage.Signer) http.Handler {
	// Use the exported constructor; bucket name comes from env.
	// In tests we call the package-level helper that passes bucket directly.
	// Since newVideosHandlerWithBucket is unexported, we use
	// NewVideosHandler and just set the env var to a test value.
	// Actually we use the exported constructor and set the env var.
	// See handler package: NewVideosHandler reads RAW_UPLOADS_BUCKET from env.
	return handler.NewVideosHandler(videos, users, signer)
}

func serveVideos(h http.Handler, r *http.Request) *httptest.ResponseRecorder {
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, r)
	return rec
}

// ─── POST /api/videos tests ───────────────────────────────────────────────────

func TestNewVideosHandler_POST_NoClaims_Returns401(t *testing.T) {
	h := buildVideosHandler(
		&stubVideoCreator{},
		&stubUserIDProvider{user: defaultUser()},
		&stubStorageSigner{url: "https://signed.url"},
	)

	body := `{"title":"My Video","mime_type":"video/mp4"}`
	req := httptest.NewRequest(http.MethodPost, "/api/videos", bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	rec := serveVideos(h, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rec.Code)
	}
}

func TestNewVideosHandler_GET_Returns405(t *testing.T) {
	h := buildVideosHandler(
		&stubVideoCreator{},
		&stubUserIDProvider{user: defaultUser()},
		&stubStorageSigner{url: "https://signed.url"},
	)

	req := httptest.NewRequest(http.MethodGet, "/api/videos", nil)
	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req = withClaims(req, claims)
	rec := serveVideos(h, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405 for GET, got %d", rec.Code)
	}
}

func TestNewVideosHandler_POST_InvalidJSON_Returns400(t *testing.T) {
	h := buildVideosHandler(
		&stubVideoCreator{},
		&stubUserIDProvider{user: defaultUser()},
		&stubStorageSigner{url: "https://signed.url"},
	)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos", bytes.NewBufferString("not-json")),
		claims,
	)
	rec := serveVideos(h, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400 on invalid JSON, got %d", rec.Code)
	}
}

func TestNewVideosHandler_POST_EmptyTitle_Returns422(t *testing.T) {
	h := buildVideosHandler(
		&stubVideoCreator{},
		&stubUserIDProvider{user: defaultUser()},
		&stubStorageSigner{url: "https://signed.url"},
	)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos",
			bytes.NewBufferString(`{"title":"","mime_type":"video/mp4"}`)),
		claims,
	)
	rec := serveVideos(h, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("expected 422 on empty title, got %d", rec.Code)
	}
}

func TestNewVideosHandler_POST_WhitespaceTitleOnly_Returns422(t *testing.T) {
	h := buildVideosHandler(
		&stubVideoCreator{},
		&stubUserIDProvider{user: defaultUser()},
		&stubStorageSigner{url: "https://signed.url"},
	)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos",
			bytes.NewBufferString(`{"title":"   ","mime_type":"video/mp4"}`)),
		claims,
	)
	rec := serveVideos(h, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("expected 422 on whitespace-only title, got %d", rec.Code)
	}
}

func TestNewVideosHandler_POST_TitleTooLong_Returns422(t *testing.T) {
	h := buildVideosHandler(
		&stubVideoCreator{},
		&stubUserIDProvider{user: defaultUser()},
		&stubStorageSigner{url: "https://signed.url"},
	)

	longTitle := make([]byte, 256)
	for i := range longTitle {
		longTitle[i] = 'a'
	}
	body, _ := json.Marshal(map[string]string{
		"title":     string(longTitle),
		"mime_type": "video/mp4",
	})
	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos", bytes.NewBuffer(body)),
		claims,
	)
	rec := serveVideos(h, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("expected 422 on 256-char title, got %d", rec.Code)
	}
}

func TestNewVideosHandler_POST_Title255Chars_Accepted(t *testing.T) {
	t.Setenv("RAW_UPLOADS_BUCKET", "test-bucket")
	h := buildVideosHandler(
		&stubVideoCreator{record: defaultVideoRecord()},
		&stubUserIDProvider{user: defaultUser()},
		&stubStorageSigner{url: "https://signed.url"},
	)

	title255 := make([]byte, 255)
	for i := range title255 {
		title255[i] = 'a'
	}
	body, _ := json.Marshal(map[string]string{
		"title":     string(title255),
		"mime_type": "video/mp4",
	})
	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos", bytes.NewBuffer(body)),
		claims,
	)
	rec := serveVideos(h, req)

	if rec.Code != http.StatusCreated {
		t.Errorf("expected 201 for 255-char title, got %d: %s", rec.Code, rec.Body.String())
	}
}

func TestNewVideosHandler_POST_MissingMIMEType_Returns422(t *testing.T) {
	h := buildVideosHandler(
		&stubVideoCreator{},
		&stubUserIDProvider{user: defaultUser()},
		&stubStorageSigner{url: "https://signed.url"},
	)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos",
			bytes.NewBufferString(`{"title":"My Video"}`)),
		claims,
	)
	rec := serveVideos(h, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("expected 422 on missing mime_type, got %d", rec.Code)
	}
}

func TestNewVideosHandler_POST_UnsupportedMIMEType_Returns422(t *testing.T) {
	h := buildVideosHandler(
		&stubVideoCreator{},
		&stubUserIDProvider{user: defaultUser()},
		&stubStorageSigner{url: "https://signed.url"},
	)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos",
			bytes.NewBufferString(`{"title":"My Video","mime_type":"image/jpeg"}`)),
		claims,
	)
	rec := serveVideos(h, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("expected 422 on unsupported mime type, got %d", rec.Code)
	}
}

func TestNewVideosHandler_POST_AcceptedMIMETypes(t *testing.T) {
	t.Setenv("RAW_UPLOADS_BUCKET", "test-bucket")
	mimeTypes := []string{"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"}

	for _, mimeType := range mimeTypes {
		t.Run(mimeType, func(t *testing.T) {
			h := buildVideosHandler(
				&stubVideoCreator{record: defaultVideoRecord()},
				&stubUserIDProvider{user: defaultUser()},
				&stubStorageSigner{url: "https://signed.url"},
			)
			body, _ := json.Marshal(map[string]string{
				"title":     "My Video",
				"mime_type": mimeType,
			})
			claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
			req := withClaims(
				httptest.NewRequest(http.MethodPost, "/api/videos", bytes.NewBuffer(body)),
				claims,
			)
			rec := serveVideos(h, req)
			if rec.Code != http.StatusCreated {
				t.Errorf("expected 201 for mime_type %q, got %d", mimeType, rec.Code)
			}
		})
	}
}

func TestNewVideosHandler_POST_MIMETypeWithParams_Accepted(t *testing.T) {
	t.Setenv("RAW_UPLOADS_BUCKET", "test-bucket")
	h := buildVideosHandler(
		&stubVideoCreator{record: defaultVideoRecord()},
		&stubUserIDProvider{user: defaultUser()},
		&stubStorageSigner{url: "https://signed.url"},
	)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos",
			bytes.NewBufferString(`{"title":"My Video","mime_type":"video/mp4; codecs=avc1"}`)),
		claims,
	)
	rec := serveVideos(h, req)

	if rec.Code != http.StatusCreated {
		t.Errorf("expected 201 for MIME type with params, got %d", rec.Code)
	}
}

func TestNewVideosHandler_POST_GetUserError_Returns500(t *testing.T) {
	dbErr := errors.New("db error")
	h := buildVideosHandler(
		&stubVideoCreator{},
		&stubUserIDProvider{err: dbErr},
		&stubStorageSigner{url: "https://signed.url"},
	)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos",
			bytes.NewBufferString(`{"title":"My Video","mime_type":"video/mp4"}`)),
		claims,
	)
	rec := serveVideos(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500 on user lookup error, got %d", rec.Code)
	}
}

func TestNewVideosHandler_POST_UserNotFound_Returns404(t *testing.T) {
	h := buildVideosHandler(
		&stubVideoCreator{},
		&stubUserIDProvider{user: nil},
		&stubStorageSigner{url: "https://signed.url"},
	)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos",
			bytes.NewBufferString(`{"title":"My Video","mime_type":"video/mp4"}`)),
		claims,
	)
	rec := serveVideos(h, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404 when user not found, got %d", rec.Code)
	}
}

func TestNewVideosHandler_POST_CreateVideoError_Returns500(t *testing.T) {
	dbErr := errors.New("insert failed")
	h := buildVideosHandler(
		&stubVideoCreator{err: dbErr},
		&stubUserIDProvider{user: defaultUser()},
		&stubStorageSigner{url: "https://signed.url"},
	)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos",
			bytes.NewBufferString(`{"title":"My Video","mime_type":"video/mp4"}`)),
		claims,
	)
	rec := serveVideos(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500 on create video error, got %d", rec.Code)
	}
}

func TestNewVideosHandler_POST_SignURLError_Returns500(t *testing.T) {
	t.Setenv("RAW_UPLOADS_BUCKET", "test-bucket")
	sigErr := errors.New("sign failed")
	h := buildVideosHandler(
		&stubVideoCreator{record: defaultVideoRecord()},
		&stubUserIDProvider{user: defaultUser()},
		&stubStorageSigner{err: sigErr},
	)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos",
			bytes.NewBufferString(`{"title":"My Video","mime_type":"video/mp4"}`)),
		claims,
	)
	rec := serveVideos(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500 on sign URL error, got %d", rec.Code)
	}
}

func TestNewVideosHandler_POST_Success_Returns201WithVideoIDAndUploadURL(t *testing.T) {
	t.Setenv("RAW_UPLOADS_BUCKET", "test-bucket")
	video := defaultVideoRecord()
	signedURL := "https://storage.googleapis.com/test-bucket/raw/uid/video-id?X-Goog-Signature=xyz"

	h := buildVideosHandler(
		&stubVideoCreator{record: video},
		&stubUserIDProvider{user: defaultUser()},
		&stubStorageSigner{url: signedURL},
	)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos",
			bytes.NewBufferString(`{"title":"My Video","mime_type":"video/mp4"}`)),
		claims,
	)
	rec := serveVideos(h, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", rec.Code, rec.Body.String())
	}

	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type: got %q, want %q", ct, "application/json")
	}

	var resp handler.CreateVideoResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("could not decode response: %v", err)
	}
	if resp.VideoID != video.ID {
		t.Errorf("video_id: got %q, want %q", resp.VideoID, video.ID)
	}
	if resp.UploadURL != signedURL {
		t.Errorf("upload_url: got %q, want %q", resp.UploadURL, signedURL)
	}
}

func TestNewVideosHandler_POST_SignerReceivesCorrectBucket(t *testing.T) {
	t.Setenv("RAW_UPLOADS_BUCKET", "my-raw-bucket")
	video := defaultVideoRecord()
	signer := &stubStorageSigner{url: "https://signed.url"}

	h := buildVideosHandler(
		&stubVideoCreator{record: video},
		&stubUserIDProvider{user: defaultUser()},
		signer,
	)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos",
			bytes.NewBufferString(`{"title":"My Video","mime_type":"video/mp4"}`)),
		claims,
	)
	serveVideos(h, req)

	if signer.capturedOpts.Bucket != "my-raw-bucket" {
		t.Errorf("signer Bucket: got %q, want %q", signer.capturedOpts.Bucket, "my-raw-bucket")
	}
}

func TestNewVideosHandler_POST_SignerReceivesObjectPathWithUserAndVideoID(t *testing.T) {
	t.Setenv("RAW_UPLOADS_BUCKET", "test-bucket")
	user := defaultUser()
	video := defaultVideoRecord()
	signer := &stubStorageSigner{url: "https://signed.url"}

	h := buildVideosHandler(
		&stubVideoCreator{record: video},
		&stubUserIDProvider{user: user},
		signer,
	)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos",
			bytes.NewBufferString(`{"title":"My Video","mime_type":"video/mp4"}`)),
		claims,
	)
	serveVideos(h, req)

	expectedObject := "raw/" + user.ID + "/" + video.ID
	if signer.capturedOpts.Object != expectedObject {
		t.Errorf("signer Object: got %q, want %q", signer.capturedOpts.Object, expectedObject)
	}
}

func TestNewVideosHandler_POST_SignerReceivesNormalisedContentType(t *testing.T) {
	t.Setenv("RAW_UPLOADS_BUCKET", "test-bucket")
	signer := &stubStorageSigner{url: "https://signed.url"}

	h := buildVideosHandler(
		&stubVideoCreator{record: defaultVideoRecord()},
		&stubUserIDProvider{user: defaultUser()},
		signer,
	)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos",
			bytes.NewBufferString(`{"title":"My Video","mime_type":"video/mp4; codecs=avc1"}`)),
		claims,
	)
	serveVideos(h, req)

	if signer.capturedOpts.ContentType != "video/mp4" {
		t.Errorf("ContentType: got %q, want %q", signer.capturedOpts.ContentType, "video/mp4")
	}
}

func TestNewVideosHandler_POST_WithCategoryAndTags(t *testing.T) {
	t.Setenv("RAW_UPLOADS_BUCKET", "test-bucket")
	catID := 2
	desc := "A great video"

	var capturedParams repository.CreateVideoParams
	recordingCreator := &recordingVideoCreator{
		onCreateFunc: func(p repository.CreateVideoParams) (*repository.VideoRecord, error) {
			capturedParams = p
			rawPath := "raw/u/v"
			return &repository.VideoRecord{
				ID:         "vid-capture",
				UploaderID: p.UploaderID,
				Title:      p.Title,
				Status:     "pending",
				GCSRawPath: &rawPath,
				CreatedAt:  time.Now(),
			}, nil
		},
	}

	h := buildVideosHandler(
		recordingCreator,
		&stubUserIDProvider{user: defaultUser()},
		&stubStorageSigner{url: "https://signed.url"},
	)

	body, _ := json.Marshal(map[string]interface{}{
		"title":       "My Video",
		"description": desc,
		"category_id": catID,
		"tags":        []string{"golang", "programming"},
		"mime_type":   "video/mp4",
	})
	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos", bytes.NewBuffer(body)),
		claims,
	)
	rec := serveVideos(h, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", rec.Code, rec.Body.String())
	}
	if capturedParams.CategoryID == nil || *capturedParams.CategoryID != catID {
		t.Errorf("CategoryID: got %v, want %d", capturedParams.CategoryID, catID)
	}
	if capturedParams.Description == nil || *capturedParams.Description != desc {
		t.Errorf("Description: got %v, want %q", capturedParams.Description, desc)
	}
	if len(capturedParams.Tags) != 2 {
		t.Errorf("Tags: got %v, want 2 tags", capturedParams.Tags)
	}
}

func TestNewVideosHandler_POST_DeduplicatesTags(t *testing.T) {
	t.Setenv("RAW_UPLOADS_BUCKET", "test-bucket")
	var capturedParams repository.CreateVideoParams
	recordingCreator := &recordingVideoCreator{
		onCreateFunc: func(p repository.CreateVideoParams) (*repository.VideoRecord, error) {
			capturedParams = p
			rawPath := "raw/u/v"
			return &repository.VideoRecord{
				ID:         "vid-dedup",
				UploaderID: p.UploaderID,
				Title:      p.Title,
				Status:     "pending",
				GCSRawPath: &rawPath,
				CreatedAt:  time.Now(),
			}, nil
		},
	}

	h := buildVideosHandler(
		recordingCreator,
		&stubUserIDProvider{user: defaultUser()},
		&stubStorageSigner{url: "https://signed.url"},
	)

	body, _ := json.Marshal(map[string]interface{}{
		"title":     "My Video",
		"tags":      []string{"go", "go", "programming"},
		"mime_type": "video/mp4",
	})
	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos", bytes.NewBuffer(body)),
		claims,
	)
	serveVideos(h, req)

	// "go" appears twice but should be deduplicated to 1
	if len(capturedParams.Tags) != 2 {
		t.Errorf("Tags after dedup: got %v, want 2 tags (go, programming)", capturedParams.Tags)
	}
}

func TestNewVideosHandler_POST_EmptyDescriptionNotStored(t *testing.T) {
	t.Setenv("RAW_UPLOADS_BUCKET", "test-bucket")
	var capturedParams repository.CreateVideoParams
	recordingCreator := &recordingVideoCreator{
		onCreateFunc: func(p repository.CreateVideoParams) (*repository.VideoRecord, error) {
			capturedParams = p
			rawPath := "raw/u/v"
			return &repository.VideoRecord{
				ID:         "vid-nodesc",
				UploaderID: p.UploaderID,
				Title:      p.Title,
				Status:     "pending",
				GCSRawPath: &rawPath,
				CreatedAt:  time.Now(),
			}, nil
		},
	}

	h := buildVideosHandler(
		recordingCreator,
		&stubUserIDProvider{user: defaultUser()},
		&stubStorageSigner{url: "https://signed.url"},
	)

	body := `{"title":"My Video","description":"","mime_type":"video/mp4"}`
	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPost, "/api/videos", bytes.NewBufferString(body)),
		claims,
	)
	serveVideos(h, req)

	if capturedParams.Description != nil {
		t.Errorf("expected nil Description for empty string, got %q", *capturedParams.Description)
	}
}

// recordingVideoCreator captures Create call arguments.
type recordingVideoCreator struct {
	onCreateFunc func(p repository.CreateVideoParams) (*repository.VideoRecord, error)
}

func (r *recordingVideoCreator) Create(_ context.Context, p repository.CreateVideoParams) (*repository.VideoRecord, error) {
	if r.onCreateFunc != nil {
		return r.onCreateFunc(p)
	}
	rawPath := "raw/u/v"
	return &repository.VideoRecord{
		ID:         "default-vid",
		UploaderID: p.UploaderID,
		Title:      p.Title,
		Status:     "pending",
		GCSRawPath: &rawPath,
		CreatedAt:  time.Now(),
	}, nil
}
