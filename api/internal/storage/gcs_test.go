// Package storage provides GCS helpers for the main API service.
package storage_test

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/ai-teammate/mytube/api/internal/storage"
)

// ─── stub Signer ──────────────────────────────────────────────────────────────

// stubSigner implements storage.Signer for testing.
type stubSigner struct {
	url string
	err error
	// capturedOpts holds the last SignedURLOptions passed.
	capturedOpts storage.SignedURLOptions
}

func (s *stubSigner) SignPutURL(_ context.Context, opts storage.SignedURLOptions) (string, error) {
	s.capturedOpts = opts
	return s.url, s.err
}

// ─── Signer interface tests ───────────────────────────────────────────────────

// TestSignedURLOptions_Fields verifies that the SignedURLOptions struct exposes
// the required fields.
func TestSignedURLOptions_Fields(t *testing.T) {
	opts := storage.SignedURLOptions{
		Bucket:      "my-bucket",
		Object:      "raw/user1/vid1",
		ContentType: "video/mp4",
		Expires:     15 * time.Minute,
	}

	if opts.Bucket != "my-bucket" {
		t.Errorf("Bucket: got %q, want %q", opts.Bucket, "my-bucket")
	}
	if opts.Object != "raw/user1/vid1" {
		t.Errorf("Object: got %q, want %q", opts.Object, "raw/user1/vid1")
	}
	if opts.ContentType != "video/mp4" {
		t.Errorf("ContentType: got %q, want %q", opts.ContentType, "video/mp4")
	}
	if opts.Expires != 15*time.Minute {
		t.Errorf("Expires: got %v, want %v", opts.Expires, 15*time.Minute)
	}
}

// TestStubSigner_ReturnsURL verifies the stub Signer passes through the URL.
func TestStubSigner_ReturnsURL(t *testing.T) {
	signer := &stubSigner{url: "https://storage.googleapis.com/my-bucket/raw/u/v?X-Goog-Signature=abc"}

	url, err := signer.SignPutURL(context.Background(), storage.SignedURLOptions{
		Bucket:      "my-bucket",
		Object:      "raw/u/v",
		ContentType: "video/mp4",
		Expires:     15 * time.Minute,
	})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if url != signer.url {
		t.Errorf("URL: got %q, want %q", url, signer.url)
	}
}

// TestStubSigner_ReturnsError verifies the stub Signer propagates errors.
func TestStubSigner_ReturnsError(t *testing.T) {
	sigErr := errors.New("sign failed")
	signer := &stubSigner{err: sigErr}

	url, err := signer.SignPutURL(context.Background(), storage.SignedURLOptions{
		Bucket:      "my-bucket",
		Object:      "raw/u/v",
		ContentType: "video/mp4",
		Expires:     15 * time.Minute,
	})

	if url != "" {
		t.Errorf("expected empty URL on error, got %q", url)
	}
	if !errors.Is(err, sigErr) {
		t.Errorf("expected wrapped sigErr, got: %v", err)
	}
}

// TestStubSigner_CapturesOptions verifies the stub records the options it
// received so handler tests can assert on the correct values.
func TestStubSigner_CapturesOptions(t *testing.T) {
	signer := &stubSigner{url: "https://signed.url"}

	opts := storage.SignedURLOptions{
		Bucket:      "test-bucket",
		Object:      "raw/uid/video-id",
		ContentType: "video/webm",
		Expires:     15 * time.Minute,
	}
	_, _ = signer.SignPutURL(context.Background(), opts)

	if signer.capturedOpts.Bucket != opts.Bucket {
		t.Errorf("Bucket: got %q, want %q", signer.capturedOpts.Bucket, opts.Bucket)
	}
	if signer.capturedOpts.Object != opts.Object {
		t.Errorf("Object: got %q, want %q", signer.capturedOpts.Object, opts.Object)
	}
	if signer.capturedOpts.ContentType != opts.ContentType {
		t.Errorf("ContentType: got %q, want %q", signer.capturedOpts.ContentType, opts.ContentType)
	}
	if signer.capturedOpts.Expires != opts.Expires {
		t.Errorf("Expires: got %v, want %v", signer.capturedOpts.Expires, opts.Expires)
	}
}
