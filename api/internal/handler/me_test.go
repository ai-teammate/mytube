package handler_test

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/ai-teammate/mytube/api/internal/auth"
	"github.com/ai-teammate/mytube/api/internal/handler"
	"github.com/ai-teammate/mytube/api/internal/middleware"
	"github.com/ai-teammate/mytube/api/internal/repository"
)

// ─── stub UserProvider ────────────────────────────────────────────────────────

type stubUserProvider struct {
	user          *repository.User
	err           error
	updateUser    *repository.User
	updateErr     error
}

func (s *stubUserProvider) Upsert(_ context.Context, _, _, _ string) (*repository.User, error) {
	return s.user, s.err
}

func (s *stubUserProvider) UpdateProfile(_ context.Context, _, _ string, _ *string) (*repository.User, error) {
	return s.updateUser, s.updateErr
}

// ─── helpers ──────────────────────────────────────────────────────────────────

// withClaims injects *auth.TokenClaims into a request's context, mimicking
// what RequireAuth middleware does.
func withClaims(r *http.Request, claims *auth.TokenClaims) *http.Request {
	// Use the exported middleware.RequireAuth path to inject claims by wiring a
	// stub verifier and re-running the middleware inline.
	stubV := &stubTokenVerifier{claims: claims}
	var req *http.Request
	inner := http.HandlerFunc(func(_ http.ResponseWriter, r2 *http.Request) {
		req = r2
	})
	w := httptest.NewRecorder()
	r.Header.Set("Authorization", "Bearer stub.token")
	middleware.RequireAuth(stubV)(inner).ServeHTTP(w, r)
	if req == nil {
		return r // fallback (should not happen in tests)
	}
	return req
}

// stubTokenVerifier is a minimal auth.TokenVerifier for withClaims.
type stubTokenVerifier struct {
	claims *auth.TokenClaims
}

func (s *stubTokenVerifier) VerifyIDToken(_ context.Context, _ string) (*auth.TokenClaims, error) {
	return s.claims, nil
}

// serveMe is a helper that calls the me handler directly via ServeHTTP.
func serveMe(h http.Handler, r *http.Request) *httptest.ResponseRecorder {
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, r)
	return rec
}

// ─── GET /api/me tests ────────────────────────────────────────────────────────

func TestNewMeHandler_GET_NoClaims_Returns401(t *testing.T) {
	users := &stubUserProvider{user: &repository.User{ID: "u1", Username: "alice"}}
	h := handler.NewMeHandler(users)

	req := httptest.NewRequest(http.MethodGet, "/api/me", nil)
	// No claims injected into context.
	rec := serveMe(h, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401 when no claims in context, got %d", rec.Code)
	}
}

func TestNewMeHandler_GET_UpsertError_Returns500(t *testing.T) {
	dbErr := errors.New("database error")
	users := &stubUserProvider{err: dbErr}
	h := handler.NewMeHandler(users)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(httptest.NewRequest(http.MethodGet, "/api/me", nil), claims)
	rec := serveMe(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500 on upsert error, got %d", rec.Code)
	}
}

func TestNewMeHandler_GET_UserNotFoundAfterUpsert_Returns500(t *testing.T) {
	// Upsert returns (nil, nil) — provisioning succeeded but row not visible.
	users := &stubUserProvider{user: nil, err: nil}
	h := handler.NewMeHandler(users)

	claims := &auth.TokenClaims{UID: "uid2", Email: "user@example.com"}
	req := withClaims(httptest.NewRequest(http.MethodGet, "/api/me", nil), claims)
	rec := serveMe(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500 when user row missing after upsert, got %d", rec.Code)
	}
}

func TestNewMeHandler_GET_Success_ReturnsUserJSON(t *testing.T) {
	avatarURL := "https://example.com/avatar.png"
	user := &repository.User{
		ID:        "00000000-0000-0000-0000-000000000001",
		Username:  "alice",
		AvatarURL: &avatarURL,
	}
	users := &stubUserProvider{user: user}
	h := handler.NewMeHandler(users)

	claims := &auth.TokenClaims{UID: "uid3", Email: "alice@example.com"}
	req := withClaims(httptest.NewRequest(http.MethodGet, "/api/me", nil), claims)
	rec := serveMe(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("expected Content-Type application/json, got %q", ct)
	}

	var body handler.MeResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("could not decode response: %v", err)
	}
	if body.ID != user.ID {
		t.Errorf("ID: got %q, want %q", body.ID, user.ID)
	}
	if body.Username != user.Username {
		t.Errorf("Username: got %q, want %q", body.Username, user.Username)
	}
	if body.AvatarURL == nil || *body.AvatarURL != avatarURL {
		t.Errorf("AvatarURL: got %v, want %q", body.AvatarURL, avatarURL)
	}
}

