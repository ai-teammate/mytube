package middleware

import (
	"encoding/json"
	"net/http"
	"strings"
	"sync"
	"time"

	"golang.org/x/time/rate"
)

// ipEntry holds a per-IP rate limiter and tracks the last time the IP was seen
// so stale entries can be evicted from the map.
type ipEntry struct {
	limiter  *rate.Limiter
	lastSeen time.Time
}

// ipLimiter holds a token-bucket rate limiter keyed by client IP with TTL-based
// eviction to prevent unbounded memory growth under IP-spoofing or scanning attacks.
type ipLimiter struct {
	mu       sync.Mutex
	limiters map[string]*ipEntry
	r        rate.Limit
	burst    int
}

func newIPLimiter(r rate.Limit, burst int) *ipLimiter {
	l := &ipLimiter{
		limiters: make(map[string]*ipEntry),
		r:        r,
		burst:    burst,
	}
	// Evict entries not seen in the last 5 minutes; run cleanup every minute.
	go func() {
		for range time.Tick(time.Minute) {
			l.mu.Lock()
			for ip, e := range l.limiters {
				if time.Since(e.lastSeen) > 5*time.Minute {
					delete(l.limiters, ip)
				}
			}
			l.mu.Unlock()
		}
	}()
	return l
}

func (l *ipLimiter) get(ip string) *rate.Limiter {
	l.mu.Lock()
	defer l.mu.Unlock()
	if e, ok := l.limiters[ip]; ok {
		e.lastSeen = time.Now()
		return e.limiter
	}
	lim := rate.NewLimiter(l.r, l.burst)
	l.limiters[ip] = &ipEntry{limiter: lim, lastSeen: time.Now()}
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

// RateLimitPublicAllow checks whether the request is allowed under the public
// per-IP rate limit without wrapping a handler. Use this inside handlers to
// apply rate limiting selectively (e.g. only to GET, not POST).
func RateLimitPublicAllow(r *http.Request) bool {
	return publicLimiter.get(clientIP(r)).Allow()
}

// clientIP extracts the client IP from X-Forwarded-For or falls back to
// RemoteAddr. On Cloud Run, the Google load balancer appends the real client IP
// at the end of the X-Forwarded-For chain; taking the rightmost non-empty entry
// prevents clients from spoofing their IP by prepending arbitrary values.
func clientIP(r *http.Request) string {
	if xff := r.Header.Get("X-Forwarded-For"); xff != "" {
		ips := strings.Split(xff, ",")
		// Use the rightmost non-empty entry; it is set by the nearest trusted
		// proxy (Cloud Run load balancer) and cannot be forged by the client.
		for i := len(ips) - 1; i >= 0; i-- {
			ip := strings.TrimSpace(ips[i])
			if ip != "" {
				return ip
			}
		}
	}
	// RemoteAddr is "IP:port" for TCP connections; strip the port.
	addr := r.RemoteAddr
	for i := len(addr) - 1; i >= 0; i-- {
		if addr[i] == ':' {
			return addr[:i]
		}
	}
	return addr
}
