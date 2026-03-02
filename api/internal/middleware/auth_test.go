package middleware_test

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/ai-teammate/mytube/api/internal/auth"
	"github.com/ai-teammate/mytube/api/internal/middleware"
)

// ─── stub verifier ────────────────────────────────────────────────────────────

// stubVerifier implements auth.TokenVerifier for unit tests.
type stubVerifier struct {
	claims *auth.TokenClaims
	err    error
}

func (s *stubVerifier) VerifyIDToken(_ context.Context, _ string) (*auth.TokenClaims, error) {
	return s.claims, s.err
}

// ─── helpers ──────────────────────────────────────────────────────────────────

// nextHandlerCalled is a sentinel handler that records whether it was invoked.
func nextHandlerCalled(called *bool) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		*called = true
		w.WriteHeader(http.StatusOK)
	})
}

// ─── RequireAuth tests ────────────────────────────────────────────────────────

func TestRequireAuth_MissingAuthHeader(t *testing.T) {
	v := &stubVerifier{claims: &auth.TokenClaims{UID: "uid", Email: "a@b.com"}}
	called := false
	h := middleware.RequireAuth(v)(nextHandlerCalled(&called))

	req := httptest.NewRequest(http.MethodGet, "/api/me", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rec.Code)
	}
	if called {
		t.Error("next handler must not be called when Authorization header is absent")
	}
}

func TestRequireAuth_NonBearerScheme(t *testing.T) {
	v := &stubVerifier{claims: &auth.TokenClaims{UID: "uid", Email: "a@b.com"}}
	called := false
	h := middleware.RequireAuth(v)(nextHandlerCalled(&called))

	req := httptest.NewRequest(http.MethodGet, "/api/me", nil)
	req.Header.Set("Authorization", "Basic dXNlcjpwYXNz")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rec.Code)
	}
	if called {
		t.Error("next handler must not be called for non-Bearer scheme")
	}
}

func TestRequireAuth_EmptyToken(t *testing.T) {
	v := &stubVerifier{claims: &auth.TokenClaims{UID: "uid", Email: "a@b.com"}}
	called := false
	h := middleware.RequireAuth(v)(nextHandlerCalled(&called))

	req := httptest.NewRequest(http.MethodGet, "/api/me", nil)
	req.Header.Set("Authorization", "Bearer ")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rec.Code)
	}
	if called {
		t.Error("next handler must not be called for empty token")
	}
}

func TestRequireAuth_InvalidToken(t *testing.T) {
	verifyErr := errors.New("token expired")
	v := &stubVerifier{err: verifyErr}
	called := false
	h := middleware.RequireAuth(v)(nextHandlerCalled(&called))

	req := httptest.NewRequest(http.MethodGet, "/api/me", nil)
	req.Header.Set("Authorization", "Bearer bad.token.here")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rec.Code)
	}
	if called {
		t.Error("next handler must not be called for invalid token")
	}
}

func TestRequireAuth_ValidToken_CallsNext(t *testing.T) {
	claims := &auth.TokenClaims{UID: "firebase-uid", Email: "user@example.com"}
	v := &stubVerifier{claims: claims}
	called := false
	h := middleware.RequireAuth(v)(nextHandlerCalled(&called))

	req := httptest.NewRequest(http.MethodGet, "/api/me", nil)
	req.Header.Set("Authorization", "Bearer valid.token.value")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}
	if !called {
		t.Error("next handler must be called for valid token")
	}
}

func TestRequireAuth_ValidToken_InjectsClaimsInContext(t *testing.T) {
	claims := &auth.TokenClaims{UID: "firebase-uid-42", Email: "injected@example.com"}
	v := &stubVerifier{claims: claims}

	var gotClaims *auth.TokenClaims
	captureHandler := http.HandlerFunc(func(_ http.ResponseWriter, r *http.Request) {
		gotClaims = middleware.ClaimsFromContext(r.Context())
	})

	h := middleware.RequireAuth(v)(captureHandler)
	req := httptest.NewRequest(http.MethodGet, "/api/me", nil)
	req.Header.Set("Authorization", "Bearer some.valid.token")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if gotClaims == nil {
		t.Fatal("expected claims in context, got nil")
	}
	if gotClaims.UID != claims.UID {
		t.Errorf("UID: got %q, want %q", gotClaims.UID, claims.UID)
	}
	if gotClaims.Email != claims.Email {
		t.Errorf("Email: got %q, want %q", gotClaims.Email, claims.Email)
	}
}

func TestRequireAuth_BearerCaseInsensitive(t *testing.T) {
	claims := &auth.TokenClaims{UID: "uid", Email: "a@b.com"}
	v := &stubVerifier{claims: claims}
	called := false
	h := middleware.RequireAuth(v)(nextHandlerCalled(&called))

	req := httptest.NewRequest(http.MethodGet, "/api/me", nil)
	req.Header.Set("Authorization", "BEARER my.token.value")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200 for case-insensitive Bearer, got %d", rec.Code)
	}
	if !called {
		t.Error("next handler must be called for BEARER (case-insensitive)")
	}
}

func TestRequireAuth_401ResponseBody_IsJSON(t *testing.T) {
	v := &stubVerifier{err: errors.New("bad token")}
	h := middleware.RequireAuth(v)(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {}))

	req := httptest.NewRequest(http.MethodGet, "/api/me", nil)
	req.Header.Set("Authorization", "Bearer bad.token")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	ct := rec.Header().Get("Content-Type")
	if ct != "application/json" {
		t.Errorf("expected Content-Type application/json, got %q", ct)
	}

	var body map[string]string
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("could not decode 401 body as JSON: %v", err)
	}
	if _, ok := body["error"]; !ok {
		t.Error("401 JSON body must contain 'error' key")
	}
}

// ─── ClaimsFromContext tests ──────────────────────────────────────────────────

func TestClaimsFromContext_Empty(t *testing.T) {
	ctx := context.Background()
	got := middleware.ClaimsFromContext(ctx)
	if got != nil {
		t.Errorf("expected nil claims from empty context, got %+v", got)
	}
}