func TestNewMeHandler_GET_Success_NilAvatarURL(t *testing.T) {
	user := &repository.User{
		ID:        "00000000-0000-0000-0000-000000000002",
		Username:  "bob",
		AvatarURL: nil,
	}
	users := &stubUserProvider{user: user}
	h := handler.NewMeHandler(users)

	claims := &auth.TokenClaims{UID: "uid4", Email: "bob@example.com"}
	req := withClaims(httptest.NewRequest(http.MethodGet, "/api/me", nil), claims)
	rec := serveMe(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var body handler.MeResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("could not decode response: %v", err)
	}
	if body.AvatarURL != nil {
		t.Errorf("expected null avatar_url, got %q", *body.AvatarURL)
	}
}

func TestNewMeHandler_GET_UsesFirebaseUIDFromClaims(t *testing.T) {
	// Verify that the handler passes the firebase UID from claims to Upsert.
	// We capture the call via a recording stub.

	var gotUID, gotEmail string
	recordingStub := &recordingUserProvider{
		onUpsert: func(firebaseUID, email string) (*repository.User, error) {
			gotUID = firebaseUID
			gotEmail = email
			return &repository.User{ID: "u5", Username: "eve"}, nil
		},
	}

	h := handler.NewMeHandler(recordingStub)
	claims := &auth.TokenClaims{UID: "firebase-uid-captured", Email: "eve@domain.com"}
	req := withClaims(httptest.NewRequest(http.MethodGet, "/api/me", nil), claims)
	rec := serveMe(h, req)
	_ = rec

	if gotUID != claims.UID {
		t.Errorf("Upsert called with UID %q, want %q", gotUID, claims.UID)
	}
	if gotEmail != claims.Email {
		t.Errorf("Upsert called with email %q, want %q", gotEmail, claims.Email)
	}
}

// ─── PUT /api/me tests ────────────────────────────────────────────────────────

func TestNewMeHandler_PUT_NoClaims_Returns401(t *testing.T) {
	users := &stubUserProvider{}
	h := handler.NewMeHandler(users)

	body := `{"username":"alice"}`
	req := httptest.NewRequest(http.MethodPut, "/api/me", bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	rec := serveMe(h, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401 when no claims, got %d", rec.Code)
	}
}

func TestNewMeHandler_PUT_InvalidJSON_Returns400(t *testing.T) {
	users := &stubUserProvider{}
	h := handler.NewMeHandler(users)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/me", bytes.NewBufferString("not-json")),
		claims,
	)
	req.Header.Set("Content-Type", "application/json")
	rec := serveMe(h, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400 on invalid JSON, got %d", rec.Code)
	}
}

func TestNewMeHandler_PUT_EmptyUsername_Returns422(t *testing.T) {
	users := &stubUserProvider{}
	h := handler.NewMeHandler(users)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/me", bytes.NewBufferString(`{"username":""}`)),
		claims,
	)
	req.Header.Set("Content-Type", "application/json")
	rec := serveMe(h, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("expected 422 on empty username, got %d", rec.Code)
	}
}

func TestNewMeHandler_PUT_WhitespaceOnlyUsername_Returns422(t *testing.T) {
	users := &stubUserProvider{}
	h := handler.NewMeHandler(users)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/me", bytes.NewBufferString(`{"username":"   "}`)),
		claims,
	)
	req.Header.Set("Content-Type", "application/json")
	rec := serveMe(h, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("expected 422 on whitespace-only username, got %d", rec.Code)
	}
}

func TestNewMeHandler_PUT_UpdateProfileError_Returns500(t *testing.T) {
	dbErr := errors.New("db error")
	users := &stubUserProvider{updateErr: dbErr}
	h := handler.NewMeHandler(users)

	claims := &auth.TokenClaims{UID: "uid2", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/me", bytes.NewBufferString(`{"username":"alice"}`)),
		claims,
	)
	req.Header.Set("Content-Type", "application/json")
	rec := serveMe(h, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500 on update error, got %d", rec.Code)
	}
}

func TestNewMeHandler_PUT_UserNotFound_Returns404(t *testing.T) {
	// UpdateProfile returns (nil, nil) — user row not found.
	users := &stubUserProvider{updateUser: nil, updateErr: nil}
	h := handler.NewMeHandler(users)

	claims := &auth.TokenClaims{UID: "uid3", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/me", bytes.NewBufferString(`{"username":"alice"}`)),
		claims,
	)
	req.Header.Set("Content-Type", "application/json")
	rec := serveMe(h, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404 when user not found, got %d", rec.Code)
	}
}

