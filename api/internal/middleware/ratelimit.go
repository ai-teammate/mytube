package middleware

import (
	"encoding/json"
	"net/http"
	"sync"

	"golang.org/x/time/rate"
)

// ipLimiter holds a token-bucket rate limiter keyed by client IP.
type ipLimiter struct {
	mu       sync.Mutex
	limiters map[string]*rate.Limiter
	r        rate.Limit
	burst    int
}

func newIPLimiter(r rate.Limit, burst int) *ipLimiter {
	return &ipLimiter{
		limiters: make(map[string]*rate.Limiter),
		r:        r,
		burst:    burst,
	}
}

func (l *ipLimiter) get(ip string) *rate.Limiter {
	l.mu.Lock()
	defer l.mu.Unlock()
	if lim, ok := l.limiters[ip]; ok {
		return lim
	}
	lim := rate.NewLimiter(l.r, l.burst)
	l.limiters[ip] = lim
	return lim
}

// publicLimiter is a package-level in-process rate limiter for public endpoints:
// 60 requests/minute per IP (burst of 20).
var publicLimiter = newIPLimiter(rate.Limit(1), 20) // 1 req/s steady state, burst 20

// RateLimitPublic is middleware that applies a per-IP token-bucket rate limit
// suitable for public, unauthenticated read endpoints. Requests that exceed the
// limit receive 429 Too Many Requests.
//
// Current limits: 1 req/s steady state with a burst of 20 (≈60 req/min per IP).
// For higher-volume deployments consider offloading rate limiting to Cloud Armor
// or a Cloud Run concurrency setting.
func RateLimitPublic(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ip := clientIP(r)
		if !publicLimiter.get(ip).Allow() {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusTooManyRequests)
			_ = json.NewEncoder(w).Encode(map[string]string{"error": "rate limit exceeded"})
			return
		}
		next.ServeHTTP(w, r)
	})
}

// clientIP extracts the client IP from X-Forwarded-For (Cloud Run sets this)
// or falls back to RemoteAddr.
func clientIP(r *http.Request) string {
	if xff := r.Header.Get("X-Forwarded-For"); xff != "" {
		// X-Forwarded-For may contain a comma-separated list; use the first entry.
		for i := 0; i < len(xff); i++ {
			if xff[i] == ',' {
				return xff[:i]
			}
		}
		return xff
	}
	// RemoteAddr is "IP:port" for TCP connections.
	addr := r.RemoteAddr
	for i := len(addr) - 1; i >= 0; i-- {
		if addr[i] == ':' {
			return addr[:i]
		}
	}
	return addr
}
