// Package storage provides GCS helpers for the main API service.
package storage

import (
	"context"
	"fmt"
	"net/http"
	"time"

	gcs "cloud.google.com/go/storage"
	"google.golang.org/api/iterator"
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

// ObjectDeleter abstracts GCS object deletion so tests can inject a stub.
type ObjectDeleter interface {
	// DeleteObject deletes a single GCS object. A not-found error is silently
	// ignored so that deletion is idempotent.
	DeleteObject(ctx context.Context, bucket, object string) error
	// DeletePrefix deletes all GCS objects whose name starts with prefix.
	// A best-effort approach is used: all objects are enumerated and deleted
	// individually; errors for individual objects are returned on first failure.
	DeletePrefix(ctx context.Context, bucket, prefix string) error
}

// GCSObjectDeleter implements ObjectDeleter using the real GCS client.
type GCSObjectDeleter struct {
	client *gcs.Client
}

// NewGCSObjectDeleter constructs a GCSObjectDeleter backed by the provided *gcs.Client.
func NewGCSObjectDeleter(client *gcs.Client) *GCSObjectDeleter {
	return &GCSObjectDeleter{client: client}
}

// DeleteObject deletes the GCS object at gs://<bucket>/<object>.
// Not-found errors are silently ignored to make deletion idempotent.
func (d *GCSObjectDeleter) DeleteObject(ctx context.Context, bucket, object string) error {
	err := d.client.Bucket(bucket).Object(object).Delete(ctx)
	if err != nil && err != gcs.ErrObjectNotExist {
		return fmt.Errorf("delete gs://%s/%s: %w", bucket, object, err)
	}
	return nil
}

// DeletePrefix deletes all GCS objects under gs://<bucket>/<prefix>.
// Not-found errors on individual objects are silently ignored.
func (d *GCSObjectDeleter) DeletePrefix(ctx context.Context, bucket, prefix string) error {
	it := d.client.Bucket(bucket).Objects(ctx, &gcs.Query{Prefix: prefix})
	for {
		attrs, err := it.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			return fmt.Errorf("list objects under gs://%s/%s: %w", bucket, prefix, err)
		}
		if delErr := d.client.Bucket(bucket).Object(attrs.Name).Delete(ctx); delErr != nil && delErr != gcs.ErrObjectNotExist {
			return fmt.Errorf("delete gs://%s/%s: %w", bucket, attrs.Name, delErr)
		}
	}
	return nil
}

// NopObjectDeleter is a no-op ObjectDeleter used when GCS cleanup is not
// configured (e.g. tests or environments where no GCS client is available).
type NopObjectDeleter struct{}

// NewNopObjectDeleter returns a NopObjectDeleter that silently ignores all deletions.
func NewNopObjectDeleter() *NopObjectDeleter { return &NopObjectDeleter{} }

func (*NopObjectDeleter) DeleteObject(_ context.Context, _, _ string) error { return nil }
func (*NopObjectDeleter) DeletePrefix(_ context.Context, _, _ string) error { return nil }