func TestNewMeHandler_PUT_Success_ReturnsUpdatedUser(t *testing.T) {
	avatarURL := "https://example.com/new-avatar.png"
	updated := &repository.User{
		ID:        "00000000-0000-0000-0000-000000000001",
		Username:  "newalice",
		AvatarURL: &avatarURL,
	}
	users := &stubUserProvider{updateUser: updated}
	h := handler.NewMeHandler(users)

	bodyStr := `{"username":"newalice","avatar_url":"https://example.com/new-avatar.png"}`
	claims := &auth.TokenClaims{UID: "uid4", Email: "alice@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/me", bytes.NewBufferString(bodyStr)),
		claims,
	)
	req.Header.Set("Content-Type", "application/json")
	rec := serveMe(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("expected Content-Type application/json, got %q", ct)
	}

	var respBody handler.MeResponse
	if err := json.NewDecoder(rec.Body).Decode(&respBody); err != nil {
		t.Fatalf("could not decode response: %v", err)
	}
	if respBody.Username != "newalice" {
		t.Errorf("Username: got %q, want %q", respBody.Username, "newalice")
	}
	if respBody.AvatarURL == nil || *respBody.AvatarURL != avatarURL {
		t.Errorf("AvatarURL: got %v, want %q", respBody.AvatarURL, avatarURL)
	}
}

func TestNewMeHandler_PUT_Success_NilAvatarURL(t *testing.T) {
	updated := &repository.User{
		ID:        "00000000-0000-0000-0000-000000000002",
		Username:  "bob",
		AvatarURL: nil,
	}
	users := &stubUserProvider{updateUser: updated}
	h := handler.NewMeHandler(users)

	bodyStr := `{"username":"bob"}`
	claims := &auth.TokenClaims{UID: "uid5", Email: "bob@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/me", bytes.NewBufferString(bodyStr)),
		claims,
	)
	req.Header.Set("Content-Type", "application/json")
	rec := serveMe(h, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}

	var respBody handler.MeResponse
	if err := json.NewDecoder(rec.Body).Decode(&respBody); err != nil {
		t.Fatalf("could not decode response: %v", err)
	}
	if respBody.AvatarURL != nil {
		t.Errorf("expected nil AvatarURL, got %q", *respBody.AvatarURL)
	}
}

func TestNewMeHandler_PUT_PassesCorrectArgsToUpdateProfile(t *testing.T) {
	avatarURL := "https://example.com/avatar.png"
	var gotUID, gotUsername string
	var gotAvatarURL *string

	recordingStub := &recordingUserProvider{
		onUpdateProfile: func(uid, username string, avatar *string) (*repository.User, error) {
			gotUID = uid
			gotUsername = username
			gotAvatarURL = avatar
			return &repository.User{ID: "u1", Username: username, AvatarURL: avatar}, nil
		},
	}

	h := handler.NewMeHandler(recordingStub)
	bodyStr := `{"username":"alice","avatar_url":"https://example.com/avatar.png"}`
	claims := &auth.TokenClaims{UID: "firebase-uid-put", Email: "alice@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodPut, "/api/me", bytes.NewBufferString(bodyStr)),
		claims,
	)
	req.Header.Set("Content-Type", "application/json")
	serveMe(h, req)

	if gotUID != "firebase-uid-put" {
		t.Errorf("UpdateProfile UID: got %q, want %q", gotUID, "firebase-uid-put")
	}
	if gotUsername != "alice" {
		t.Errorf("UpdateProfile username: got %q, want %q", gotUsername, "alice")
	}
	if gotAvatarURL == nil || *gotAvatarURL != avatarURL {
		t.Errorf("UpdateProfile avatarURL: got %v, want %q", gotAvatarURL, avatarURL)
	}
}

func TestNewMeHandler_UnsupportedMethod_Returns405(t *testing.T) {
	users := &stubUserProvider{}
	h := handler.NewMeHandler(users)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(
		httptest.NewRequest(http.MethodDelete, "/api/me", nil),
		claims,
	)
	rec := serveMe(h, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405 for DELETE, got %d", rec.Code)
	}
}

// recordingUserProvider captures Upsert and UpdateProfile arguments.
type recordingUserProvider struct {
	onUpsert        func(firebaseUID, email string) (*repository.User, error)
	onUpdateProfile func(uid, username string, avatar *string) (*repository.User, error)
}

func (r *recordingUserProvider) Upsert(_ context.Context, firebaseUID, email, _ string) (*repository.User, error) {
	if r.onUpsert != nil {
		return r.onUpsert(firebaseUID, email)
	}
	return &repository.User{ID: "default", Username: "default"}, nil
}

func (r *recordingUserProvider) UpdateProfile(_ context.Context, uid, username string, avatar *string) (*repository.User, error) {
	if r.onUpdateProfile != nil {
		return r.onUpdateProfile(uid, username, avatar)
	}
	return &repository.User{ID: "default", Username: username, AvatarURL: avatar}, nil
}
