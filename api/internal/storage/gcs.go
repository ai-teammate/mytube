// Package storage provides GCS helpers for the main API service.
package storage

import (
	"context"
	"fmt"
	"net/http"
	"time"

	gcs "cloud.google.com/go/storage"
)

// SignedURLOptions configures signed URL generation.
type SignedURLOptions struct {
	// Bucket is the GCS bucket name.
	Bucket string
	// Object is the GCS object path (key).
	Object string
	// ContentType is the expected MIME type of the upload.
	ContentType string
	// Expires is how long the signed URL remains valid.
	Expires time.Duration
}

// Signer generates GCS signed PUT URLs.
// Satisfied by *GCSSigner and allows tests to inject a stub.
type Signer interface {
	SignPutURL(ctx context.Context, opts SignedURLOptions) (string, error)
}

// GCSSigner generates signed PUT URLs using the real GCS client.
// The underlying *storage.Client must be initialised with credentials that
// have the iam.serviceAccounts.signBlob permission.
type GCSSigner struct {
	client *gcs.Client
}

// NewGCSSigner constructs a GCSSigner backed by the provided *storage.Client.
func NewGCSSigner(client *gcs.Client) *GCSSigner {
	return &GCSSigner{client: client}
}

// SignPutURL generates a V4 signed URL that allows an HTTP PUT of a single
// object to GCS.  The URL expires after opts.Expires.
func (s *GCSSigner) SignPutURL(ctx context.Context, opts SignedURLOptions) (string, error) {
	url, err := s.client.Bucket(opts.Bucket).SignedURL(opts.Object, &gcs.SignedURLOptions{
		Method:      http.MethodPut,
		ContentType: opts.ContentType,
		Expires:     time.Now().Add(opts.Expires),
		Scheme:      gcs.SigningSchemeV4,
	})
	if err != nil {
		return "", fmt.Errorf("sign PUT URL for gs://%s/%s: %w", opts.Bucket, opts.Object, err)
	}
	return url, nil
}
