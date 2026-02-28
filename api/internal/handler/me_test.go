package handler_test

import (
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
	user *repository.User
	err  error
}

func (s *stubUserProvider) Upsert(_ context.Context, _, _ string) (*repository.User, error) {
	return s.user, s.err
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

// ─── Tests ────────────────────────────────────────────────────────────────────

func TestNewMeHandler_NoClaims_Returns401(t *testing.T) {
	users := &stubUserProvider{user: &repository.User{ID: "u1", Username: "alice"}}
	h := handler.NewMeHandler(users)

	req := httptest.NewRequest(http.MethodGet, "/api/me", nil)
	// No claims injected into context.
	rec := httptest.NewRecorder()
	h(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401 when no claims in context, got %d", rec.Code)
	}
}

func TestNewMeHandler_UpsertError_Returns500(t *testing.T) {
	dbErr := errors.New("database error")
	users := &stubUserProvider{err: dbErr}
	h := handler.NewMeHandler(users)

	claims := &auth.TokenClaims{UID: "uid1", Email: "user@example.com"}
	req := withClaims(httptest.NewRequest(http.MethodGet, "/api/me", nil), claims)
	rec := httptest.NewRecorder()
	h(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500 on upsert error, got %d", rec.Code)
	}
}

func TestNewMeHandler_UserNotFoundAfterUpsert_Returns500(t *testing.T) {
	// Upsert returns (nil, nil) — provisioning succeeded but row not visible.
	users := &stubUserProvider{user: nil, err: nil}
	h := handler.NewMeHandler(users)

	claims := &auth.TokenClaims{UID: "uid2", Email: "user@example.com"}
	req := withClaims(httptest.NewRequest(http.MethodGet, "/api/me", nil), claims)
	rec := httptest.NewRecorder()
	h(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Errorf("expected 500 when user row missing after upsert, got %d", rec.Code)
	}
}

func TestNewMeHandler_Success_ReturnsUserJSON(t *testing.T) {
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
	rec := httptest.NewRecorder()
	h(rec, req)

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

func TestNewMeHandler_Success_NilAvatarURL(t *testing.T) {
	user := &repository.User{
		ID:        "00000000-0000-0000-0000-000000000002",
		Username:  "bob",
		AvatarURL: nil,
	}
	users := &stubUserProvider{user: user}
	h := handler.NewMeHandler(users)

	claims := &auth.TokenClaims{UID: "uid4", Email: "bob@example.com"}
	req := withClaims(httptest.NewRequest(http.MethodGet, "/api/me", nil), claims)
	rec := httptest.NewRecorder()
	h(rec, req)

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

func TestNewMeHandler_UsesFirebaseUIDFromClaims(t *testing.T) {
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
	rec := httptest.NewRecorder()
	h(rec, req)

	if gotUID != claims.UID {
		t.Errorf("Upsert called with UID %q, want %q", gotUID, claims.UID)
	}
	if gotEmail != claims.Email {
		t.Errorf("Upsert called with email %q, want %q", gotEmail, claims.Email)
	}
}

// recordingUserProvider captures Upsert arguments.
type recordingUserProvider struct {
	onUpsert func(firebaseUID, email string) (*repository.User, error)
}

func (r *recordingUserProvider) Upsert(_ context.Context, firebaseUID, email string) (*repository.User, error) {
	return r.onUpsert(firebaseUID, email)
}
