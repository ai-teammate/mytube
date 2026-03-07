package middleware_test

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/ai-teammate/mytube/api/internal/middleware"
)

// okHandler is a trivial handler that always returns 200 OK.
var okHandler = http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
	w.WriteHeader(http.StatusOK)
})

// ─── CORS header tests ────────────────────────────────────────────────────────

func TestCORS_SetsAllowOriginHeader(t *testing.T) {
	h := middleware.CORS(okHandler)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/recent", nil)
	req.Header.Set("Origin", "https://ai-teammate.github.io")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	got := rec.Header().Get("Access-Control-Allow-Origin")
	if got != "https://ai-teammate.github.io" {
		t.Errorf("Access-Control-Allow-Origin: got %q, want %q", got, "https://ai-teammate.github.io")
	}
}

func TestCORS_SetsAllowMethodsHeader(t *testing.T) {
	h := middleware.CORS(okHandler)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/popular", nil)
	req.Header.Set("Origin", "https://ai-teammate.github.io")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	got := rec.Header().Get("Access-Control-Allow-Methods")
	if got == "" {
		t.Error("Access-Control-Allow-Methods header must be present")
	}
}

func TestCORS_SetsAllowHeadersHeader(t *testing.T) {
	h := middleware.CORS(okHandler)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/recent", nil)
	req.Header.Set("Origin", "https://ai-teammate.github.io")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	got := rec.Header().Get("Access-Control-Allow-Headers")
	if got == "" {
		t.Error("Access-Control-Allow-Headers header must be present")
	}
}

func TestCORS_PreflightReturns200(t *testing.T) {
	h := middleware.CORS(okHandler)

	req := httptest.NewRequest(http.MethodOptions, "/api/me/videos", nil)
	req.Header.Set("Origin", "https://ai-teammate.github.io")
	req.Header.Set("Access-Control-Request-Method", "GET")
	req.Header.Set("Access-Control-Request-Headers", "authorization")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("OPTIONS preflight: expected 200, got %d", rec.Code)
	}
}

func TestCORS_PreflightDoesNotCallNext(t *testing.T) {
	called := false
	next := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		called = true
		w.WriteHeader(http.StatusOK)
	})
	h := middleware.CORS(next)

	req := httptest.NewRequest(http.MethodOptions, "/api/videos/recent", nil)
	req.Header.Set("Origin", "https://ai-teammate.github.io")
	req.Header.Set("Access-Control-Request-Method", "GET")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if called {
		t.Error("next handler must NOT be called for OPTIONS preflight")
	}
}

func TestCORS_NonPreflightCallsNext(t *testing.T) {
	called := false
	next := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		called = true
		w.WriteHeader(http.StatusOK)
	})
	h := middleware.CORS(next)

	req := httptest.NewRequest(http.MethodGet, "/api/videos/recent", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if !called {
		t.Error("next handler must be called for non-OPTIONS requests")
	}
}

func TestCORS_HeadersPresentForAllMethods(t *testing.T) {
	methods := []string{http.MethodGet, http.MethodPost, http.MethodPut, http.MethodDelete}
	for _, method := range methods {
		t.Run(method, func(t *testing.T) {
			h := middleware.CORS(okHandler)
			req := httptest.NewRequest(method, "/api/videos", nil)
			req.Header.Set("Origin", "https://ai-teammate.github.io")
			rec := httptest.NewRecorder()
			h.ServeHTTP(rec, req)

			if rec.Header().Get("Access-Control-Allow-Origin") != "https://ai-teammate.github.io" {
				t.Errorf("%s: missing Access-Control-Allow-Origin header", method)
			}
		})
	}
}
